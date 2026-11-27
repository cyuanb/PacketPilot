import { useEffect, useState } from "react";
import type { Scenario } from "../workflow/types";
import { api, post, type Case } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Dialog } from "../../components/Dialog";
import { kinds } from "./constants";
type Props = Pick<
  WorkspaceState,
  | "modal"
  | "error"
  | "setModal"
  | "act"
  | "item"
  | "draftCase"
  | "setDraftCase"
  | "loadCases"
  | "openCase"
  | "setItem"
  | "busy"
>;
export function CaseEditor({
  modal,
  error,
  setModal,
  act,
  item,
  draftCase,
  setDraftCase,
  loadCases,
  openCase,
  setItem,
  busy,
}: Props) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState("");
  const [scenarioError, setScenarioError] = useState("");
  useEffect(() => {
    if (modal !== "new") return;
    setScenarioId("");
    setDraftCase({ title: "", institution: "", kind: "other", deadline: "" });
    setScenarioError("");
    const controller = new AbortController();
    api<Scenario[]>("/scenarios", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setScenarios(value);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setScenarioError(error.message);
      });
    return () => controller.abort();
  }, [modal]);
  const scenario = scenarios.find((value) => value.id === scenarioId);
  return (
    <>
      {(modal === "new" || modal === "edit") && (
        <Dialog
          busy={busy}
          error={error}
          title={modal === "edit" ? "编辑申请信息" : "创建一份新的申请"}
          close={() => setModal("")}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                const c =
                  modal === "edit" && item
                    ? await api<Case>("/cases/" + item.id, {
                        method: "PATCH",
                        body: JSON.stringify({
                          ...draftCase,
                          revision: item.revision,
                          archived: item.archived,
                        }),
                      })
                    : await post<Case>("/cases", {
                        ...draftCase,
                        scenario_id: scenarioId || null,
                      });
                setModal("");
                setDraftCase({
                  title: "",
                  institution: "",
                  kind: "other",
                  deadline: "",
                });
                await loadCases();
                openCase(c.id);
                setItem(c);
              });
            }}
          >
            <p className="dialog-intro">
              {modal === "edit"
                ? "修改后会提示重新核对，确保检查与当前申请信息一致。"
                : "先记下申请目标，材料可以慢慢补齐。"}
            </p>
            {modal === "new" && (
              <div className="scenario-selector">
                <label>
                  事项场景
                  <select
                    value={scenarioId}
                    onChange={(event) => {
                      setScenarioId(event.target.value);
                      const config = scenarios.find(
                        (value) => value.id === event.target.value,
                      );
                      setDraftCase({
                        ...draftCase,
                        kind: config?.kind || "other",
                      });
                    }}
                  >
                    <option value="">通用材料事项</option>
                    {scenarios.map((config) => (
                      <option key={config.id} value={config.id}>
                        {config.title}
                      </option>
                    ))}
                  </select>
                </label>
                {scenario && (
                  <>
                    <p>{scenario.description}</p>
                    <small>{scenario.notice}</small>
                  </>
                )}
                {scenarioError && (
                  <p role="alert">
                    场景配置未读取：{scenarioError}
                    。仍可创建通用事项，或重新打开此窗口。
                  </p>
                )}
              </div>
            )}
            {modal === "edit" && item?.scenario && (
              <p className="hint">
                场景：{item.scenario.title} · 起步配置 v{item.scenario.version}
                （场景快照保持原样）
              </p>
            )}
            <label>
              申请名称
              <input
                required
                placeholder={
                  scenario
                    ? `例如：${scenario.title} · 本次目标`
                    : "例如：项目申请、入职或客户准入材料"
                }
                value={draftCase.title}
                onChange={(e) =>
                  setDraftCase({ ...draftCase, title: e.target.value })
                }
              />
            </label>
            <label>
              接收方/机构
              <input
                placeholder="学校、单位、客户或平台名称"
                value={draftCase.institution}
                onChange={(e) =>
                  setDraftCase({ ...draftCase, institution: e.target.value })
                }
              />
            </label>
            <div className="form-row">
              <label>
                申请类型
                <select
                  disabled={
                    !!scenarioId || !!(modal === "edit" && item?.scenario)
                  }
                  value={draftCase.kind}
                  onChange={(e) =>
                    setDraftCase({ ...draftCase, kind: e.target.value })
                  }
                >
                  {Object.entries(kinds).map(([k, v]) => (
                    <option value={k} key={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                截止日期（可选）
                <input
                  type="date"
                  value={draftCase.deadline}
                  onChange={(e) =>
                    setDraftCase({ ...draftCase, deadline: e.target.value })
                  }
                />
              </label>
            </div>
            <div className="dialog-actions">
              <button
                disabled={busy}
                type="button"
                className="secondary"
                onClick={() => setModal("")}
              >
                取消
              </button>
              <button className="primary" disabled={busy}>
                {modal === "edit" ? "保存修改" : "创建申请"}
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </>
  );
}
