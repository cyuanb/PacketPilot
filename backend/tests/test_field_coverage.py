import pytest
from app.domain import check_one, verify_evidence
from test_domain import doc, rule


@pytest.mark.parametrize(
    "kind,parameters,first,second",
    [
        ("field_consistency", {"field": "姓名"}, "姓名：李沐\n姓名：李沐", "课程：数据库"),
        ("required_field", {"field": "姓名"}, "姓名：李沐", "课程：数据库"),
        (
            "date_constraint",
            {"field": "有效期", "not_before": "2026-12-01"},
            "有效期：2026-12-01\n有效期：2026-12-01",
            "课程：数据库",
        ),
    ],
)
def test_values_in_one_document_do_not_cover_another(kind, parameters, first, second):
    documents = [doc("成绩单\n" + first), doc("成绩单\n" + second, id="d2")]
    finding = check_one(rule(kind, parameters=parameters), documents, {})
    assert finding["verdict"] == "unknown"
    assert [(c["document_id"], c["status"]) for c in finding["field_coverage"]] == [
        ("d1", "covered"),
        ("d2", "missing"),
    ]
    verify_evidence(finding["evidence"], documents)


@pytest.mark.parametrize(
    "kind,parameters",
    [
        ("field_consistency", {"field": "姓名"}),
        ("required_field", {"field": "姓名"}),
        ("date_constraint", {"field": "有效期", "not_before": "2026-12-01"}),
    ],
)
def test_unreadable_matched_document_is_not_dropped(kind, parameters):
    finding = check_one(
        rule(kind, parameters=parameters),
        [
            doc("成绩单\n姓名：李沐\n有效期：2026-12-01"),
            doc("", id="d2", category="成绩单", parse_status="needs_review"),
        ],
        {},
    )
    assert finding["verdict"] != "pass"
    assert finding["field_coverage"][1]["status"] == "unreadable"


@pytest.mark.parametrize("text", ["姓名：\n课程：数据库", "推荐人姓名：李沐", "姓名：____", "姓名：待填写"])
def test_empty_placeholder_or_other_role_does_not_cover_field(text):
    finding = check_one(rule("required_field", parameters={"field": "姓名"}), [doc("成绩单\n" + text)], {})
    assert finding["verdict"] == "unknown"
    assert finding["field_coverage"][0]["status"] == "missing"


def test_duplicate_values_in_each_complete_document_are_allowed():
    finding = check_one(
        rule("field_consistency", parameters={"field": "姓名"}),
        [doc("成绩单\n姓名：李沐\n姓名：李沐"), doc(id="d2")],
        {},
    )
    assert finding["verdict"] == "pass"
    assert all(c["status"] == "covered" for c in finding["field_coverage"])


def test_multiple_values_in_one_document_need_subject_review():
    finding = check_one(
        rule("field_consistency", parameters={"field": "姓名"}),
        [doc("成绩单\n姓名：李沐\n姓名：林沐"), doc(id="d2")],
        {},
    )
    assert finding["verdict"] == "unknown"
    assert finding["field_coverage"][0]["status"] == "ambiguous"


@pytest.mark.parametrize("value", ["2026-12-01（未经确认）", "2026-12-01x", "2026-02-30", "12/01/2026"])
def test_unvalidated_date_is_not_silently_accepted(value):
    finding = check_one(
        rule("date_constraint", parameters={"field": "有效期", "not_before": "2026-01-01"}),
        [doc("成绩单\n有效期：" + value)],
        {},
    )
    assert finding["verdict"] == "unknown"
    assert finding["field_coverage"][0]["status"] == "invalid"


def test_covered_dates_and_exact_boundary_pass_with_evidence():
    documents = [doc("成绩单\n有效期：2026-12-01"), doc("成绩单\n有效期：2026-12-02", id="d2")]
    finding = check_one(
        rule("date_constraint", parameters={"field": "有效期", "not_before": "2026-12-01"}), documents, {}
    )
    assert finding["verdict"] == "pass"
    assert {e["document_id"] for e in finding["evidence"]} == {"d1", "d2"}
    verify_evidence(finding["evidence"], documents)
