import pytest
from app.domain import check_one, condition_value, overall, verify_evidence


def rule(kind="material_presence", **kwargs):
    return {
        "id": "r1",
        "title": "成绩单",
        "kind": kind,
        "document_type": "成绩单",
        "required": True,
        "condition": {},
        "parameters": {},
        "source_evidence": [{"document_id": "notice", "page": 1, "quote": "提供成绩单"}],
        **kwargs,
    }


def doc(text="成绩单\n姓名：李沐", **kwargs):
    return {
        "id": "d1",
        "purpose": "material",
        "category": "",
        "filename": "成绩单.txt",
        "mime": "text/plain",
        "size": 100,
        "parse_status": "ready",
        "pages": [{"number": 1, "text": text}],
        **kwargs,
    }


@pytest.mark.parametrize(
    "condition,facts,expected",
    [
        ({}, {}, True),
        ({"field": "类别", "value": "本科"}, {}, None),
        ({"field": "类别", "value": "本科"}, {"类别": "本科"}, True),
        ({"field": "类别", "value": "本科"}, {"类别": "硕士"}, False),
        ({"all": [{"field": "x", "value": 1}, {"field": "y", "value": 2}]}, {"x": 0}, False),
        ({"any": [{"field": "x", "value": 1}, {"field": "y", "value": 2}]}, {"x": 0}, None),
        ({"field": "x", "op": "in", "value": [1, 2]}, {"x": 1}, True),
        ({"field": "x", "op": "execute"}, {"x": 1}, None),
    ],
)
def test_conditions(condition, facts, expected):
    assert condition_value(condition, facts) is expected


def test_missing_material_has_inventory_dependency():
    f = check_one(rule(), [], {})
    assert f["verdict"] == "missing"
    assert "material_inventory" in f["dependencies"]


def test_file_name_is_not_evidence():
    assert check_one(rule(), [doc("购物清单\n苹果：2个")], {})["verdict"] == "missing"


def test_unreadable_candidate_is_unknown_not_missing():
    assert check_one(rule(), [doc("", parse_status="needs_review")], {})["verdict"] == "unknown"


def test_confirmed_category_without_content_cannot_pass():
    assert check_one(rule(), [doc("没有明确材料类别", category="成绩单")], {})["verdict"] == "unknown"


def test_presence_quotes_actual_document():
    f = check_one(rule(), [doc()], {})
    assert f["verdict"] == "pass"
    verify_evidence(f["evidence"], [doc()], "material")


def test_unknown_condition_never_passes():
    f = check_one(rule(condition={"field": "类别", "value": "本科"}), [doc()], {})
    assert f["applicability"] == "unknown" and f["verdict"] == "unknown"


def test_conflicting_names_exposes_both_sources():
    f = check_one(
        rule("field_consistency", parameters={"field": "姓名"}),
        [doc(), doc("成绩单\n姓名：林沐", id="d2")],
        {},
    )
    assert f["verdict"] == "conflict"
    assert {e["document_id"] for e in f["evidence"]} == {"d1", "d2"}


def test_consistency_requires_two_materials():
    assert (
        check_one(rule("field_consistency", parameters={"field": "姓名"}), [doc()], {})["verdict"]
        == "unknown"
    )


@pytest.mark.parametrize(
    "kind,parameters,document,expected",
    [
        ("file_format", {"allowed": ["pdf"]}, doc(), "fail"),
        ("file_size", {"max_bytes": 100}, doc(), "pass"),
        ("file_size", {"max_bytes": 99}, doc(), "fail"),
        ("page_count", {"max_pages": 1}, doc(), "unknown"),
        ("page_count", {"max_pages": 1}, doc(mime="application/pdf"), "pass"),
        (
            "date_constraint",
            {"field": "有效期", "not_before": "2026-12-01"},
            doc("成绩单\n有效期：2026-12-01"),
            "pass",
        ),
        (
            "date_constraint",
            {"field": "有效期", "not_before": "2026-12-01"},
            doc("成绩单\n有效期：2026-11-30"),
            "fail",
        ),
        (
            "date_constraint",
            {"field": "有效期", "not_before": "2026-12-01"},
            doc("成绩单\n有效期：12-01"),
            "unknown",
        ),
        ("manual_review", {}, doc(), "unknown"),
    ],
)
def test_deterministic_checks(kind, parameters, document, expected):
    assert check_one(rule(kind, parameters=parameters), [document], {})["verdict"] == expected


def test_citation_is_bound_to_version_page_and_quote():
    with pytest.raises(ValueError):
        verify_evidence([{"document_id": "d1", "page": 2, "quote": "成绩单"}], [doc()])
    with pytest.raises(ValueError):
        verify_evidence([{"document_id": "other", "page": 1, "quote": "成绩单"}], [doc()])
    with pytest.raises(ValueError):
        verify_evidence([{"document_id": "d1", "page": 1, "quote": "编造"}], [doc()])


def test_stale_unknown_and_empty_are_never_ready():
    passing = check_one(rule(), [doc()], {})
    assert overall([]) == "not_ready"
    assert overall([passing], stale=True) == "stale"
    assert overall([check_one(rule(), [doc("", parse_status="failed")], {})]) == "needs_review"


def test_attestation_only_resolves_manual_unknown():
    manual = check_one(rule("manual_review"), [doc()], {})
    assert overall([manual], confirmed=["r1"]) == "ready"
    unreadable = check_one(rule(), [doc("", parse_status="needs_review")], {})
    assert overall([unreadable], confirmed=["r1"]) == "needs_review"
