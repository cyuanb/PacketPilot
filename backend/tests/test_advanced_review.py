from copy import deepcopy

import pytest
from app.review.aggregation import assess_results
from app.review.checks import run_checks
from app.review.semantic import validate_semantic
from app.review.structure import validate_structure
from test_domain import doc, rule
from test_workflow import case, current, text_document


def inputs(rules, docs, **values):
    return {
        "requirements": rules,
        "documents": docs,
        "facts": {},
        "subjects": [],
        "reference_date": "2026-11-27",
        "deadline": "2026-12-01",
        **values,
    }


@pytest.mark.parametrize(
    "operator,minimum,expected", [("all", 1, "blocked"), ("any", 1, "ready"), ("at_least", 2, "blocked")]
)
def test_requirement_groups_control_readiness_instead_of_every_alternative(operator, minimum, expected):
    a = rule(id="a")
    b = rule(id="b", document_type="申请表")
    group = rule(
        kind="group",
        id="group",
        parameters={"children": ["a", "b"], "operator": operator, "min_count": minimum},
    )
    rules = [a, b, group]
    findings = run_checks(inputs(rules, [doc()]))
    report = assess_results(rules, findings, {})
    assert report["coverage"]["complete"] and report["status"] == expected


def test_nested_group_rejects_cycles_and_multiple_parents():
    a = rule(id="a", kind="group", parameters={"children": ["b"]})
    b = rule(id="b", kind="group", parameters={"children": ["a"]})
    with pytest.raises(ValueError):
        validate_structure([a, b])
    with pytest.raises(ValueError):
        validate_structure(
            [rule(id="x"), {**a, "parameters": {"children": ["x"]}}, {**b, "parameters": {"children": ["x"]}}]
        )


def test_manual_group_confirmation_is_not_machine_pass():
    r = rule(kind="manual_review", id="manual")
    g = rule(kind="group", id="group", parameters={"children": ["manual"], "operator": "all"})
    findings = run_checks(inputs([r, g], [doc()]))
    report = assess_results([r, g], findings, {}, confirmed=["manual"])
    assert report["status"] == "ready"
    group = report["findings"][1]
    assert group["verdict"] == "unknown" and group["satisfied_by_confirmation"]


def test_duplicate_content_does_not_meet_two_independent_materials():
    docs = [doc(id="a", sha256="same"), doc(id="b", sha256="same")]
    r = rule(parameters={"min_count": 2, "distinct_by": "original"})
    assert run_checks(inputs([r], docs))[0]["verdict"] == "missing"
    docs[1]["sha256"] = "different"
    assert run_checks(inputs([r], docs))[0]["verdict"] == "pass"
    r["parameters"]["distinct_by"] = "issuer"
    assert run_checks(inputs([r], docs))[0]["verdict"] == "unknown"


def test_subject_fields_do_not_mix_recommender_and_applicant():
    r = rule(
        kind="field_consistency",
        parameters={"field": "姓名", "subject_role": "applicant", "slot_id": "identity"},
    )
    docs = [
        doc(id="a", assignment={"state": "accepted", "subject_id": "person1", "slot_ids": ["identity"]}),
        doc(id="b", assignment={"state": "accepted", "subject_id": "person1", "slot_ids": ["identity"]}),
        doc(
            id="c",
            text="成绩单\n姓名：另外一人\n成绩：100",
            assignment={"state": "accepted", "subject_id": "person2", "slot_ids": ["identity"]},
        ),
    ]
    subjects = [
        {"subject_id": "person1", "role": "applicant"},
        {"subject_id": "person2", "role": "recommender"},
    ]
    result = run_checks(inputs([r], docs, subjects=subjects))[0]
    assert result["verdict"] == "pass" and {c["document_id"] for c in result["field_coverage"]} == {"a", "b"}
    subjects.append({"subject_id": "person2", "role": "applicant"})
    assert run_checks(inputs([r], docs, subjects=subjects))[0]["verdict"] == "unknown"


def test_original_translation_requires_same_subject_explicit_pair():
    r = rule(parameters={"variant": "original", "requires_pair": True})
    a = doc(
        id="a",
        assignment={
            "state": "accepted",
            "document_type": "成绩单",
            "variant": "original",
            "subject_id": "one",
            "pair_key": "pair",
        },
    )
    b = doc(
        id="b",
        assignment={
            "state": "accepted",
            "document_type": "成绩单",
            "variant": "translation",
            "subject_id": "two",
            "pair_key": "pair",
        },
    )
    assert run_checks(inputs([r], [a, b]))[0]["verdict"] == "unknown"
    b["assignment"]["subject_id"] = "one"
    assert run_checks(inputs([r], [a, b]))[0]["verdict"] == "pass"


def test_date_window_period_and_missing_reference_are_conservative():
    r = rule(
        kind="date_constraint",
        parameters={"field": "开始日期", "end_field": "结束日期", "reference": "deadline"},
    )
    d = doc(text="成绩单\n开始日期：2026-01-01\n结束日期：2026-12-31")
    assert run_checks(inputs([r], [d]))[0]["verdict"] == "pass"
    assert run_checks(inputs([r], [d], deadline=""))[0]["verdict"] == "unknown"
    d["pages"][0]["text"] = "成绩单\n开始日期：2026-01-01\n结束日期：2026-11-01"
    assert run_checks(inputs([r], [d]))[0]["verdict"] == "fail"


def test_semantic_requires_every_criterion_and_every_scoped_document():
    r = rule(kind="semantic_requirement", parameters={"criteria": ["包含课程成绩"]})
    docs = [doc(id="a"), doc(id="b")]
    evidence = [{"document_id": d["id"], "page": 1, "quote": d["pages"][0]["text"]} for d in docs]
    f = {"verdict": "pass", "evidence": evidence, "semantic_coverage": []}
    with pytest.raises(ValueError):
        validate_semantic(f, r, inputs([r], docs))
    f["semantic_coverage"] = [
        {"criterion": "包含课程成绩", "verdict": "pass", "reason": "两份均有成绩字段", "evidence": evidence}
    ]
    validate_semantic(f, r, inputs([r], docs))
    bad = deepcopy(f)
    bad["semantic_coverage"][0]["evidence"] = evidence[:1]
    with pytest.raises(ValueError):
        validate_semantic(bad, r, inputs([r], docs))
    docs[1]["parse_status"] = "needs_review"
    with pytest.raises(ValueError):
        validate_semantic(f, r, inputs([r], docs))


def test_conflict_dry_run_does_not_activate_and_requires_resolution(client):
    item = case(client)
    a = text_document(client, item, "文件不得超过 100 字节", "source", "通知甲")
    b = text_document(client, item, "文件不得超过 200 字节", "source", "通知乙")
    rules = [
        rule(
            id="a",
            kind="file_size",
            parameters={"max_bytes": 100},
            source_evidence=[{"document_id": a["id"], "page": 1, "quote": "文件不得超过 100 字节"}],
        ),
        rule(
            id="b",
            kind="file_size",
            parameters={"max_bytes": 200},
            source_evidence=[{"document_id": b["id"], "page": 1, "quote": "文件不得超过 200 字节"}],
        ),
    ]
    body = {"revision": current(client, item)["revision"], "requirements": rules}
    trial = client.post(f"/api/v1/cases/{item['id']}/rules/preview", json=body)
    assert trial.status_code == 200 and trial.json()["conflicts"][0]["resolved"] is False
    assert not current(client, item)["checklist"]["requirements"]
    draft = client.post(f"/api/v1/cases/{item['id']}/rule-sets", json=body).json()
    assert (
        client.post(
            f"/api/v1/rule-sets/{draft['id']}/activate", json={"revision": body["revision"]}
        ).status_code
        == 422
    )
    for r in rules:
        r["parameters"]["conflict_resolution"] = "两个接收渠道均须满足，按严格约束准备"
    draft = client.post(f"/api/v1/cases/{item['id']}/rule-sets", json={**body, "requirements": rules}).json()
    assert client.post(
        f"/api/v1/rule-sets/{draft['id']}/activate", json={"revision": body["revision"]}
    ).is_success
