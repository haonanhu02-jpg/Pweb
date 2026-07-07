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
from tender_poc.spiders.html_utils import extract_attachments, extract_table_fields, parse_date


@dataclass(frozen=True)
class CrrcSource:
    company: str
    site_code: str
    list_url: str
    region: str
    business_tag: str


CRRC_SOURCES = [
    CrrcSource("中车大连机车车辆有限公司", "dl", "https://www.crrcgc.cc/dl/138_8399/138_8417/index.html", "辽宁大连", "机车车辆"),
    CrrcSource("中车太原机车车辆有限公司", "ty", "https://www.crrcgc.cc/ty/145_8993/145_9515/index.html", "山西太原", "机车车辆检修"),
    CrrcSource("中车永济电机有限公司", "yjdj", "https://www.crrcgc.cc/yjdj/147_9199/147_9269/index.html", "山西永济", "牵引电机"),
    CrrcSource("中车西安车辆有限公司", "xa", "https://www.crrcgc.cc/xa/134_8018/134_8038/index.html", "陕西西安", "车辆检修"),
    CrrcSource("中车戚墅堰机车有限公司", "qsy", "https://www.crrcgc.cc/qsy/24_1035/24_10299/index.html", "江苏常州", "机车检修"),
    CrrcSource("中车天津机车车辆有限公司", "tj", "https://www.crrcgc.cc/tj/151_9547/151_9617/index.html", "天津", "机车车辆检修"),
    CrrcSource("中车大连电力牵引研发中心有限公司", "dldq", "https://www.crrcgc.cc/dldq/126_7499/126_7572/index.html", "辽宁大连", "电力牵引"),
    CrrcSource("中车山东风电有限公司", "zcfd", "https://www.crrcgc.cc/zcfd/246_16921/246_16939/index.html", "山东济南", "风电装备"),
    CrrcSource("中车石家庄车辆有限公司", "sjz", "https://www.crrcgc.cc/sjz/42_2423/42_2486/index.html", "河北石家庄", "车辆检修"),
    CrrcSource("中车大同电力机车有限公司", "dt", "https://www.crrcgc.cc/dt/137_8247/137_8265/index.html", "山西大同", "电力机车"),
    CrrcSource("中车北京南口机械有限公司", "nk", "https://www.crrcgc.cc/nk/139_8476/139_18560/index.html", "北京", "机械装备"),
    CrrcSource("中车工程技术有限公司", "gc", "https://www.crrcgc.cc/gc/150_9434/150_18051/index.html", "北京", "工程技术"),
]


class CrrcSpider(BaseSpider):
    name = "crrc"
    start_url = "https://www.crrcgc.cc/"
    sources = CRRC_SOURCES
    list_urls = [source.list_url for source in sources]
    source_platform = "中国中车公开采购公告"
    source_channel = "央企集团官网/自有采购公开公告"

    def run(self, limit: int) -> SpiderRunResult:
        notices: list[TenderNoticeV1] = []
        raw_html_by_notice_id: dict[str, str] = {}
        failed: list[dict[str, str]] = []
        items: list[ListItem] = []
        item_groups: list[list[ListItem]] = []
        seen: set[str] = set()

        for source in self.sources:
            try:
                list_page = self.fetch(source.list_url)
                group: list[ListItem] = []
                for item in self.parse_list(list_page.soup()):
                    if item.url in seen:
                        continue
                    seen.add(item.url)
                    group.append(item)
                item_groups.append(group)
            except Exception as exc:  # noqa: BLE001 - one list page should not abort the spider.
                failed.append({"url": source.list_url, "company": source.company, "error": repr(exc)})

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
        for link in soup.select('a[href*="/article_"][href$=".html"]'):
            href = str(link.get("href", "")).strip()
            title = normalize_text(link.get("title") or link.get_text(" ", strip=True))
            if not href or not title or not _is_procurement_related(title):
                continue
            url = urljoin(self.start_url, href)
            publish_date = self._date_from_url(url)
            yield ListItem(title=title, url=url, publish_date_text=publish_date)

    def parse_detail(self, item: ListItem, page: FetchResult) -> tuple[TenderNoticeV1, str]:
        soup = page.soup()
        meta = self._extract_meta(soup)
        title = meta.get("ArticleTitle") or self._extract_title(soup) or item.title
        content_node = soup.select_one(".detail-content") or soup.select_one(".Gnews-detail") or soup.body or soup
        content_text = normalize_text(content_node.get_text(" ", strip=True))
        source = self._source_for_url(page.url) or self._source_for_url(item.url)
        raw_fields = {
            **extract_table_fields(content_node),
            "crrc_company": source.company if source else None,
            "crrc_region": source.region if source else None,
            "crrc_business_tag": source.business_tag if source else None,
            "crrc_list_url": source.list_url if source else None,
            "site_name": meta.get("SiteName"),
            "column_name": meta.get("ColumnName"),
            "pub_date": meta.get("PubDate"),
            "keywords": meta.get("Keywords"),
            "author": meta.get("Author"),
            "content_source": meta.get("ContentSource"),
            "article_url": meta.get("Url"),
        }
        raw_fields = {key: value for key, value in raw_fields.items() if value}
        publish_time = parse_date(meta.get("PubDate")) or parse_date(meta.get("createDate")) or parse_date(item.publish_date_text)
        platform_url = page.url

        notice = TenderNoticeV1(
            id=TenderNoticeV1.build_id(self.source_platform, platform_url),
            source_platform=self.source_platform,
            source_channel=self.source_channel,
            notice_type=self._infer_notice_type(title, meta.get("ColumnName")),
            title=title,
            buyer=meta.get("SiteName") or (source.company if source else None),
            agency=None,
            publish_time=publish_time,
            deadline=self._find_date_after(content_text, ["截止", "报名截止", "投标截止", "响应文件递交"]),
            bid_open_time=self._find_date_after(content_text, ["开标时间", "谈判时间", "评审时间"]),
            region=(source.region if source else None) or self._infer_region(meta.get("SiteName"), platform_url),
            industry=source.business_tag if source else "轨道交通装备",
            platform_url=platform_url,
            original_url=platform_url,
            attachments=extract_attachments(soup, page.url),
            content_text=content_text,
            raw_fields=raw_fields,
            content_hash=TenderNoticeV1.build_hash(title, content_text, platform_url),
        )
        return notice, page.text

    def _extract_meta(self, soup: BeautifulSoup) -> dict[str, str]:
        fields: dict[str, str] = {}
        for node in soup.select("meta[name][content]"):
            name = str(node.get("name", "")).strip()
            content = normalize_text(str(node.get("content", "")))
            if name and content:
                fields[name] = content
        return fields

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        for selector in [".detail-titles", "h1", "h2"]:
            node = soup.select_one(selector)
            if node:
                title = normalize_text(node.get_text(" ", strip=True))
                if title:
                    return title
        if soup.title:
            return normalize_text(soup.title.get_text(" ", strip=True))
        return None

    def _date_from_url(self, url: str) -> str | None:
        match = re.search(r"/(\d{4})-(\d{2})/(\d{2})/", url)
        if not match:
            return None
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"

    def _infer_notice_type(self, title: str, column_name: str | None) -> str | None:
        for keyword in [
            "招标公告",
            "竞标公告",
            "公开竞标公告",
            "谈判采购",
            "寻源公告",
            "采购公告",
            "直接采购公示",
            "中标候选人公示",
            "中标结果公示",
            "中标公告",
            "竞标结果公示",
            "成交候选人公示",
            "成交公告",
            "结果公示",
            "废标公告",
        ]:
            if keyword in title:
                return keyword
        return column_name

    def _source_for_url(self, url: str) -> CrrcSource | None:
        for source in self.sources:
            if f"/{source.site_code}/" in url or url.rstrip("/") == source.list_url.rstrip("/"):
                return source
        return None

    def _infer_region(self, site_name: str | None, url: str) -> str | None:
        text = " ".join(value for value in [site_name, url] if value)
        if "大连" in text or "/dl/" in text:
            return "辽宁大连"
        if "太原" in text or "/ty/" in text:
            return "山西太原"
        return None

    def _find_date_after(self, content_text: str, labels: list[str]) -> datetime | None:
        for label in labels:
            index = content_text.find(label)
            if index < 0:
                continue
            parsed = parse_date(content_text[index : index + 120])
            if parsed:
                return parsed
        return None


def _is_procurement_related(title: str) -> bool:
    include_terms = ["采购", "招标", "谈判", "寻源", "中标", "成交", "废标", "比选", "竞标", "询价", "询比", "公示"]
    return any(term in title for term in include_terms)
