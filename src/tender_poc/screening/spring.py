from __future__ import annotations

from collections.abc import Iterable, Mapping

from tender_poc.models import SpringDemandAssessmentV1, TenderNoticeV1, normalize_text


OPEN_PROCUREMENT_TERMS = [
    "采购",
    "招标",
    "投标",
    "谈判采购",
    "公开寻源",
    "寻源公告",
    "报名",
    "招标公告",
    "采购公告",
    "询价",
    "竞争性谈判",
    "竞争性磋商",
    "比选",
    "竞价",
    "框架协议",
    "征集",
    "招标项目",
    "采购项目",
    "投标人应",
    "供应商应",
    "获取招标文件",
    "获取采购文件",
]

RESULT_TERMS = ["中标", "成交", "候选人", "结果公告", "结果公示", "成交公告", "中标公告"]
ASSET_TERMS = ["资产出租", "资产转让", "挂牌", "拍卖", "产权交易", "房屋出租", "土地使用权"]
ENGINEERING_TERMS = ["施工", "装修", "建设工程", "工程总承包", "EPC", "监理", "设计", "勘察", "改造工程"]

DIRECT_SPRING_TERMS = [
    "弹簧采购",
    "采购弹簧",
    "弹簧类",
    "弹簧及",
    "弹簧组件",
    "弹簧总成",
    "弹簧备件",
    "压缩弹簧",
    "拉伸弹簧",
    "扭簧",
    "碟簧",
    "板簧",
    "螺旋弹簧",
    "涡卷弹簧",
    "恒力弹簧",
    "异形弹簧",
    "弹性元件",
    "弹性件",
    "弹簧片",
    "弹簧垫圈",
    "弹簧支吊架",
    "转向架弹簧",
    "阀门弹簧",
    "断路器弹簧",
    "弹簧机构",
    "悬挂弹簧",
    "空气弹簧",
    "橡胶弹簧",
    "钢弹簧",
    "一系弹簧",
    "二系弹簧",
    "轴箱弹簧",
    "枕簧",
    "旁承弹簧",
    "减振弹簧",
    "弹簧减振",
    "弹簧减震",
    "弹簧悬挂",
    "弹簧垫",
    "弹簧座",
    "弹簧支吊架",
    "支吊架弹簧",
    "弹性支吊架",
    "阻尼弹簧",
    "液压支架弹簧",
]

GENERAL_SPRING_TERMS = [
    "弹簧",
    "碟簧",
    "板簧",
    "扭簧",
    "弹性元件",
    "弹性件",
    "弹簧机构",
    "橡胶弹簧",
    "空气弹簧",
    "钢弹簧",
    "弹簧支吊架",
    "弹性支吊架",
]
COMPONENT_CONTEXT_TERMS = [
    "采购",
    "询价",
    "招标",
    "供货",
    "供应",
    "备件",
    "配件",
    "检修配件",
    "机车检修配件",
    "阀类件检修",
    "支吊架",
    "阀门",
    "泵",
    "输送机",
    "液压支架",
    "矿用",
    "机务",
    "检修物资",
    "零部件",
    "组件",
    "总成",
    "物资",
    "材料",
    "年度",
    "框架",
    "入围",
]
STRUCTURE_ONLY_TERMS = ["结构", "装置", "系统", "整机", "设备", "维保", "检修", "维修", "改造", "工程", "施工"]

HARD_NEGATIVE_TERMS = [
    "Spring Boot",
    "Spring Cloud",
    "spring boot",
    "spring cloud",
    "Spring框架",
    "弹簧床垫",
    "床垫",
    "沙发",
    "玩具",
    "办公椅",
    "文具",
]

IT_NEGATIVE_TERMS = ["软件", "信息化", "运维", "系统建设", "服务器", "数据库", "网络安全"]

SUBJECT_FIELD_HINTS = [
    "项目名称",
    "采购内容",
    "采购范围",
    "招标范围",
    "标段名称",
    "标包名称",
    "包件名称",
    "物资名称",
    "货物名称",
    "主要标的",
    "项目概况",
]

INDUSTRY_RULES = [
    (
        ["转向架", "轨道", "车辆", "机车", "动车", "铁路", "地铁", "受电弓", "悬挂", "减振", "减震", "架修", "厂修", "客修"],
        "轨道交通弹簧",
        "轨道交通",
    ),
    (["断路器", "隔离开关", "开关柜", "电力", "电网", "变电", "互感器"], "电力设备弹簧", "电力设备"),
    (["阀门", "石化", "炼化", "油田", "化工", "中石油", "中石化"], "石油化工阀门弹簧", "石油化工"),
    (["火电", "电厂", "锅炉", "汽轮机", "磨煤机", "弹簧支吊架", "支吊架", "机务"], "电厂机务弹簧/弹性支吊架", "电力能源"),
    (["煤矿", "矿山", "重工", "振动筛", "破碎机", "输送", "输送机", "皮带机", "液压支架", "托辊"], "矿山/重工设备弹簧", "矿山重工"),
    (["船舶", "舰船", "海工", "船用"], "船舶/军工装备弹簧", "船舶装备"),
    (["垫圈", "紧固件"], "通用紧固件/弹性件", "通用工业"),
]


RESULT_TERMS += ["中标", "成交", "候选人", "结果公告", "结果公示"]


def assess_notices(
    notices: Iterable[TenderNoticeV1],
    attachment_texts_by_notice_id: Mapping[str, list[str]] | None = None,
) -> list[SpringDemandAssessmentV1]:
    attachment_texts_by_notice_id = attachment_texts_by_notice_id or {}
    return [
        assess_notice(notice, attachment_texts=attachment_texts_by_notice_id.get(notice.id, []))
        for notice in notices
    ]


def assess_notice(notice: TenderNoticeV1, attachment_texts: list[str] | None = None) -> SpringDemandAssessmentV1:
    title_text = normalize_text(notice.title)
    raw_subject_text = _build_subject_text(notice)
    attachment_name_text = " ".join(attachment.name for attachment in notice.attachments)
    parsed_attachment_text = normalize_text(" ".join(attachment_texts or []))
    body_text = normalize_text(notice.content_text)
    subject_text = normalize_text(" ".join([title_text, raw_subject_text, attachment_name_text]))
    full_text = normalize_text(" ".join([subject_text, body_text, parsed_attachment_text]))

    stage, is_procurement_notice = _detect_stage(title_text, full_text)
    negative_terms = _find_terms(full_text, HARD_NEGATIVE_TERMS + IT_NEGATIVE_TERMS)
    hard_negative_terms = _find_terms(full_text, HARD_NEGATIVE_TERMS)

    direct_subject_terms = _find_terms(subject_text, DIRECT_SPRING_TERMS)
    direct_body_terms = _find_terms(body_text, DIRECT_SPRING_TERMS)
    direct_attachment_terms = _find_terms(parsed_attachment_text, DIRECT_SPRING_TERMS)
    general_subject_terms = _find_terms(subject_text, GENERAL_SPRING_TERMS)
    general_body_terms = _find_terms(body_text, GENERAL_SPRING_TERMS)
    general_attachment_terms = _find_terms(parsed_attachment_text, GENERAL_SPRING_TERMS)
    context_terms = _find_terms(full_text, COMPONENT_CONTEXT_TERMS)
    structure_terms = _find_terms(full_text, STRUCTURE_ONLY_TERMS)
    matched_terms = _unique(
        direct_subject_terms
        + direct_body_terms
        + direct_attachment_terms
        + general_subject_terms
        + general_body_terms
        + general_attachment_terms
        + context_terms
    )

    product_category, industry_category, industry_terms = _classify_industry(full_text)
    evidence: list[str] = []
    score = 0

    if stage == "open":
        score += 20
        evidence.append("公告阶段为采购/询价/招标中")
    elif stage == "result":
        score += 5
        evidence.append("公告阶段为中标/成交结果，不是开放投标机会")
    elif stage == "engineering":
        score += 5
        evidence.append("公告阶段偏工程/施工类，需要判断是否单独采购弹簧部件")
    elif stage == "asset_transfer":
        score -= 40
        evidence.append("公告阶段为资产出租/转让，通常不是采购机会")

    if direct_subject_terms:
        score += 55
        evidence.append(f"标题或采购标的命中强需求词：{', '.join(direct_subject_terms)}")
    if direct_body_terms:
        score += 35
        evidence.append(f"正文命中强需求词：{', '.join(direct_body_terms)}")
    if direct_attachment_terms:
        score += 35
        evidence.append(f"附件正文命中强需求词：{', '.join(direct_attachment_terms)}")
    if general_subject_terms and not direct_subject_terms:
        score += 40
        evidence.append(f"标题或采购标的命中弹簧相关词：{', '.join(general_subject_terms)}")
    if general_body_terms and not direct_body_terms:
        score += 20
        evidence.append(f"正文命中弹簧相关词：{', '.join(general_body_terms)}")
    if general_attachment_terms and not direct_attachment_terms:
        score += 20
        evidence.append(f"附件正文命中弹簧相关词：{', '.join(general_attachment_terms)}")
    if context_terms and (
        direct_subject_terms
        or direct_body_terms
        or direct_attachment_terms
        or general_subject_terms
        or general_body_terms
        or general_attachment_terms
    ):
        score += 15
        evidence.append(f"同时命中采购/备件语境：{', '.join(context_terms[:6])}")
    if industry_terms:
        score += 10
        evidence.append(f"命中目标行业场景：{', '.join(industry_terms)}")
    if negative_terms:
        score -= 50 if hard_negative_terms else 20
        evidence.append(f"命中负向词：{', '.join(negative_terms)}")

    demand_type = _detect_demand_type(
        direct_subject_terms=direct_subject_terms,
        direct_body_terms=_unique(direct_body_terms + direct_attachment_terms),
        general_subject_terms=general_subject_terms,
        general_body_terms=_unique(general_body_terms + general_attachment_terms),
        context_terms=context_terms,
        structure_terms=structure_terms,
    )

    has_spring_demand = demand_type in {"直接弹簧采购", "弹簧零部件/备件采购"}
    if hard_negative_terms:
        has_spring_demand = False
        demand_type = None
    if stage == "asset_transfer":
        has_spring_demand = False

    score = max(0, min(score, 100))
    opportunity_level = _level_for(
        score=score,
        stage=stage,
        demand_type=demand_type,
        has_spring_demand=has_spring_demand,
        hard_negative=bool(hard_negative_terms),
    )

    if not evidence:
        evidence.append("未发现弹簧采购需求证据")

    reason = _build_reason(opportunity_level, demand_type, stage, has_spring_demand, matched_terms, negative_terms)

    return SpringDemandAssessmentV1(
        notice_id=notice.id,
        is_procurement_notice=is_procurement_notice,
        procurement_stage=stage,
        has_spring_demand=has_spring_demand,
        demand_type=demand_type,
        procurement_subject=_best_subject(notice, raw_subject_text),
        product_category=product_category if has_spring_demand or opportunity_level == "review" else None,
        industry_category=industry_category if has_spring_demand or opportunity_level == "review" else None,
        opportunity_level=opportunity_level,
        relevance_score=score,
        matched_terms=matched_terms,
        negative_terms=negative_terms,
        evidence=evidence,
        reason=reason,
    )


def _build_subject_text(notice: TenderNoticeV1) -> str:
    parts: list[str] = []
    for key, value in notice.raw_fields.items():
        key_text = str(key)
        if any(hint in key_text for hint in SUBJECT_FIELD_HINTS):
            parts.append(str(value))
    return normalize_text(" ".join(parts))


def _best_subject(notice: TenderNoticeV1, raw_subject_text: str) -> str:
    raw_subject_text = normalize_text(raw_subject_text)
    if raw_subject_text and raw_subject_text != normalize_text(notice.title):
        return raw_subject_text[:300]
    return normalize_text(notice.title)[:300]


def _detect_stage(title_text: str, full_text: str) -> tuple[str, bool]:
    stage_source = " ".join([title_text, full_text[:1000]])
    if _contains_any(stage_source, ASSET_TERMS):
        return "asset_transfer", False
    if _contains_any(stage_source, RESULT_TERMS):
        return "result", True
    if _contains_any(stage_source, ENGINEERING_TERMS):
        return "engineering", True
    if _contains_any(stage_source, OPEN_PROCUREMENT_TERMS):
        return "open", True
    return "unknown", False


def _detect_demand_type(
    *,
    direct_subject_terms: list[str],
    direct_body_terms: list[str],
    general_subject_terms: list[str],
    general_body_terms: list[str],
    context_terms: list[str],
    structure_terms: list[str],
) -> str | None:
    if direct_subject_terms:
        return "直接弹簧采购"
    if direct_body_terms and context_terms:
        return "弹簧零部件/备件采购"
    if general_subject_terms and context_terms:
        return "弹簧零部件/备件采购"
    if general_body_terms and structure_terms:
        return "结构描述疑似"
    if general_body_terms and context_terms:
        return "弹簧零部件/备件采购"
    return None


def _level_for(
    *,
    score: int,
    stage: str,
    demand_type: str | None,
    has_spring_demand: bool,
    hard_negative: bool,
) -> str:
    if hard_negative or stage == "asset_transfer":
        return "excluded"
    if demand_type == "结构描述疑似":
        return "review"
    if not has_spring_demand:
        return "excluded" if score < 35 else "low"
    if stage == "result":
        return "low"
    if stage == "engineering":
        return "review"
    if stage == "open" and score >= 80:
        return "high"
    if score >= 50:
        return "review"
    return "low"


def _classify_industry(text: str) -> tuple[str, str, list[str]]:
    for terms, product_category, industry_category in INDUSTRY_RULES:
        matched = _find_terms(text, terms)
        if matched:
            return product_category, industry_category, matched
    return "通用弹簧/弹性件", "通用工业", []


def _find_terms(text: str, terms: Iterable[str]) -> list[str]:
    if not text:
        return []
    lower_text = text.lower()
    matched: list[str] = []
    for term in terms:
        if term.lower() in lower_text:
            matched.append(term)
    return _unique(matched)


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    return bool(_find_terms(text, terms))


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _build_reason(
    opportunity_level: str,
    demand_type: str | None,
    stage: str,
    has_spring_demand: bool,
    matched_terms: list[str],
    negative_terms: list[str],
) -> str:
    if negative_terms and opportunity_level == "excluded":
        return f"命中负向词（{', '.join(negative_terms)}），排除为非目标弹簧采购需求"
    if opportunity_level == "high":
        return f"开放采购公告中识别到{demand_type}，建议优先跟进"
    if opportunity_level == "review":
        if demand_type == "结构描述疑似":
            return "公告仅在设备/结构描述中出现弹簧相关内容，需人工确认是否单独采购弹簧零部件"
        return f"识别到弹簧相关采购线索（{', '.join(matched_terms[:6])}），需人工复核"
    if has_spring_demand and stage == "result":
        return "识别到弹簧采购需求线索，但公告为中标/成交结果，不是开放投标机会"
    if has_spring_demand:
        return "识别到弹簧相关采购需求，但开放性或标的信息不足"
    return "未识别到可销售的弹簧/弹簧组件/相关备件采购需求"
