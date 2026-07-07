from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, UnicodeDammit

from tender_poc.models import TenderNoticeV1


@dataclass(frozen=True)
class ListItem:
    title: str
    url: str
    publish_date_text: str | None = None


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    raw_bytes: bytes

    def soup(self) -> BeautifulSoup:
        return BeautifulSoup(self.text, "html.parser")


@dataclass
class SpiderRunResult:
    notices: list[TenderNoticeV1]
    raw_html_by_notice_id: dict[str, str]
    failed: list[dict[str, str]]


class BaseSpider(ABC):
    name: str
    start_url: str

    def __init__(self, delay_seconds: float = 0.5, timeout_seconds: int = 20) -> None:
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36 tender-poc/0.1"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def fetch(self, url: str) -> FetchResult:
        absolute_url = self.abs_url(url)
        response = self.session.get(absolute_url, timeout=self.timeout_seconds)
        response.raise_for_status()
        dammit = UnicodeDammit(response.content, is_html=True)
        text = dammit.unicode_markup or response.text
        return FetchResult(
            url=response.url,
            status_code=response.status_code,
            text=text,
            raw_bytes=response.content,
        )

    def abs_url(self, url: str) -> str:
        return urljoin(self.start_url, url)

    def run(self, limit: int) -> SpiderRunResult:
        notices: list[TenderNoticeV1] = []
        raw_html_by_notice_id: dict[str, str] = {}
        failed: list[dict[str, str]] = []

        try:
            list_page = self.fetch(self.start_url)
            items = list(self.parse_list(list_page.soup()))
        except Exception as exc:  # noqa: BLE001 - POC should report and keep shape stable.
            return SpiderRunResult(
                notices=[],
                raw_html_by_notice_id={},
                failed=[{"url": self.start_url, "error": repr(exc)}],
            )

        for item in items[:limit]:
            try:
                time.sleep(self.delay_seconds)
                detail_page = self.fetch(item.url)
                notice, raw_html = self.parse_detail(item, detail_page)
                notices.append(notice)
                raw_html_by_notice_id[notice.id] = raw_html
            except Exception as exc:  # noqa: BLE001 - single item failures must not abort the run.
                failed.append({"url": item.url, "title": item.title, "error": repr(exc)})

        return SpiderRunResult(notices=notices, raw_html_by_notice_id=raw_html_by_notice_id, failed=failed)

    @abstractmethod
    def parse_list(self, soup: BeautifulSoup) -> Iterable[ListItem]:
        raise NotImplementedError

    @abstractmethod
    def parse_detail(self, item: ListItem, page: FetchResult) -> tuple[TenderNoticeV1, str]:
        raise NotImplementedError
