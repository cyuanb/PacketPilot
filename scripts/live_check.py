"""Opt-in real-model smoke test. Uses synthetic documents only; creates a labeled test case."""

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import settings  # noqa: E402


def main():
    with httpx.Client(
        base_url=settings.app_origin, headers={"X-PacketPilot": "1"}, timeout=30, trust_env=False
    ) as client:

        def call(method, path, **kwargs):
            r = client.request(method, "/api/v1" + path, **kwargs)
            r.raise_for_status()
            return r.json()

        call(
            "POST",
            "/auth/login",
            json={"username": settings.owner_username, "password": settings.owner_password},
        )
        c = call("POST", "/demo")
        path = "/cases/" + c["id"]

        def wait(run):
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                result = call("GET", "/runs/" + run["id"])
                if result["status"] not in ("queued", "running"):
                    if result["status"] not in ("completed", "waiting_for_input"):
                        raise RuntimeError(result["error"])
                    return result
                time.sleep(2)
            raise TimeoutError("Live model run exceeded smoke-test deadline")

        extraction = wait(call("POST", path + "/extract", json={"revision": c["revision"]}))
        c = call("GET", path)
        draft = next(r for r in c["rule_sets"] if r["id"] == extraction["result"]["draft_id"])
        assert len(draft["requirements"]) >= 5
        # Exercise activation on a fresh real-model draft, then use curated version for reproducible amendment checks.
        c = call("POST", "/rule-sets/" + draft["id"] + "/activate", json={"revision": c["revision"]})
        initial = wait(call("POST", path + "/checks", json={"revision": c["revision"]}))
        c = call("GET", path)
        application = next(d for d in c["documents"] if d["category"] == "申请表")
        call(
            "POST",
            "/documents/" + application["id"] + "/correction",
            json={"revision": c["revision"], "text": "申请表\n姓名：李沐\n申请类别：本科交流"},
        )
        assert call("GET", path)["checklist"]["stale"]
        for title, content in [
            (
                "学习计划",
                "学习计划\n姓名：李沐\n学习目标：学习数据库与分布式系统，提升工程实践能力。\n拟修课程：数据库系统、分布式计算。\n",
            ),
            (
                "推荐信",
                "推荐信\n姓名：李沐\n推荐意见：该生学习认真，具有独立研究能力。\n推荐人签名栏：请人工查看原件。\n",
            ),
        ]:
            call(
                "POST",
                path + "/sources/text",
                json={"title": title, "text": content, "purpose": "material", "category": title},
            )
        c = call("GET", path)
        amended = wait(call("POST", path + "/checks", json={"revision": c["revision"]}))
        c = call("GET", path)
        findings = c["checklist"]["findings"]
        assert not any(f["verdict"] in ("missing", "conflict") for f in findings), findings
        for finding in findings:
            if finding["method"] == "manual":
                call(
                    "POST",
                    path + "/attestations",
                    json={
                        "revision": c["revision"],
                        "requirement_id": finding["requirement_id"],
                        "note": "合成样例：测试人工复核入口，不代表真实签名验证。",
                    },
                )
        final = call("GET", path)
        # All semantic unknowns must be visible rather than silently counted as passes.
        export = client.get("/api/v1" + path + "/export?format=html")
        export.raise_for_status()
        summary = {
            "case_id": c["id"],
            "model": settings.llm_model,
            "extracted_requirements": len(draft["requirements"]),
            "initial": [(f["requirement_id"], f["verdict"]) for f in initial["result"]["findings"]],
            "amended": [(f["requirement_id"], f["verdict"]) for f in amended["result"]["findings"]],
            "final_status": final["checklist"]["status"],
            "export": export.status_code,
            "skill_hash": amended["skill_hash"],
        }
        output = ROOT / "artifacts"
        output.mkdir(exist_ok=True)
        (output / "live-evaluation.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
