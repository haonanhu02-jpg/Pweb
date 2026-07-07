from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from tender_poc.models import AttachmentDocumentV1, SpringDemandAssessmentV1, TenderNoticeV1
from tender_poc.paths import DB_PATH, EXPORT_DIR, RAW_DIR, ensure_data_dirs


@dataclass
class InsertSummary:
    new_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0


@dataclass
class ScreeningSummary:
    screened_count: int = 0
    failed_count: int = 0


class TenderStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        ensure_data_dirs()
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenders (
                id TEXT PRIMARY KEY,
                source_platform TEXT NOT NULL,
                source_channel TEXT NOT NULL,
                notice_type TEXT,
                title TEXT NOT NULL,
                buyer TEXT,
                agency TEXT,
                publish_time TEXT,
                deadline TEXT,
                bid_open_time TEXT,
                region TEXT,
                industry TEXT,
                platform_url TEXT NOT NULL UNIQUE,
                original_url TEXT,
                attachments_json TEXT NOT NULL,
                content_text TEXT NOT NULL,
                raw_fields_json TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                raw_html_path TEXT,
                fetched_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spring_demand_assessments (
                notice_id TEXT PRIMARY KEY,
                is_procurement_notice INTEGER NOT NULL,
                procurement_stage TEXT NOT NULL,
                has_spring_demand INTEGER NOT NULL,
                demand_type TEXT,
                procurement_subject TEXT,
                product_category TEXT,
                industry_category TEXT,
                opportunity_level TEXT NOT NULL,
                relevance_score INTEGER NOT NULL,
                matched_terms_json TEXT NOT NULL,
                negative_terms_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                assessed_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (notice_id) REFERENCES tenders(id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spring_demand_reviews (
                notice_id TEXT PRIMARY KEY,
                review_status TEXT NOT NULL DEFAULT 'pending_review',
                review_note TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (notice_id) REFERENCES tenders(id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attachment_documents (
                notice_id TEXT NOT NULL,
                attachment_url TEXT NOT NULL,
                attachment_name TEXT NOT NULL,
                file_path TEXT,
                file_ext TEXT,
                status TEXT NOT NULL,
                content_text TEXT NOT NULL DEFAULT '',
                content_hash TEXT,
                error TEXT,
                fetched_at TEXT,
                parsed_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (notice_id, attachment_url),
                FOREIGN KEY (notice_id) REFERENCES tenders(id)
            )
            """
        )
        self.conn.commit()

    def insert_many(self, notices: list[TenderNoticeV1], raw_html_by_notice_id: dict[str, str]) -> InsertSummary:
        summary = InsertSummary()
        for notice in notices:
            try:
                inserted = self.insert_notice(notice, raw_html_by_notice_id.get(notice.id))
                if inserted:
                    summary.new_count += 1
                else:
                    summary.duplicate_count += 1
            except sqlite3.IntegrityError:
                summary.duplicate_count += 1
            except Exception:
                summary.failed_count += 1
        return summary

    def insert_notice(self, notice: TenderNoticeV1, raw_html: str | None = None) -> bool:
        raw_html_path = self._write_raw_html(notice, raw_html) if raw_html else None
        payload = notice.model_dump(mode="json")
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO tenders (
                id,
                source_platform,
                source_channel,
                notice_type,
                title,
                buyer,
                agency,
                publish_time,
                deadline,
                bid_open_time,
                region,
                industry,
                platform_url,
                original_url,
                attachments_json,
                content_text,
                raw_fields_json,
                content_hash,
                raw_html_path,
                fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["id"],
                payload["source_platform"],
                payload["source_channel"],
                payload.get("notice_type"),
                payload["title"],
                payload.get("buyer"),
                payload.get("agency"),
                payload.get("publish_time"),
                payload.get("deadline"),
                payload.get("bid_open_time"),
                payload.get("region"),
                payload.get("industry"),
                payload["platform_url"],
                payload.get("original_url"),
                json.dumps(payload["attachments"], ensure_ascii=False),
                payload["content_text"],
                json.dumps(payload["raw_fields"], ensure_ascii=False),
                payload["content_hash"],
                str(raw_html_path) if raw_html_path else None,
                payload["fetched_at"],
            ),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def list_notices(self, limit: int | None = None) -> list[TenderNoticeV1]:
        sql = """
            SELECT *
            FROM tenders
            ORDER BY COALESCE(publish_time, fetched_at) DESC
        """
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        rows = self.conn.execute(sql, params).fetchall()
        return [TenderNoticeV1(**self._row_to_notice_payload(row)) for row in rows]

    def upsert_assessments(self, assessments: list[SpringDemandAssessmentV1]) -> ScreeningSummary:
        summary = ScreeningSummary()
        for assessment in assessments:
            try:
                self.upsert_assessment(assessment)
                summary.screened_count += 1
            except Exception:
                summary.failed_count += 1
        return summary

    def upsert_assessment(self, assessment: SpringDemandAssessmentV1) -> None:
        payload = assessment.model_dump(mode="json")
        self.conn.execute(
            """
            INSERT INTO spring_demand_assessments (
                notice_id,
                is_procurement_notice,
                procurement_stage,
                has_spring_demand,
                demand_type,
                procurement_subject,
                product_category,
                industry_category,
                opportunity_level,
                relevance_score,
                matched_terms_json,
                negative_terms_json,
                evidence_json,
                reason,
                assessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(notice_id) DO UPDATE SET
                is_procurement_notice = excluded.is_procurement_notice,
                procurement_stage = excluded.procurement_stage,
                has_spring_demand = excluded.has_spring_demand,
                demand_type = excluded.demand_type,
                procurement_subject = excluded.procurement_subject,
                product_category = excluded.product_category,
                industry_category = excluded.industry_category,
                opportunity_level = excluded.opportunity_level,
                relevance_score = excluded.relevance_score,
                matched_terms_json = excluded.matched_terms_json,
                negative_terms_json = excluded.negative_terms_json,
                evidence_json = excluded.evidence_json,
                reason = excluded.reason,
                assessed_at = excluded.assessed_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                payload["notice_id"],
                int(payload["is_procurement_notice"]),
                payload["procurement_stage"],
                int(payload["has_spring_demand"]),
                payload.get("demand_type"),
                payload.get("procurement_subject"),
                payload.get("product_category"),
                payload.get("industry_category"),
                payload["opportunity_level"],
                payload["relevance_score"],
                json.dumps(payload["matched_terms"], ensure_ascii=False),
                json.dumps(payload["negative_terms"], ensure_ascii=False),
                json.dumps(payload["evidence"], ensure_ascii=False),
                payload["reason"],
                payload["assessed_at"],
            ),
        )
        self.conn.commit()

    def upsert_attachment_document(self, document: AttachmentDocumentV1) -> None:
        payload = document.model_dump(mode="json")
        self.conn.execute(
            """
            INSERT INTO attachment_documents (
                notice_id,
                attachment_url,
                attachment_name,
                file_path,
                file_ext,
                status,
                content_text,
                content_hash,
                error,
                fetched_at,
                parsed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(notice_id, attachment_url) DO UPDATE SET
                attachment_name = excluded.attachment_name,
                file_path = excluded.file_path,
                file_ext = excluded.file_ext,
                status = excluded.status,
                content_text = excluded.content_text,
                content_hash = excluded.content_hash,
                error = excluded.error,
                fetched_at = excluded.fetched_at,
                parsed_at = excluded.parsed_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                payload["notice_id"],
                payload["attachment_url"],
                payload["attachment_name"],
                payload.get("file_path"),
                payload.get("file_ext"),
                payload["status"],
                payload.get("content_text") or "",
                payload.get("content_hash"),
                payload.get("error"),
                payload.get("fetched_at"),
                payload["parsed_at"],
            ),
        )
        self.conn.commit()

    def get_attachment_document(self, notice_id: str, attachment_url: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT *
            FROM attachment_documents
            WHERE notice_id = ? AND attachment_url = ?
            """,
            (notice_id, attachment_url),
        ).fetchone()
        return self._row_to_attachment_document_payload(row) if row else None

    def get_attachment_documents(self, notice_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM attachment_documents
            WHERE notice_id = ?
            ORDER BY attachment_name, attachment_url
            """,
            (notice_id,),
        ).fetchall()
        return [self._row_to_attachment_document_payload(row) for row in rows]

    def get_attachment_texts(self, notice_ids: list[str]) -> dict[str, list[str]]:
        if not notice_ids:
            return {}
        placeholders = ",".join("?" for _ in notice_ids)
        rows = self.conn.execute(
            f"""
            SELECT notice_id, content_text
            FROM attachment_documents
            WHERE notice_id IN ({placeholders})
              AND status = 'parsed'
              AND TRIM(content_text) != ''
            ORDER BY attachment_name, attachment_url
            """,
            tuple(notice_ids),
        ).fetchall()
        result: dict[str, list[str]] = {notice_id: [] for notice_id in notice_ids}
        for row in rows:
            result.setdefault(row["notice_id"], []).append(row["content_text"])
        return result

    def attachment_stats(self) -> dict[str, Any]:
        rows = self.conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM attachment_documents
            GROUP BY status
            ORDER BY count DESC
            """
        ).fetchall()
        total = self.conn.execute("SELECT COUNT(*) AS count FROM attachment_documents").fetchone()["count"]
        return {
            "total_count": total,
            "by_status": [dict(row) for row in rows],
        }

    def screen_stats(self) -> dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) AS assessed_count,
                SUM(CASE WHEN has_spring_demand = 1 THEN 1 ELSE 0 END) AS spring_demand_count,
                MAX(assessed_at) AS latest_assessed_at
            FROM spring_demand_assessments
            """
        ).fetchone()
        by_level = self.conn.execute(
            """
            SELECT opportunity_level, COUNT(*) AS count
            FROM spring_demand_assessments
            GROUP BY opportunity_level
            ORDER BY
                CASE opportunity_level
                    WHEN 'high' THEN 1
                    WHEN 'review' THEN 2
                    WHEN 'low' THEN 3
                    ELSE 4
                END
            """
        ).fetchall()
        by_stage = self.conn.execute(
            """
            SELECT procurement_stage, COUNT(*) AS count
            FROM spring_demand_assessments
            GROUP BY procurement_stage
            ORDER BY count DESC
            """
        ).fetchall()
        totals = dict(row)
        totals["assessed_count"] = totals.get("assessed_count") or 0
        totals["spring_demand_count"] = totals.get("spring_demand_count") or 0
        return {
            **totals,
            "by_level": [dict(item) for item in by_level],
            "by_stage": [dict(item) for item in by_stage],
        }

    def dashboard(self) -> dict[str, Any]:
        tender_stats = self.stats()
        screen_stats = self.screen_stats()
        pending_review_count = self.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM spring_demand_assessments a
            LEFT JOIN spring_demand_reviews r ON r.notice_id = a.notice_id
            WHERE a.opportunity_level IN ('high', 'review')
              AND COALESCE(r.review_status, 'pending_review') = 'pending_review'
            """
        ).fetchone()["count"]
        review_statuses = self.conn.execute(
            """
            SELECT COALESCE(r.review_status, 'pending_review') AS review_status, COUNT(*) AS count
            FROM spring_demand_assessments a
            LEFT JOIN spring_demand_reviews r ON r.notice_id = a.notice_id
            GROUP BY COALESCE(r.review_status, 'pending_review')
            ORDER BY count DESC
            """
        ).fetchall()
        return {
            "total_count": tender_stats["total_count"],
            "platform_count": tender_stats["platform_count"],
            "latest_publish_time": tender_stats["latest_publish_time"],
            "latest_created_at": tender_stats["latest_created_at"],
            "assessed_count": screen_stats["assessed_count"],
            "spring_demand_count": screen_stats["spring_demand_count"],
            "latest_assessed_at": screen_stats["latest_assessed_at"],
            "pending_review_count": pending_review_count,
            "by_platform": tender_stats["by_platform"],
            "by_level": screen_stats["by_level"],
            "by_stage": screen_stats["by_stage"],
            "by_review_status": [dict(item) for item in review_statuses],
        }

    def list_opportunities(
        self,
        *,
        min_level: str = "review",
        opportunity_level: str | None = None,
        review_status: str | None = None,
        platform: str | None = None,
        procurement_stage: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        level_rank = {"excluded": 0, "low": 1, "review": 2, "high": 3}
        min_rank = level_rank[min_level]
        where = [
            """
            CASE a.opportunity_level
                WHEN 'high' THEN 3
                WHEN 'review' THEN 2
                WHEN 'low' THEN 1
                ELSE 0
            END >= ?
            """
        ]
        params: list[Any] = [min_rank]
        if opportunity_level:
            where.append("a.opportunity_level = ?")
            params.append(opportunity_level)
        if review_status:
            where.append("COALESCE(r.review_status, 'pending_review') = ?")
            params.append(review_status)
        if platform:
            where.append("t.source_platform = ?")
            params.append(platform)
        if procurement_stage:
            where.append("a.procurement_stage = ?")
            params.append(procurement_stage)
        if q:
            like = f"%{q}%"
            where.append(
                """
                (
                    t.title LIKE ?
                    OR t.content_text LIKE ?
                    OR t.raw_fields_json LIKE ?
                    OR a.matched_terms_json LIKE ?
                    OR a.reason LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM attachment_documents d
                        WHERE d.notice_id = t.id
                          AND d.content_text LIKE ?
                    )
                )
                """
            )
            params.extend([like, like, like, like, like, like])

        where_sql = " AND ".join(where)
        total = self.conn.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM tenders t
            JOIN spring_demand_assessments a ON a.notice_id = t.id
            LEFT JOIN spring_demand_reviews r ON r.notice_id = t.id
            WHERE {where_sql}
            """,
            params,
        ).fetchone()["count"]
        rows = self.conn.execute(
            f"""
            SELECT
                t.id,
                t.title,
                t.source_platform,
                t.notice_type,
                t.publish_time,
                t.region,
                t.buyer,
                t.platform_url,
                t.original_url,
                a.procurement_stage,
                a.has_spring_demand,
                a.demand_type,
                a.procurement_subject,
                a.product_category,
                a.industry_category,
                a.opportunity_level,
                a.relevance_score,
                a.matched_terms_json,
                a.negative_terms_json,
                a.evidence_json,
                a.reason,
                a.assessed_at,
                COALESCE(r.review_status, 'pending_review') AS review_status,
                COALESCE(r.review_note, '') AS review_note,
                r.reviewed_at
            FROM tenders t
            JOIN spring_demand_assessments a ON a.notice_id = t.id
            LEFT JOIN spring_demand_reviews r ON r.notice_id = t.id
            WHERE {where_sql}
            ORDER BY a.relevance_score DESC, COALESCE(t.publish_time, t.fetched_at) DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [self._row_to_opportunity_summary(row) for row in rows],
        }

    def get_opportunity(self, notice_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT
                t.*,
                a.is_procurement_notice,
                a.procurement_stage,
                a.has_spring_demand,
                a.demand_type,
                a.procurement_subject,
                a.product_category,
                a.industry_category,
                a.opportunity_level,
                a.relevance_score,
                a.matched_terms_json,
                a.negative_terms_json,
                a.evidence_json,
                a.reason,
                a.assessed_at,
                COALESCE(r.review_status, 'pending_review') AS review_status,
                COALESCE(r.review_note, '') AS review_note,
                r.reviewed_at
            FROM tenders t
            JOIN spring_demand_assessments a ON a.notice_id = t.id
            LEFT JOIN spring_demand_reviews r ON r.notice_id = t.id
            WHERE t.id = ?
            """,
            (notice_id,),
        ).fetchone()
        if row is None:
            return None
        payload = self._row_to_notice_payload(row)
        payload["spring_demand_assessment"] = self._row_to_assessment_payload(row)
        payload["review"] = self._row_to_review_payload(row)
        payload["attachment_documents"] = self.get_attachment_documents(notice_id)
        return payload

    def upsert_review(self, notice_id: str, review_status: str, review_note: str = "") -> dict[str, Any]:
        reviewed_at = None if review_status == "pending_review" else datetime.utcnow().isoformat(timespec="seconds")
        self.conn.execute(
            """
            INSERT INTO spring_demand_reviews (
                notice_id,
                review_status,
                review_note,
                reviewed_at
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(notice_id) DO UPDATE SET
                review_status = excluded.review_status,
                review_note = excluded.review_note,
                reviewed_at = excluded.reviewed_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (notice_id, review_status, review_note, reviewed_at),
        )
        self.conn.commit()
        row = self.conn.execute(
            """
            SELECT notice_id AS id, review_status, review_note, reviewed_at
            FROM spring_demand_reviews
            WHERE notice_id = ?
            """,
            (notice_id,),
        ).fetchone()
        return self._row_to_review_payload(row)

    def export_opportunities_jsonl(self, min_level: str = "review", output_path: Path | None = None) -> Path:
        ensure_data_dirs()
        level_rank = {"excluded": 0, "low": 1, "review": 2, "high": 3}
        min_rank = level_rank[min_level]
        path = output_path or EXPORT_DIR / "spring_opportunities.jsonl"
        rows = self.conn.execute(
            """
            SELECT
                t.*,
                a.is_procurement_notice,
                a.procurement_stage,
                a.has_spring_demand,
                a.demand_type,
                a.procurement_subject,
                a.product_category,
                a.industry_category,
                a.opportunity_level,
                a.relevance_score,
                a.matched_terms_json,
                a.negative_terms_json,
                a.evidence_json,
                a.reason,
                a.assessed_at
            FROM tenders t
            JOIN spring_demand_assessments a ON a.notice_id = t.id
            ORDER BY a.relevance_score DESC, COALESCE(t.publish_time, t.fetched_at) DESC
            """
        ).fetchall()
        with path.open("w", encoding="utf-8") as fp:
            for row in rows:
                if level_rank.get(row["opportunity_level"], 0) < min_rank:
                    continue
                payload = self._row_to_notice_payload(row)
                payload["spring_demand_assessment"] = self._row_to_assessment_payload(row)
                fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path

    def stats(self) -> dict[str, Any]:
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                COUNT(DISTINCT source_platform) AS platform_count,
                MIN(publish_time) AS earliest_publish_time,
                MAX(publish_time) AS latest_publish_time,
                MAX(created_at) AS latest_created_at
            FROM tenders
            """
        ).fetchone()
        by_platform = self.conn.execute(
            """
            SELECT source_platform, COUNT(*) AS count
            FROM tenders
            GROUP BY source_platform
            ORDER BY count DESC
            """
        ).fetchall()
        return {
            **dict(row),
            "by_platform": [dict(item) for item in by_platform],
            "db_path": str(self.db_path),
        }

    def export_jsonl(self, output_path: Path | None = None) -> Path:
        ensure_data_dirs()
        path = output_path or EXPORT_DIR / "tenders.jsonl"
        rows = self.conn.execute(
            """
            SELECT *
            FROM tenders
            ORDER BY COALESCE(publish_time, fetched_at) DESC
            """
        ).fetchall()
        with path.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(json.dumps(self._row_to_notice_payload(row), ensure_ascii=False) + "\n")
        return path

    def sample(self, limit: int = 3) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT title, source_platform, publish_time, platform_url, original_url, substr(content_text, 1, 160) AS content_preview
            FROM tenders
            ORDER BY COALESCE(publish_time, fetched_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _write_raw_html(self, notice: TenderNoticeV1, raw_html: str) -> Path:
        date_part = notice.publish_time.strftime("%Y%m%d") if notice.publish_time else datetime.utcnow().strftime("%Y%m%d")
        directory = RAW_DIR / notice.source_platform / date_part
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{notice.id}.html"
        if not path.exists():
            path.write_text(raw_html, encoding="utf-8")
        return path

    def _row_to_notice_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "source_platform": row["source_platform"],
            "source_channel": row["source_channel"],
            "notice_type": row["notice_type"],
            "title": row["title"],
            "buyer": row["buyer"],
            "agency": row["agency"],
            "publish_time": row["publish_time"],
            "deadline": row["deadline"],
            "bid_open_time": row["bid_open_time"],
            "region": row["region"],
            "industry": row["industry"],
            "platform_url": row["platform_url"],
            "original_url": row["original_url"],
            "attachments": json.loads(row["attachments_json"]),
            "content_text": row["content_text"],
            "raw_fields": json.loads(row["raw_fields_json"]),
            "content_hash": row["content_hash"],
            "fetched_at": row["fetched_at"],
        }

    def _row_to_assessment_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "notice_id": row["id"],
            "is_procurement_notice": bool(row["is_procurement_notice"]),
            "procurement_stage": row["procurement_stage"],
            "has_spring_demand": bool(row["has_spring_demand"]),
            "demand_type": row["demand_type"],
            "procurement_subject": row["procurement_subject"],
            "product_category": row["product_category"],
            "industry_category": row["industry_category"],
            "opportunity_level": row["opportunity_level"],
            "relevance_score": row["relevance_score"],
            "matched_terms": json.loads(row["matched_terms_json"]),
            "negative_terms": json.loads(row["negative_terms_json"]),
            "evidence": json.loads(row["evidence_json"]),
            "reason": row["reason"],
            "assessed_at": row["assessed_at"],
        }

    def _row_to_review_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "notice_id": row["id"],
            "review_status": row["review_status"],
            "review_note": row["review_note"],
            "reviewed_at": row["reviewed_at"],
        }

    def _row_to_attachment_document_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "notice_id": row["notice_id"],
            "attachment_url": row["attachment_url"],
            "attachment_name": row["attachment_name"],
            "file_path": row["file_path"],
            "file_ext": row["file_ext"],
            "status": row["status"],
            "content_text": row["content_text"],
            "content_hash": row["content_hash"],
            "error": row["error"],
            "fetched_at": row["fetched_at"],
            "parsed_at": row["parsed_at"],
        }

    def _row_to_opportunity_summary(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "source_platform": row["source_platform"],
            "notice_type": row["notice_type"],
            "publish_time": row["publish_time"],
            "region": row["region"],
            "buyer": row["buyer"],
            "platform_url": row["platform_url"],
            "original_url": row["original_url"],
            "spring_demand_assessment": {
                "notice_id": row["id"],
                "procurement_stage": row["procurement_stage"],
                "has_spring_demand": bool(row["has_spring_demand"]),
                "demand_type": row["demand_type"],
                "procurement_subject": row["procurement_subject"],
                "product_category": row["product_category"],
                "industry_category": row["industry_category"],
                "opportunity_level": row["opportunity_level"],
                "relevance_score": row["relevance_score"],
                "matched_terms": json.loads(row["matched_terms_json"]),
                "negative_terms": json.loads(row["negative_terms_json"]),
                "evidence": json.loads(row["evidence_json"]),
                "reason": row["reason"],
                "assessed_at": row["assessed_at"],
            },
            "review": self._row_to_review_payload(row),
        }
