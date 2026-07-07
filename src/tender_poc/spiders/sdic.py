from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlencode

from bs4 import BeautifulSoup, Tag

from tender_poc.models import TenderNoticeV1, normalize_text
from tender_poc.spiders.base import BaseSpider, FetchResult, ListItem
from tender_poc.spiders.html_utils import (
    extract_attachments,
    extract_label_value_pairs,
    parse_date,
    parse_date_field,
    pick_first,
)


class SdicSpider(BaseSpider):
    name = "sdic"
    start_url = "https://www.sdicc.com.cn/cgxx/ggList"
    source_platform = "国投集团电子采购平台"
    source_channel = "央企集团自有电子采购平台"

    def parse_list(self, soup: BeautifulSoup) -> Iterable[ListItem]:
        seen: set[str] = set()
        for row in soup.select(".tbody tr[onclick]"):
            onclick = str(row.get("onclick", ""))
            match = re.search(r"urlChange\('([^']+)','([^']+)'\)", onclick)
            if not match:
                continue
            gg_guid, gc_guid = match.groups()
            cells = [cell for cell in row.find_all("td", recursive=False) if isinstance(cell, Tag)]
            if len(cells) < 4:
                continue
            title = normalize_text(cells[1].get_text(" ", strip=True))
            notice_kind = normalize_text(cells[2].get_text(" ", strip=True))
            publish_date = normalize_text(cells[3].get_text(" ", strip=True))
            detail_url = self.abs_url("/cgxx/ggDetail?" + urlencode({"ggGuid": gg_guid, "gcGuid": gc_guid}))
            if detail_url in seen:
                continue
            seen.add(detail_url)
            yield ListItem(
                title=title,
                url=detail_url,
                publish_date_text=f"{publish_date} {notice_kind}".strip(),
            )

    def parse_detail(self, item: ListItem, page: FetchResult) -> tuple[TenderNoticeV1, str]:
        soup = page.soup()
        title = self._extract_title(soup) or item.title
        detail_node = soup.select_one(".dg-notice-detail") or soup.body or soup
        content_text = normalize_text(detail_node.get_text(" ", strip=True))
        raw_fields = extract_label_value_pairs(soup)
        publish_time = self._extract_publish_time(soup, raw_fields, item.publish_date_text)
        notice_type = self._extract_notice_type(soup, raw_fields, item.publish_date_text)
        platform_url = page.url

        notice = TenderNoticeV1(
            id=TenderNoticeV1.build_id(self.source_platform, platform_url),
            source_platform=self.source_platform,
            source_channel=self.source_channel,
            notice_type=notice_type,
            title=title,
            buyer=pick_first(raw_fields, ["招标人", "采购人"]),
            agency=pick_first(raw_fields, ["代理机构", "采购代理机构", "招标代理机构"]),
            publish_time=publish_time,
            deadline=parse_date_field(raw_fields, ["文件获取截止时间", "投标截止时间", "截止时间"]),
            bid_open_time=parse_date_field(raw_fields, ["截标/开标时间", "开标时间"]),
            region=pick_first(raw_fields, ["项目实施地点", "项目所在地", "交货地点"]),
            industry=pick_first(raw_fields, ["所属行业分类", "项目类型"]),
            platform_url=platform_url,
            original_url=platform_url,
            attachments=extract_attachments(soup, page.url),
            content_text=content_text,
            raw_fields=raw_fields,
            content_hash=TenderNoticeV1.build_hash(title, content_text, platform_url),
        )
        return notice, page.text

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        node = soup.select_one(".dg-notice-title")
        return normalize_text(node.get_text(" ", strip=True)) if node else None

    def _extract_publish_time(
        self,
        soup: BeautifulSoup,
        raw_fields: dict[str, str],
        list_date_text: str | None,
    ):
        parsed = parse_date_field(raw_fields, ["发布时间", "发布日期"])
        if parsed:
            return parsed
        state_text = normalize_text(" ".join(node.get_text(" ", strip=True) for node in soup.select(".dg-notice-state-item")))
        return parse_date(state_text) or parse_date(list_date_text)

    def _extract_notice_type(
        self,
        soup: BeautifulSoup,
        raw_fields: dict[str, str],
        list_date_text: str | None,
    ) -> str | None:
        for key in ["采购方式", "项目类型"]:
            if raw_fields.get(key):
                return raw_fields[key]
        if list_date_text:
            parts = list_date_text.split()
            if len(parts) > 1:
                return parts[-1]
        location = soup.select_one(".dg-head-default")
        return normalize_text(location.get_text(" ", strip=True)) if location else None
