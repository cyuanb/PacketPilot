import { useEffect, useState } from "react";
import type { Run } from "../../api/types";
import { watchRun } from "./watchRun";

const toolLabels: Record<string, string> = {
  get_case_context: "读取申请背景",
  read_document: "查看材料原文",
  save_requirement_draft: "整理要求草稿",
  run_checks: "逐项核对材料",
  record_semantic_findings: "保存内容检查",
  propose_facts: "整理待确认背景",
  ask_user: "确认关键信息",
};

export function useRunActivity(
  running: Run | undefined,
  loadDetail: (force?: boolean) => Promise<unknown>,
  loadCases: (force?: boolean) => Promise<unknown>,
) {
  const [activity, setActivity] = useState("");
  const [trace, setTrace] = useState<string[]>([]);
  const id = running?.id,
    kind = running?.kind;
  useEffect(() => {
    setTrace([]);
    setActivity(kind === "parse" ? "正在读取材料内容" : "");
    if (!id) return;
    return watchRun(id, {
      stage: setActivity,
      tool: (name) =>
        setTrace((trace) => [
          ...trace.slice(-15),
          toolLabels[name] || "正在处理",
        ]),
      done: () => setActivity(""),
      refreshDetail: loadDetail,
      refreshList: loadCases,
    });
  }, [id, kind, loadDetail, loadCases]);
  return { activity, trace, setTrace };
}
