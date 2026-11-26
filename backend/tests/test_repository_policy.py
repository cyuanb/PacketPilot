import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "public_content_policy", Path(__file__).resolve().parents[2] / "scripts/check_public_content.py"
)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


@pytest.mark.parametrize(
    "path",
    [
        "plan/internal.md",
        "status/current.md",
        "research/interviews.md",
        "docs/plans/internal.md",
        "docs/iteration-progress.md",
        "docs/evidence/run.json",
    ],
)
def test_private_workspace_paths_are_rejected(path):
    assert policy.violations(path, "internal record")


def test_internal_task_marker_in_public_document_is_rejected():
    assert policy.violations("README.md", "Internal task " + "PP-" + "001")


@pytest.mark.parametrize(
    "path,text",
    [
        ("README.md", "PacketPilot installation and supported file types"),
        ("docs/architecture.md", "Versioned materials and authenticated downloads"),
        ("docs/testing.md", "Run pytest with synthetic documents"),
    ],
)
def test_current_product_documentation_is_allowed(path, text):
    assert not policy.violations(path, text)
