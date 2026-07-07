from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from dateutil import parser as date_parser

from tender_poc.models import Attachment, TenderNoticeV1, normalize_text
from tender_poc.spiders.base import BaseSpider, FetchResult, ListItem


class GgzySpider(BaseSpider):
    name = "ggzy"
    start_url = "https://www.ggzy.gov.cn/"
    source_platform = "全国公共资源交易平台"
    source_channel = "全国及各省市公共资源交易平台"

    def parse_list(self, soup: BeautifulSoup) -> Iterable[ListItem]:
        seen: set[str] = set()
        for link in soup.select('a[href*="/information/deal/html/a/"]'):
            href = link.get("href")
            title = normalize_text(link.get_text(" ", strip=True))
            if not href or not title:
                continue
            url = self.abs_url(str(href))
            if url in seen:
                continue
            seen.add(url)
            li = link.find_parent("li")
            publish_date_text = None
            if li:
                date_node = li.find("span")
                if date_node:
                    publish_date_text = normalize_text(date_node.get_text(" ", strip=True))
            yield ListItem(title=title, url=url, publish_date_text=publish_date_text)

    def parse_detail(self, item: ListItem, page: FetchResult) -> tuple[TenderNoticeV1, str]:
        outer_soup = page.soup()
        content_url = self._find_content_url(outer_soup, page.url)
        content_page = self.fetch(content_url)
        content_soup = content_page.soup()

        title = self._extract_title(content_soup) or self._extract_title(outer_soup) or item.title
        content_text = self._extract_content_text(content_soup)
        raw_fields = self._extract_table_fields(content_soup)
        info_source = self._extract_info_source(content_soup)
        original_url = self._extract_original_url(content_soup)
        attachments = self._extract_attachments(content_soup, content_page.url)
        publish_time = self._extract_publish_time(content_soup, raw_fields, item.publish_date_text)

        buyer = self._pick_first(raw_fields, ["采购人", "招标人", "转让方名称", "出让方", "项目法人"])
        agency = self._pick_first(raw_fields, ["代理机构", "招标代理机构", "采购代理机构"])
        notice_type = self._infer_notice_type(content_soup, raw_fields)
        region = self._infer_region(content_page.url, raw_fields)
        industry = self._infer_industry(content_soup, raw_fields)

        platform_url = content_page.url
        content_hash = TenderNoticeV1.build_hash(title, content_text, original_url)
        notice = TenderNoticeV1(
            id=TenderNoticeV1.build_id(self.source_platform, platform_url),
            source_platform=self.source_platform,
            source_channel=self.source_channel,
            notice_type=notice_type,
            title=title,
            buyer=buyer,
            agency=agency,
            publish_time=publish_time,
            deadline=self._parse_date_field(raw_fields, ["报名截止时间", "投标截止时间", "截止时间"]),
            bid_open_time=self._parse_date_field(raw_fields, ["开标时间"]),
            region=region,
            industry=industry,
            platform_url=platform_url,
            original_url=original_url,
            attachments=attachments,
            content_text=content_text,
            raw_fields={
                **raw_fields,
                "outer_url": page.url,
                "content_url": content_page.url,
                "info_source": info_source,
            },
            content_hash=content_hash,
        )
        return notice, content_page.text

    def _find_content_url(self, soup: BeautifulSoup, outer_url: str) -> str:
        script_text = "\n".join(script.get_text("\n", strip=False) for script in soup.find_all("script"))
        match = re.search(r"firstLastUrl\s*=\s*['\"]([^'\"]+)['\"]", script_text)
        if match:
            return urljoin(outer_url, match.group(1))

        detail_link = soup.select_one('a[onclick*="/information/deal/html/b/"]')
        if detail_link:
            onclick = detail_link.get("onclick", "")
            match = re.search(r"(/information/deal/html/b/[^'\"]+\.html)", onclick)
            if match:
                return urljoin(outer_url, match.group(1))

        if "/html/a/" in outer_url:
            return outer_url.replace("/html/a/", "/html/b/")
        return outer_url

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        node = soup.select_one("h4.h4_o")
        if node:
            return normalize_text(node.get_text(" ", strip=True))
        if soup.title:
            return normalize_text(soup.title.get_text(" ", strip=True).split("_")[0])
        return None

    def _extract_info_source(self, soup: BeautifulSoup) -> str | None:
        label = soup.select_one("#platformName")
        if label:
            return normalize_text(label.get_text(" ", strip=True))
        text = normalize_text(soup.get_text(" ", strip=True))
        match = re.search(r"信息来源[:：]\s*([^ ]+)", text)
        return match.group(1) if match else None

    def _extract_original_url(self, soup: BeautifulSoup) -> str | None:
        link = soup.select_one("a[href][target='_blank']")
        if link and "原文" in normalize_text(link.get_text(" ", strip=True)):
            return str(link["href"]).strip()
        for candidate in soup.select("a[href]"):
            text = normalize_text(candidate.get_text(" ", strip=True))
            if "原文" in text or "链接地址" in text:
                return str(candidate["href"]).strip()
        return None

    def _extract_content_text(self, soup: BeautifulSoup) -> str:
        node = soup.select_one("#mycontent") or soup.select_one(".detail") or soup.body or soup
        return normalize_text(node.get_text(" ", strip=True))

    def _extract_table_fields(self, soup: BeautifulSoup) -> dict[str, str]:
        fields: dict[str, str] = {}
        for row in soup.select("table tr"):
            cells = [cell for cell in row.find_all(["th", "td"]) if isinstance(cell, Tag)]
            if len(cells) < 2:
                continue
            key = normalize_text(cells[0].get_text(" ", strip=True)).rstrip(":：")
            value = normalize_text(cells[1].get_text(" ", strip=True))
            if key and value:
                fields[key] = value
        return fields

    def _extract_attachments(self, soup: BeautifulSoup, base_url: str) -> list[Attachment]:
        attachments: list[Attachment] = []
        seen: set[str] = set()
        for link in soup.select("a[href]"):
            href = str(link.get("href", "")).strip()
            name = normalize_text(link.get_text(" ", strip=True))
            if not href or not name:
                continue
            lower = href.lower()
            looks_like_file = any(lower.endswith(ext) for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar"])
            if not looks_like_file and "附件" not in name:
                continue
            url = urljoin(base_url, href)
            if url in seen:
                continue
            seen.add(url)
            attachments.append(Attachment(name=name, url=url))
        return attachments

    def _extract_publish_time(
        self,
        soup: BeautifulSoup,
        raw_fields: dict[str, str],
        list_date_text: str | None,
    ) -> datetime | None:
        parsed = self._parse_date_field(raw_fields, ["发布时间", "发布日期", "挂牌日期", "公告日期"])
        if parsed:
            return parsed
        text = normalize_text(soup.get_text(" ", strip=True))
        for pattern in [r"发布时间[:：]\s*(\d{4}-\d{1,2}-\d{1,2})", r"挂牌日期[:：]\s*(\d{4}-\d{1,2}-\d{1,2})"]:
            match = re.search(pattern, text)
            if match:
                return self._parse_date(match.group(1))
        return self._parse_date(list_date_text)

    def _parse_date_field(self, raw_fields: dict[str, str], keys: list[str]) -> datetime | None:
        for key in keys:
            value = raw_fields.get(key)
            parsed = self._parse_date(value)
            if parsed:
                return parsed
        return None

    def _parse_date(self, value: str | None) -> datetime | None:
        if not value:
            return None
        match = re.search(r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}(?:日)?(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", value)
        if not match:
            return None
        cleaned = match.group(0).replace("年", "-").replace("月", "-").replace("日", "")
        try:
            return date_parser.parse(cleaned)
        except (ValueError, TypeError, OverflowError):
            return None

    def _pick_first(self, raw_fields: dict[str, str], keys: list[str]) -> str | None:
        for key in keys:
            if raw_fields.get(key):
                return raw_fields[key]
        return None

    def _infer_notice_type(self, soup: BeautifulSoup, raw_fields: dict[str, str]) -> str | None:
        if raw_fields.get("交易方式"):
            return raw_fields["交易方式"]
        location = soup.select_one(".location")
        if location:
            parts = [part.strip() for part in normalize_text(location.get_text(">", strip=True)).split(">") if part.strip()]
            if parts:
                return parts[-1]
        return None

    def _infer_region(self, url: str, raw_fields: dict[str, str]) -> str | None:
        for key in ["行政区域", "项目所在地区", "转让标的所在地区", "地区"]:
            if raw_fields.get(key):
                return raw_fields[key]
        match = re.search(r"/html/b/(\d{6})/", url)
        return match.group(1) if match else None

    def _infer_industry(self, soup: BeautifulSoup, raw_fields: dict[str, str]) -> str | None:
        for key in ["资产类别", "行业分类", "项目类型", "品目"]:
            if raw_fields.get(key):
                return raw_fields[key]
        location = soup.select_one(".location")
        if location:
            parts = [part.strip() for part in normalize_text(location.get_text(">", strip=True)).split(">") if part.strip()]
            if parts:
                return parts[-1]
        return None
