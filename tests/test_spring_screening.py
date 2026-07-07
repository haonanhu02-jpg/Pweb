from __future__ import annotations

import unittest

from tender_poc.models import TenderNoticeV1
from tender_poc.screening.spring import assess_notice


def make_notice(title: str, content: str, raw_fields: dict | None = None) -> TenderNoticeV1:
    url = "https://example.test/" + TenderNoticeV1.build_id("test", title)
    return TenderNoticeV1(
        id=TenderNoticeV1.build_id("test", url),
        source_platform="test",
        source_channel="test",
        notice_type="采购公告",
        title=title,
        platform_url=url,
        original_url=url,
        attachments=[],
        content_text=content,
        raw_fields=raw_fields or {},
        content_hash=TenderNoticeV1.build_hash(title, content, url),
    )


class SpringScreeningTests(unittest.TestCase):
    def test_direct_bogie_spring_purchase_is_high(self) -> None:
        notice = make_notice(
            "车辆段转向架弹簧采购公告",
            "采购内容：转向架弹簧组件一批。供应商应按招标文件要求投标。",
            {"采购内容": "转向架弹簧组件"},
        )

        assessment = assess_notice(notice)

        self.assertEqual(assessment.opportunity_level, "high")
        self.assertTrue(assessment.has_spring_demand)
        self.assertEqual(assessment.product_category, "轨道交通弹簧")

    def test_breaker_spring_mechanism_spares_inquiry_is_high(self) -> None:
        notice = make_notice(
            "断路器弹簧操作机构备件询价公告",
            "本次询价采购断路器弹簧操作机构配件，用于变电站检修。",
        )

        assessment = assess_notice(notice)

        self.assertEqual(assessment.opportunity_level, "high")
        self.assertTrue(assessment.has_spring_demand)
        self.assertEqual(assessment.product_category, "电力设备弹簧")

    def test_crrc_air_spring_maintenance_parts_purchase_is_high(self) -> None:
        notice = make_notice(
            "中车天津公司空气弹簧检修配件采购公告",
            "本项目采购机车检修配件，包含空气弹簧、橡胶弹簧等车辆悬挂系统备件。",
            {"采购内容": "空气弹簧、橡胶弹簧等车辆悬挂系统备件"},
        )

        assessment = assess_notice(notice)

        self.assertEqual(assessment.opportunity_level, "high")
        self.assertTrue(assessment.has_spring_demand)
        self.assertEqual(assessment.product_category, "轨道交通弹簧")

    def test_power_plant_spring_hanger_purchase_is_high(self) -> None:
        notice = make_notice(
            "火电厂锅炉弹簧支吊架采购公告",
            "采购内容：锅炉管道弹簧支吊架、弹性支吊架备件一批，供应商应按招标文件要求投标。",
            {"采购内容": "锅炉管道弹簧支吊架、弹性支吊架备件"},
        )

        assessment = assess_notice(notice)

        self.assertEqual(assessment.opportunity_level, "high")
        self.assertTrue(assessment.has_spring_demand)
        self.assertEqual(assessment.product_category, "电厂机务弹簧/弹性支吊架")

    def test_valve_structure_only_spring_reference_is_review(self) -> None:
        notice = make_notice(
            "阀门采购公告",
            "采购阀门一批，技术要求：阀门采用弹簧复位结构。",
        )

        assessment = assess_notice(notice)

        self.assertEqual(assessment.opportunity_level, "review")
        self.assertFalse(assessment.has_spring_demand)
        self.assertEqual(assessment.demand_type, "结构描述疑似")

    def test_spring_purchase_result_is_not_open_high_opportunity(self) -> None:
        notice = make_notice(
            "弹簧采购中标结果公示",
            "弹簧采购项目已完成评审，现发布中标结果。",
        )

        assessment = assess_notice(notice)

        self.assertTrue(assessment.has_spring_demand)
        self.assertEqual(assessment.procurement_stage, "result")
        self.assertNotEqual(assessment.opportunity_level, "high")

    def test_it_and_mattress_false_positives_are_excluded(self) -> None:
        cases = [
            make_notice("Spring Boot系统建设采购公告", "采购Spring Boot后台管理系统开发服务。"),
            make_notice("弹簧床垫采购公告", "采购宿舍弹簧床垫一批。"),
        ]

        for notice in cases:
            with self.subTest(title=notice.title):
                assessment = assess_notice(notice)
                self.assertEqual(assessment.opportunity_level, "excluded")
                self.assertFalse(assessment.has_spring_demand)


    def test_attachment_text_can_create_high_opportunity(self) -> None:
        notice = make_notice(
            "轨道交通配件谈判采购公告",
            "采购内容详见附件项目明细表。",
        )

        assessment = assess_notice(notice, attachment_texts=["转向架弹簧采购 转向架弹簧组件 采购"])

        self.assertEqual(assessment.opportunity_level, "high")
        self.assertTrue(assessment.has_spring_demand)
        self.assertTrue(any("附件正文" in item for item in assessment.evidence))

    def test_attachment_structure_only_reference_is_review(self) -> None:
        notice = make_notice(
            "阀门采购公告",
            "采购阀门一批，技术参数详见附件。",
        )

        assessment = assess_notice(notice, attachment_texts=["阀门采用弹簧复位结构"])

        self.assertEqual(assessment.opportunity_level, "review")
        self.assertFalse(assessment.has_spring_demand)


if __name__ == "__main__":
    unittest.main()
