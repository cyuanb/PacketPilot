import copy

import pytest
from app.domain import assess_results, check_one, overall
from app.models import RuleSet, Run
from test_domain import doc, rule


def passing(r=None):
    return check_one(r or rule(), [doc()], {})


def test_expected_requirements_cannot_be_inferred_from_present_results():
    requirements = [rule(), rule(id="r2")]
    report = assess_results(requirements, [passing()], {})
    assert report["status"] == "needs_review"
    assert report["coverage"]["missing_ids"] == ["r2"]
    assert report["findings"][1]["evaluation_state"] == "not_evaluated"
    assert overall([passing()]) == "not_ready"


@pytest.mark.parametrize(
    "mutation,problem",
    [
        (lambda fs: fs + [copy.deepcopy(fs[0])], "duplicate_ids"),
        (lambda fs: fs + [{**fs[0], "requirement_id": "other"}], "unexpected_ids"),
        (lambda fs: [{**fs[0], "verdict": "invented"}], "invalid_ids"),
        (lambda fs: [{**fs[0], "applicability": "not_applicable"}], "invalid_ids"),
        (lambda fs: [{**fs[0], "method": "manual"}], "invalid_ids"),
    ],
)
def test_duplicate_unknown_and_invalid_results_do_not_make_ready(mutation, problem):
    report = assess_results([rule()], mutation([passing()]), {})
    assert not report["coverage"]["complete"]
    assert report["coverage"][problem]
    assert report["status"] == "needs_review"


@pytest.mark.parametrize("condition", [{"field": "学历", "value": "本科"}, {"all": []}, {"all": None}])
def test_unknown_conditions_cannot_be_reported_as_pass(condition):
    r = rule(condition=condition)
    f = {**passing(), "applicability": "applicable"}
    assert assess_results([r], [f], {})["status"] == "needs_review"


def test_evaluated_advisory_failure_is_visible_but_not_a_blocker():
    r = rule(required=False)
    f = check_one(r, [], {})
    report = assess_results([r], [f], {})
    assert report["status"] == "ready"
    assert report["coverage"]["complete"]
    assert report["advisory_count"] == 1
    assert report["findings"][0]["verdict"] == "missing"


def test_empty_or_duplicate_rule_sets_never_make_ready():
    assert assess_results([], [], {})["status"] == "not_ready"
    assert assess_results([rule(), rule()], [passing()], {})["status"] == "needs_review"


def test_unknown_condition_is_not_resolved_by_attestation():
    r = rule("manual_review", condition={"field": "x", "value": "yes"})
    f = check_one(r, [doc()], {})
    assert assess_results([r], [f], {}, confirmed=["r1"])["status"] == "needs_review"


def test_explicit_not_applicable_is_covered():
    r = rule(condition={"field": "x", "value": "yes"})
    f = check_one(r, [], {"x": "no"})
    report = assess_results([r], [f], {"x": "no"})
    assert report["status"] == "ready" and report["coverage"]["complete"]


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("missing", "needs_review"),
        ("duplicate", "needs_review"),
        ("invalid", "needs_review"),
        ("failed", "needs_review"),
        ("running", "not_ready"),
        ("legacy", "stale"),
        ("changed_rules", "stale"),
    ],
)
def test_readiness_and_exports_validate_stored_results(client, database, mode, expected):
    c = client.post("/api/v1/demo").json()
    with database.begin() as db:
        run = db.get(Run, c["checklist"]["run_id"])
        result = copy.deepcopy(run.result)
        if mode == "missing":
            result["findings"] = result["findings"][:2]  # Only the passing rows remain.
        elif mode == "duplicate":
            result["findings"].append(copy.deepcopy(result["findings"][0]))
        elif mode == "invalid":
            result["findings"][0]["verdict"] = "made_up"
        elif mode == "legacy":
            result.pop("engine_version", None)
        elif mode in ("failed", "running"):
            run.status = mode
        else:
            rules = db.get(RuleSet, run.snapshot["rules_id"])
            changed = copy.deepcopy(rules.requirements)
            changed[0]["title"] = "不同语义但仍沿用 r1"
            rules.requirements = changed
        run.result = result
    updated = client.get("/api/v1/cases/" + c["id"]).json()
    assert updated["checklist"]["status"] == expected
    assert updated["checklist"]["can_export"] is False
    assert client.get("/api/v1/cases/" + c["id"] + "/export").status_code == 409


def test_current_complete_report_has_version_and_coverage(client):
    c = client.post("/api/v1/demo").json()
    report = c["checklist"]
    assert report["engine_version"] == "0.2.0"
    assert report["coverage"]["expected_count"] == report["coverage"]["evaluated_count"] == 5
    assert report["coverage"]["complete"] and report["can_export"]
