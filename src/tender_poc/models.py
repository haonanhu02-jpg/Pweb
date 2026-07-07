from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def make_content_hash(*parts: str | None) -> str:
    payload = "\n".join(normalize_text(part) for part in parts if part)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Attachment(BaseModel):
    name: str
    url: str

    @field_validator("name", "url")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class AttachmentDocumentV1(BaseModel):
    notice_id: str
    attachment_url: str
    attachment_name: str
    file_path: str | None = None
    file_ext: str | None = None
    status: str
    content_text: str = ""
    content_hash: str | None = None
    error: str | None = None
    fetched_at: datetime | None = None
    parsed_at: datetime = Field(default_factory=now_utc)

    @field_validator(
        "notice_id",
        "attachment_url",
        "attachment_name",
        "file_path",
        "file_ext",
        "status",
        "content_text",
        "content_hash",
        "error",
        mode="before",
    )
    @classmethod
    def clean_attachment_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return normalize_text(value)
        return value


class TenderNoticeV1(BaseModel):
    id: str
    source_platform: str
    source_channel: str
    notice_type: str | None = None
    title: str
    buyer: str | None = None
    agency: str | None = None
    publish_time: datetime | None = None
    deadline: datetime | None = None
    bid_open_time: datetime | None = None
    region: str | None = None
    industry: str | None = None
    platform_url: str
    original_url: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    content_text: str
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    content_hash: str
    fetched_at: datetime = Field(default_factory=now_utc)

    @field_validator(
        "source_platform",
        "source_channel",
        "notice_type",
        "title",
        "buyer",
        "agency",
        "region",
        "industry",
        "platform_url",
        "original_url",
        "content_text",
        "content_hash",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return normalize_text(value)
        return value

    @classmethod
    def build_id(cls, source_platform: str, platform_url: str) -> str:
        return make_content_hash(source_platform, platform_url)[:24]

    @classmethod
    def build_hash(cls, title: str, content_text: str, original_url: str | None = None) -> str:
        return make_content_hash(title, content_text, original_url)


class SpringDemandAssessmentV1(BaseModel):
    notice_id: str
    is_procurement_notice: bool
    procurement_stage: str
    has_spring_demand: bool
    demand_type: str | None = None
    procurement_subject: str | None = None
    product_category: str | None = None
    industry_category: str | None = None
    opportunity_level: str
    relevance_score: int
    matched_terms: list[str] = Field(default_factory=list)
    negative_terms: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reason: str
    assessed_at: datetime = Field(default_factory=now_utc)

    @field_validator(
        "notice_id",
        "procurement_stage",
        "demand_type",
        "procurement_subject",
        "product_category",
        "industry_category",
        "opportunity_level",
        "reason",
        mode="before",
    )
    @classmethod
    def clean_assessment_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return normalize_text(value)
        return value
