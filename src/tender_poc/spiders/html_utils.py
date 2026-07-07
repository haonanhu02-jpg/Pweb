from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser

from tender_poc.models import Attachment, normalize_text


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.search(
        r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}(?:日)?(?:\s+\d{1,2}[:：]\d{2}(?:[:：]\d{2})?)?",
        value,
    )
    if not match:
        return None
    cleaned = (
        match.group(0)
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("：", ":")
    )
    try:
        return date_parser.parse(cleaned)
    except (ValueError, TypeError, OverflowError):
        return None


def pick_first(raw_fields: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        value = raw_fields.get(key)
        if value:
            return value
    return None


def parse_date_field(raw_fields: dict[str, str], keys: list[str]) -> datetime | None:
    for key in keys:
        parsed = parse_date(raw_fields.get(key))
        if parsed:
            return parsed
    return None


def extract_attachments(soup: BeautifulSoup, base_url: str) -> list[Attachment]:
    attachments: list[Attachment] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        href = str(link.get("href", "")).strip()
        name = normalize_text(link.get_text(" ", strip=True))
        if not href or not name:
            continue
        lower = href.lower()
        looks_like_file = any(
            lower.endswith(ext)
            for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar"]
        )
        if not looks_like_file and "附件" not in name:
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        attachments.append(Attachment(name=name, url=url))
    return attachments


def extract_table_fields(soup: BeautifulSoup) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in soup.select("table tr"):
        cells = [cell for cell in row.find_all(["th", "td"], recursive=False) if isinstance(cell, Tag)]
        if len(cells) < 2:
            cells = [cell for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)]
        if len(cells) < 2:
            continue
        key = normalize_key(cells[0].get_text(" ", strip=True))
        value = normalize_text(cells[1].get_text(" ", strip=True))
        if key and value:
            fields[key] = value
    return fields


def normalize_key(value: str) -> str:
    return normalize_text(value).rstrip(":：")


def extract_label_value_pairs(soup: BeautifulSoup, item_selector: str = ".dg-flex-item") -> dict[str, str]:
    fields: dict[str, str] = {}
    for node in soup.select(".dg-flex"):
        children = [
            child
            for child in node.find_all(recursive=False)
            if isinstance(child, Tag) and child.select_one(item_selector) is None
        ]
        if len(children) >= 2:
            _add_pair(fields, children[0], children[1])

        direct_items = [
            child
            for child in node.find_all(recursive=False)
            if isinstance(child, Tag) and item_selector.replace(".", "") in child.get("class", [])
        ]
        if len(direct_items) >= 2:
            _add_pair(fields, direct_items[0], direct_items[1])

    return fields


def _add_pair(fields: dict[str, str], key_node: Tag, value_node: Tag) -> None:
    raw_key = normalize_text(key_node.get_text(" ", strip=True))
    if not raw_key.endswith((":", "：")):
        return
    key = normalize_key(raw_key)
    value = normalize_text(value_node.get_text(" ", strip=True))
    if key and value:
        fields[key] = value
