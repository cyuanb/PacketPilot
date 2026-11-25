import pytest
from app.domain import check_one, verify_evidence
from test_domain import doc, rule


@pytest.mark.parametrize(
    "text",
    [
        "材料补交通知：请补交成绩单。",
        "材料清单\n1. 成绩单\n2. 申请表\n姓名：李沐\n平均绩点：3.6",
        "成绩单填写说明\n姓名：李沐\n平均绩点：3.6",
        "成绩单模板\n姓名：张三\n平均绩点：3.6",
        "成绩单\n姓名：____\n平均绩点：待填写",
        "成绩单",
        "成绩单\n姓名：李沐",
        "成绩单\n姓名：请填写您的姓名\n平均绩点：请填写平均绩点",
    ],
)
def test_mentions_templates_or_heading_alone_never_pass(text):
    finding = check_one(rule(), [doc(text)], {})
    assert finding["verdict"] == "unknown"
    assert finding["material_matches"][0]["status"] == "unverified"


@pytest.mark.parametrize(
    "title,text",
    [
        ("成绩单", "成绩单\n姓名：李沐\n平均绩点：3.6"),
        ("申请表", "申请表\n姓名：李沐\n申请类别：本科交流"),
        ("入职登记表", "入职登记表\n姓名：李沐\n入职日期：2026-12-01"),
        ("营业执照", "营业执照\n名称：青禾演示公司\n统一社会信用代码：SYNTHETIC-001"),
    ],
)
def test_supported_material_requires_heading_and_substantive_fields(title, text):
    document = doc(text)
    finding = check_one(rule(document_type=title), [document], {})
    assert finding["verdict"] == "pass"
    assert finding["material_matches"][0]["status"] == "verified"
    verify_evidence(finding["evidence"], [document])


def test_unknown_document_type_is_not_guessed():
    finding = check_one(rule(document_type="特殊证明"), [doc("特殊证明\n编号：123\n姓名：李沐")], {})
    assert finding["verdict"] == "unknown"


def test_presence_can_be_satisfied_by_one_verified_document():
    documents = [doc("请提供成绩单"), doc("成绩单\n姓名：李沐\n平均绩点：3.6", id="d2")]
    finding = check_one(rule(), documents, {})
    assert finding["verdict"] == "pass"
    assert {e["document_id"] for e in finding["evidence"]} == {"d2"}


def test_unreadable_title_or_category_is_not_a_match_confirmation():
    finding = check_one(rule(), [doc("", category="成绩单", parse_status="failed")], {})
    assert finding["verdict"] == "unknown"
    assert finding["material_matches"][0]["status"] == "unreadable"
