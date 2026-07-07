from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup, Tag

from tender_poc.models import TenderNoticeV1, normalize_text
from tender_poc.spiders.base import BaseSpider, FetchResult, ListItem
from tender_poc.spiders.html_utils import extract_attachments, parse_date, pick_first


class CecSpider(BaseSpider):
    name = "cec"
    start_url = "https://www.cec-ec.com.cn/cms/channel/1xmgg0/index.htm"
    source_platform = "CEC电子采购平台"
    source_channel = "央企集团自有电子采购平台"

    def parse_list(self, soup: BeautifulSoup) -> Iterable[ListItem]:
        seen: set[str] = set()
        for link in soup.select('li[name="li_name"] a[href]'):
            href = str(link.get("href", "")).strip()
            title = normalize_text(link.get("title") or link.get_text(" ", strip=True))
            if not href or not title:
                continue
            url = self.abs_url(href)
            if url in seen:
                continue
            seen.add(url)
            li = link.find_parent("li")
            date_node = li.find("em") if li else None
            publish_date_text = normalize_text(date_node.get_text(" ", strip=True)) if date_node else None
            yield ListItem(title=title, url=url, publish_date_text=publish_date_text)

    def parse_detail(self, item: ListItem, page: FetchResult) -> tuple[TenderNoticeV1, str]:
        soup = page.soup()
        title = self._extract_title(soup) or item.title
        content_node = soup.select_one(".article-content") or soup.body or soup
        main_text_node = soup.select_one(".main-text") or content_node
        content_text = normalize_text(main_text_node.get_text(" ", strip=True))
        raw_fields = self._extract_raw_fields(soup)
        publish_time = self._extract_publish_time(soup, item.publish_date_text)
        notice_type = self._extract_notice_type(soup, title)
        platform_url = page.url

        notice = TenderNoticeV1(
            id=TenderNoticeV1.build_id(self.source_platform, platform_url),
            source_platform=self.source_platform,
            source_channel=self.source_channel,
            notice_type=notice_type,
            title=title,
            buyer=pick_first(raw_fields, ["招标人", "采购人", "比选人", "询价人"]),
            agency=pick_first(raw_fields, ["代理机构", "招标代理机构", "采购代理机构"]),
            publish_time=publish_time,
            deadline=self._find_date_after(content_text, ["投标截止", "递交投标文件截止", "响应文件递交截止"]),
            bid_open_time=self._find_date_after(content_text, ["开标时间", "投标截止"]),
            region=pick_first(raw_fields, ["地址", "项目地点", "交付地点"]),
            industry=None,
            platform_url=platform_url,
            original_url=platform_url,
            attachments=extract_attachments(soup, page.url),
            content_text=content_text,
            raw_fields=raw_fields,
            content_hash=TenderNoticeV1.build_hash(title, content_text, platform_url),
        )
        return notice, page.text

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        node = soup.select_one(".article-title")
        return normalize_text(node.get_text(" ", strip=True)) if node else None

    def _extract_publish_time(self, soup: BeautifulSoup, list_date_text: str | None):
        author_text = normalize_text(" ".join(node.get_text(" ", strip=True) for node in soup.select(".article-author")))
        return parse_date(author_text) or parse_date(list_date_text)

    def _extract_notice_type(self, soup: BeautifulSoup, title: str) -> str | None:
        location = soup.select_one(".location")
        if location:
            links = [normalize_text(a.get_text(" ", strip=True)) for a in location.select("a")]
            for value in reversed(links):
                if value and value not in {"采购信息"}:
                    return value
        for keyword in ["招标公告", "采购公告", "中标候选人公示", "中标公示", "中标公告", "变更公告"]:
            if keyword in title:
                return keyword
        return None

    def _extract_raw_fields(self, soup: BeautifulSoup) -> dict[str, str]:
        fields: dict[str, str] = {}
        main_text = soup.select_one(".main-text") or soup
        chunks = [normalize_text(value) for value in main_text.stripped_strings if normalize_text(value)]
        for label in ["工程名称", "项目名称", "招标人", "采购人", "地址", "联系人", "联系电话"]:
            value = self._find_text_after_label(chunks, label)
            if value:
                fields[label] = value
        location = soup.select_one(".location")
        if location:
            fields["栏目路径"] = normalize_text(location.get_text(" ", strip=True))
        return fields

    def _find_text_after_label(self, chunks: list[str], label: str) -> str | None:
        stop_labels = [
            "招标人",
            "采购人",
            "联系人",
            "联系方式",
            "联系电话",
            "联系邮箱",
            "地址",
            "项目编号",
            "项目名称",
            "工程名称",
            "公示周期",
            "公示时间",
        ]
        for chunk in chunks:
            match = re.search(rf"{re.escape(label)}[:：]\s*(.+)", chunk)
            if not match:
                continue
            value = normalize_text(match.group(1))
            for stop_label in stop_labels:
                if stop_label == label:
                    continue
                value = re.split(rf"\s*{re.escape(stop_label)}[:：]", value, maxsplit=1)[0]
            value = re.split(r"[。；;]", value, maxsplit=1)[0]
            value = normalize_text(value)
            if value:
                return value
        return None

    def _find_date_after(self, content_text: str, labels: list[str]):
        for label in labels:
            index = content_text.find(label)
            if index < 0:
                continue
            parsed = parse_date(content_text[index : index + 80])
            if parsed:
                return parsed
        return None
