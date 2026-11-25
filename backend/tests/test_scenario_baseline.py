import json
from pathlib import Path

import pytest
from app.domain import check_one, verify_evidence
from app.schemas import Requirement

CASES = json.loads((Path(__file__).parent / "fixtures/review_scenarios.json").read_text(encoding="utf-8"))[
    "cases"
]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_cross_scenario_regression(case):
    requirement = Requirement(
        id="r1",
        title=case["notice"],
        **case["requirement"],
        source_evidence=[{"document_id": "notice", "page": 1, "quote": case["notice"]}],
    )
    documents = [
        {
            "id": d["id"],
            "filename": d["id"] + ".txt",
            "purpose": "material",
            "category": "",
            "mime": "text/plain",
            "size": len(d["text"].encode()),
            "parse_status": "ready",
            "pages": [{"number": 1, "text": d["text"]}],
        }
        for d in case["documents"]
    ]
    documents.append({"id": "notice", "purpose": "source", "pages": [{"number": 1, "text": case["notice"]}]})
    verify_evidence(requirement.source_evidence, documents, "source")
    finding = check_one(requirement, documents, case.get("facts", {}))
    assert finding["verdict"] == case["expected"]["verdict"]
    if "applicability" in case["expected"]:
        assert finding["applicability"] == case["expected"]["applicability"]
    if "field_statuses" in case["expected"]:
        assert [c["status"] for c in finding["field_coverage"]] == case["expected"]["field_statuses"]
    verify_evidence(finding["evidence"], documents, "material")
