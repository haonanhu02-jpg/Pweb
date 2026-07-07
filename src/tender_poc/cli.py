from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from tender_poc.attachments import parse_notice_attachments
from tender_poc.paths import DB_PATH
from tender_poc.screening import assess_notices
from tender_poc.spiders import SPIDERS
from tender_poc.storage import TenderStore


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


app = typer.Typer(help="Tender notice collection POC")
screen_app = typer.Typer(help="Business screening commands")
attachments_app = typer.Typer(help="Attachment download and parsing commands")
app.add_typer(screen_app, name="screen")
app.add_typer(attachments_app, name="attachments")

LEVELS = {"excluded": 0, "low": 1, "review": 2, "high": 3}


@app.command("run")
def run_spider(
    spider_name: str = typer.Argument(..., help="Spider name: ggzy / sdic / cec / crrc"),
    limit: int = typer.Option(20, min=1, max=200, help="Maximum notices to fetch in this run"),
    delay: float = typer.Option(0.5, min=0.0, help="Delay seconds between detail requests"),
) -> None:
    spider_class = SPIDERS.get(spider_name)
    if spider_class is None:
        available = ", ".join(sorted(SPIDERS))
        raise typer.BadParameter(f"Unknown spider: {spider_name}; available: {available}")

    spider = spider_class(delay_seconds=delay)
    result = spider.run(limit=limit)

    store = TenderStore()
    try:
        summary = store.insert_many(result.notices, result.raw_html_by_notice_id)
        summary.failed_count += len(result.failed)
        attachment_summary = parse_notice_attachments(store, result.notices)
        screening_output = _screen_notices(store, result.notices)
        output = {
            "spider": spider.name,
            "requested_limit": limit,
            "fetched_count": len(result.notices),
            "new_count": summary.new_count,
            "duplicate_count": summary.duplicate_count,
            "failed_count": summary.failed_count,
            "failures": result.failed[:10],
            "attachment_parsing": attachment_summary.as_dict(),
            "spring_screening": screening_output,
            "db_path": str(DB_PATH),
        }
        typer.echo(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        store.close()


@app.command("export")
def export(
    format: str = typer.Option("jsonl", "--format", help="Export format; only jsonl is supported"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    if format != "jsonl":
        raise typer.BadParameter("Only jsonl is supported")

    store = TenderStore()
    try:
        path = store.export_jsonl(output)
        typer.echo(str(path))
    finally:
        store.close()


@app.command("export-opportunities")
def export_opportunities(
    format: str = typer.Option("jsonl", "--format", help="Export format; only jsonl is supported"),
    min_level: str = typer.Option("review", "--min-level", help="Minimum level: low / review / high"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    if format != "jsonl":
        raise typer.BadParameter("Only jsonl is supported")
    if min_level not in LEVELS or min_level == "excluded":
        raise typer.BadParameter("min-level must be one of: low, review, high")

    store = TenderStore()
    try:
        path = store.export_opportunities_jsonl(min_level=min_level, output_path=output)
        typer.echo(str(path))
    finally:
        store.close()


@app.command("stats")
def stats() -> None:
    store = TenderStore()
    try:
        typer.echo(json.dumps(store.stats(), ensure_ascii=False, indent=2))
    finally:
        store.close()


@app.command("screen-stats")
def screen_stats() -> None:
    store = TenderStore()
    try:
        typer.echo(json.dumps(store.screen_stats(), ensure_ascii=False, indent=2))
    finally:
        store.close()


@app.command("attachments-stats")
def attachments_stats() -> None:
    store = TenderStore()
    try:
        typer.echo(json.dumps(store.attachment_stats(), ensure_ascii=False, indent=2))
    finally:
        store.close()


@app.command("sample")
def sample(limit: int = typer.Option(3, min=1, max=20, help="Number of sample notices")) -> None:
    store = TenderStore()
    try:
        typer.echo(json.dumps(store.sample(limit), ensure_ascii=False, indent=2))
    finally:
        store.close()


@screen_app.command("spring")
def screen_spring(limit: int = typer.Option(200, min=1, max=5000, help="Maximum notices to screen")) -> None:
    store = TenderStore()
    try:
        notices = store.list_notices(limit=limit)
        output = _screen_notices(store, notices)
        output["requested_limit"] = limit
        typer.echo(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        store.close()


@attachments_app.command("parse")
def parse_attachments(
    limit: int = typer.Option(100, min=1, max=5000, help="Maximum attachments to parse"),
) -> None:
    store = TenderStore()
    try:
        notices = store.list_notices(limit=5000)
        summary = parse_notice_attachments(store, notices, limit=limit)
        output = {
            "requested_limit": limit,
            **summary.as_dict(),
        }
        typer.echo(json.dumps(output, ensure_ascii=False, indent=2))
    finally:
        store.close()


def _screen_notices(store: TenderStore, notices: list) -> dict:
    attachment_texts = store.get_attachment_texts([notice.id for notice in notices])
    assessments = assess_notices(notices, attachment_texts_by_notice_id=attachment_texts)
    summary = store.upsert_assessments(assessments)
    by_level: dict[str, int] = {}
    for assessment in assessments:
        by_level[assessment.opportunity_level] = by_level.get(assessment.opportunity_level, 0) + 1
    return {
        "screened_count": summary.screened_count,
        "failed_count": summary.failed_count,
        "by_level": by_level,
    }
