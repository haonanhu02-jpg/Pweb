from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from tender_poc.models import TenderNoticeV1, normalize_text
from tender_poc.spiders.base import BaseSpider, FetchResult, ListItem, SpiderRunResult
from tender_poc.spiders.html_utils import extract_attachments, extract_table_fields, parse_date, pick_first


@dataclass(frozen=True)
class ChnEnergySource:
    category_code: str
    list_url: str
    notice_type: str
    business_tag: str
    max_pages: int = 3


CHNENERGY_SOURCES = [
    ChnEnergySource(
        "001002001",
        "https://www.chnenergybidding.com.cn/bidweb/001/001002/001002001/moreinfo.html",
        "招标公告-货物",
        "能源设备物资",
    ),
    ChnEnergySource(
        "001003",
        "https://www.chnenergybidding.com.cn/bidweb/001/001003/moreinfo.html",
        "非招标公告",
        "自采/竞价采购",
    ),
    ChnEnergySource(
        "001002002",
        "https://www.chnenergybidding.com.cn/bidweb/001/001002/001002002/moreinfo.html",
        "招标公告-工程",
        "电厂/煤矿工程",
    ),
    ChnEnergySource(
        "001002003",
        "https://www.chnenergybidding.com.cn/bidweb/001/001002/001002003/moreinfo.html",
        "招标公告-服务",
        "检修/服务",
    ),
    ChnEnergySource(
        "001001001",
        "https://www.chnenergybidding.com.cn/bidweb/001/001001/001001001/moreinfo.html",
        "资格预审公告-货物",
        "供应商资格预审",
    ),
    ChnEnergySource(
        "001005001",
        "https://www.chnenergybidding.com.cn/bidweb/001/001005/001005001/moreinfo.html",
        "候选人公示-货物",
        "能源设备物资",
    ),
    ChnEnergySource(
        "001006001",
        "https://www.chnenergybidding.com.cn/bidweb/001/001006/001006001/moreinfo.html",
        "中标公告-货物",
        "能源设备物资",
    ),
]


class ChnEnergySpider(BaseSpider):
    name = "chnenergy"
    start_url = "https://www.chnenergybidding.com.cn/bidweb/"
    sources = CHNENERGY_SOURCES
    source_platform = "国家能源集团国能e招"
    source_channel = "央企集团自有电子采购平台/公开公告"

    def run(self, limit: int) -> SpiderRunResult:
        notices: list[TenderNoticeV1] = []
        raw_html_by_notice_id: dict[str, str] = {}
        failed: list[dict[str, str]] = []
        items: list[ListItem] = []
        item_groups: list[list[ListItem]] = []
        seen: set[str] = set()

        for source in self.sources:
            group: list[ListItem] = []
            for page_no in range(1, source.max_pages + 1):
                try:
                    list_url = self._page_url(source, page_no)
                    list_page = self.fetch(list_url)
                    page_items = list(self.parse_list(list_page.soup()))
                    if not page_items:
                        break
                    for item in page_items:
                        if item.url in seen:
                            continue
                        seen.add(item.url)
                        group.append(item)
                except Exception as exc:  # noqa: BLE001 - one list page should not abort the spider.
                    failed.append({"url": self._page_url(source, page_no), "category": source.notice_type, "error": repr(exc)})
                    break
            item_groups.append(group)

        max_group_size = max((len(group) for group in item_groups), default=0)
        for index in range(max_group_size):
            for group in item_groups:
                if index < len(group):
                    items.append(group[index])

        for item in items:
            if len(notices) >= limit:
                break
            try:
                time.sleep(self.delay_seconds)
                detail_page = self.fetch(item.url)
                notice, raw_html = self.parse_detail(item, detail_page)
                notices.append(notice)
                raw_html_by_notice_id[notice.id] = raw_html
            except Exception as exc:  # noqa: BLE001 - single item failures must not abort the run.
                failed.append({"url": item.url, "title": item.title, "error": repr(exc)})

        return SpiderRunResult(notices=notices, raw_html_by_notice_id=raw_html_by_notice_id, failed=failed)

    def parse_list(self, soup: BeautifulSoup) -> Iterable[ListItem]:
        seen: set[str] = set()
        for link in soup.select("a.infolink[href]"):
            href = str(link.get("href", "")).strip()
            title = normalize_text(link.get("title") or link.get_text(" ", strip=True))
            if not href or not title or not href.endswith(".html"):
                continue
            url = urljoin(self.start_url, href)
            if url in seen or "/bidweb/001/" not in url:
                continue
            seen.add(url)
            publish_date = self._date_from_url(url) or self._date_from_list_item(link)
            yield ListItem(title=title, url=url, publish_date_text=publish_date)

    def parse_detail(self, item: ListItem, page: FetchResult) -> tuple[TenderNoticeV1, str]:
        soup = page.soup()
        source = self._source_for_url(page.url)
        title = self._extract_title(soup) or item.title
        article_node = soup.select_one(".article") or soup.body or soup
        content_node = soup.select_one(".article .con") or article_node
        content_text = normalize_text(content_node.get_text(" ", strip=True))
        raw_fields = {
            **extract_table_fields(content_node),
            **self._extract_label_fields(content_text),
            "chnenergy_category": source.notice_type if source else None,
            "chnenergy_business_tag": source.business_tag if source else None,
            "chnenergy_category_code": source.category_code if source else None,
            "chnenergy_list_url": source.list_url if source else None,
            "info_id": self._input_value(soup, "infoid"),
            "project_code": self._input_value(soup, "zbnum"),
            "breadcrumb": self._breadcrumb(soup),
            "publish_source_text": self._publish_source_text(soup),
        }
        raw_fields = {key: value for key, value in raw_fields.items() if value}
        publish_time = self._extract_publish_time(soup, item.publish_date_text)
        platform_url = page.url

        notice = TenderNoticeV1(
            id=TenderNoticeV1.build_id(self.source_platform, platform_url),
            source_platform=self.source_platform,
            source_channel=self.source_channel,
            notice_type=self._infer_notice_type(title, source),
            title=title,
            buyer=pick_first(raw_fields, ["招标人", "采购人", "项目单位"]),
            agency=pick_first(raw_fields, ["招标机构", "招标代理机构", "代理机构", "采购代理机构"]),
            publish_time=publish_time,
            deadline=self._find_date_after(content_text, ["投标截止时间", "递交截止时间", "响应文件递交截止", "报价截止", "文件领购结束时间"]),
            bid_open_time=self._find_date_after(content_text, ["开标时间", "投标截止时间", "评审时间"]),
            region=pick_first(raw_fields, ["项目实施地点", "交货地点", "项目地点"]),
            industry=source.business_tag if source else "能源设备物资",
            platform_url=platform_url,
            original_url=platform_url,
            attachments=extract_attachments(soup, page.url),
            content_text=content_text,
            raw_fields=raw_fields,
            content_hash=TenderNoticeV1.build_hash(title, content_text, platform_url),
        )
        return notice, page.text

    def _page_url(self, source: ChnEnergySource, page_no: int) -> str:
        if page_no <= 1:
            return source.list_url
        return source.list_url.replace("/moreinfo.html", f"/{page_no}.html")

    def _source_for_url(self, url: str) -> ChnEnergySource | None:
        candidates = sorted(self.sources, key=lambda item: len(item.category_code), reverse=True)
        for source in candidates:
            if f"/{source.category_code}/" in url or url.rstrip("/") == source.list_url.rstrip("/"):
                return source
        return None

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        node = soup.select_one("h1#title") or soup.select_one("h1")
        return normalize_text(node.get_text(" ", strip=True)) if node else None

    def _extract_publish_time(self, soup: BeautifulSoup, list_date_text: str | None) -> datetime | None:
        source_text = self._publish_source_text(soup)
        return parse_date(source_text) or self._parse_loose_date(source_text) or parse_date(list_date_text)

    def _publish_source_text(self, soup: BeautifulSoup) -> str | None:
        node = soup.select_one(".info-sources")
        return normalize_text(node.get_text(" ", strip=True)) if node else None

    def _input_value(self, soup: BeautifulSoup, node_id: str) -> str | None:
        node = soup.select_one(f"#{node_id}")
        if not node:
            return None
        return normalize_text(str(node.get("value") or node.get_text(" ", strip=True)))

    def _breadcrumb(self, soup: BeautifulSoup) -> str | None:
        node = soup.select_one(".right-local")
        return normalize_text(node.get_text(" ", strip=True)) if node else None

    def _date_from_url(self, url: str) -> str | None:
        match = re.search(r"/(\d{4})(\d{2})(\d{2})/", url)
        if not match:
            return None
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"

    def _date_from_list_item(self, link) -> str | None:
        item_node = link.find_parent("li") or link.find_parent(class_="tab2-item")
        if not item_node:
            return None
        date_node = item_node.select_one("span.r")
        return normalize_text(date_node.get_text(" ", strip=True)) if date_node else None

    def _infer_notice_type(self, title: str, source: ChnEnergySource | None) -> str | None:
        for keyword in [
            "招标公告",
            "资格预审公告",
            "非招标公告",
            "竞价采购",
            "询价采购",
            "候选人公示",
            "中标结果公告",
            "中标公告",
            "终止公告",
            "变更公告",
        ]:
            if keyword in title:
                return keyword
        return source.notice_type if source else None

    def _extract_label_fields(self, content_text: str) -> dict[str, str]:
        labels = [
            "日期",
            "招标编号",
            "项目编号",
            "项目名称",
            "招标人",
            "采购人",
            "项目单位",
            "招标机构",
            "招标代理机构",
            "代理机构",
            "采购代理机构",
            "项目实施地点",
            "交货地点",
            "项目地点",
            "招标文件领购开始时间",
            "招标文件领购结束时间",
            "投标截止时间",
            "开标时间",
        ]
        fields: dict[str, str] = {}
        for index, label in enumerate(labels):
            next_labels = labels[index + 1 :]
            pattern = rf"{re.escape(label)}\s*[:：]\s*(.+?)"
            if next_labels:
                lookahead = "|".join(re.escape(next_label) + r"\s*[:：]" for next_label in next_labels)
                pattern += rf"(?=\s*(?:{lookahead})|$)"
            else:
                pattern += r"$"
            match = re.search(pattern, content_text)
            if match:
                value = normalize_text(match.group(1))[:500]
                if value:
                    fields[label] = value
        return fields

    def _find_date_after(self, content_text: str, labels: list[str]) -> datetime | None:
        for label in labels:
            index = content_text.find(label)
            if index < 0:
                continue
            snippet = content_text[index : index + 180]
            parsed = parse_date(snippet) or self._parse_loose_date(snippet)
            if parsed:
                return parsed
        return None

    def _parse_loose_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        match = re.search(
            r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日(?:\s*(上午|下午)?\s*(\d{1,2})\s*[:：]\s*(\d{1,2}))?",
            value,
        )
        if not match:
            return None
        year, month, day, meridiem, hour, minute = match.groups()
        hour_value = int(hour or 0)
        if meridiem == "下午" and hour_value < 12:
            hour_value += 12
        try:
            return datetime(int(year), int(month), int(day), hour_value, int(minute or 0))
        except ValueError:
            return None
