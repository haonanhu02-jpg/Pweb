from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tender_poc.screening import assess_notices
from tender_poc.storage import TenderStore


ReviewStatus = Literal["pending_review", "relevant", "invalid", "viewed"]
OpportunityLevel = Literal["excluded", "low", "review", "high"]


class ReviewUpdate(BaseModel):
    review_status: ReviewStatus
    review_note: str = Field(default="", max_length=1000)


app = FastAPI(title="Tender POC Opportunity API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard() -> dict:
    store = TenderStore()
    try:
        return store.dashboard()
    finally:
        store.close()


@app.get("/api/opportunities")
def opportunities(
    min_level: OpportunityLevel = Query("review"),
    opportunity_level: OpportunityLevel | None = None,
    review_status: ReviewStatus | None = None,
    platform: str | None = None,
    procurement_stage: str | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    store = TenderStore()
    try:
        return store.list_opportunities(
            min_level=min_level,
            opportunity_level=opportunity_level,
            review_status=review_status,
            platform=platform,
            procurement_stage=procurement_stage,
            q=q,
            limit=limit,
            offset=offset,
        )
    finally:
        store.close()


@app.get("/api/opportunities/{notice_id}")
def opportunity_detail(notice_id: str) -> dict:
    store = TenderStore()
    try:
        payload = store.get_opportunity(notice_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        return payload
    finally:
        store.close()


@app.patch("/api/opportunities/{notice_id}/review")
def update_review(notice_id: str, body: ReviewUpdate) -> dict:
    store = TenderStore()
    try:
        if store.get_opportunity(notice_id) is None:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        return store.upsert_review(
            notice_id=notice_id,
            review_status=body.review_status,
            review_note=body.review_note,
        )
    finally:
        store.close()


@app.post("/api/screen/spring")
def screen_spring(limit: int = Query(5000, ge=1, le=10000)) -> dict:
    store = TenderStore()
    try:
        notices = store.list_notices(limit=limit)
        attachment_texts = store.get_attachment_texts([notice.id for notice in notices])
        assessments = assess_notices(notices, attachment_texts_by_notice_id=attachment_texts)
        summary = store.upsert_assessments(assessments)
        by_level: dict[str, int] = {}
        for assessment in assessments:
            by_level[assessment.opportunity_level] = by_level.get(assessment.opportunity_level, 0) + 1
        return {
            "requested_limit": limit,
            "screened_count": summary.screened_count,
            "failed_count": summary.failed_count,
            "by_level": by_level,
        }
    finally:
        store.close()
