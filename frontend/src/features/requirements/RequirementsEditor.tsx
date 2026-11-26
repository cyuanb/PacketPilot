import { post } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Dialog } from "../../components/Dialog";
type Props = Pick<
  WorkspaceState,
  | "modal"
  | "item"
  | "error"
  | "setModal"
  | "advanced"
  | "setRulesRaw"
  | "rules"
  | "setRules"
  | "rulesRaw"
  | "setError"
  | "setAdvanced"
  | "busy"
  | "act"
  | "refresh"
  | "setNotice"
>;
export function RequirementsEditor({
  modal,
  item,
  error,
  setModal,
  advanced,
  setRulesRaw,
  rules,
  setRules,
  rulesRaw,
  setError,
  setAdvanced,
  busy,
  act,
  refresh,
  setNotice,
}: Props) {
  return (
    <>
      {modal === "rules" && item && (
        <Dialog
          busy={busy}
          error={error}
          title="审阅申请要求"
          close={() => setModal("")}
          wide
        >
          <p className="dialog-intro">
            编辑会保存为新的草稿版本。请确认来源、适用条件和检查方式，再启用。
          </p>
          <button
            className="text-action"
            onClick={() => {
              if (!advanced) setRulesRaw(JSON.stringify(rules, null, 2));
              else {
                try {
                  setRules(JSON.parse(rulesRaw));
                } catch {
                  setError("要求格式有误");
                  return;
                }
              }
              setAdvanced(!advanced);
            }}
          >
            {advanced ? "返回可视化编辑" : "高级：编辑完整结构"}
          </button>
          {advanced ? (
            <textarea
              className="code-editor"
              value={rulesRaw}
              onChange={(e) => setRulesRaw(e.target.value)}
              aria-label="要求 JSON"
            />
          ) : (
            rules.map((r, i) => (
              <div className="rule-editor" key={r.id}>
                <label>
                  要求 {i + 1}
                  <input
                    value={r.title}
                    onChange={(e) =>
                      setRules(
                        rules.map((x, j) =>
                          j === i ? { ...x, title: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </label>
                <div className="form-row">
                  <label>
                    对应材料
                    <input
                      value={r.document_type}
                      onChange={(e) =>
                        setRules(
                          rules.map((x, j) =>
                            j === i
                              ? { ...x, document_type: e.target.value }
                              : x,
                          ),
                        )
                      }
                    />
                  </label>
                  <label>
                    检查方式
                    <select
                      value={r.kind}
                      onChange={(e) =>
                        setRules(
                          rules.map((x, j) =>
                            j === i ? { ...x, kind: e.target.value } : x,
                          ),
                        )
                      }
                    >
                      {Object.entries({
                        material_presence: "材料存在",
                        semantic_requirement: "内容核对",
                        manual_review: "人工核对",
                        file_format: "文件格式",
                        file_size: "文件大小",
                        page_count: "页数",
                        required_field: "必填字段",
                        field_consistency: "字段一致性",
                        date_constraint: "日期限制",
                      }).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <blockquote>
                  {r.source_evidence.map((e) => e.quote).join("\n")}
                </blockquote>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={r.required}
                    onChange={(e) =>
                      setRules(
                        rules.map((x, j) =>
                          j === i ? { ...x, required: e.target.checked } : x,
                        ),
                      )
                    }
                  />
                  必需要求
                </label>
                <small>
                  条件：
                  {Object.keys(r.condition).length
                    ? JSON.stringify(r.condition)
                    : "无附加条件"}
                </small>
              </div>
            ))
          )}
          <div className="dialog-actions">
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await post("/cases/" + item.id + "/rule-sets", {
                    revision: item.revision,
                    requirements: advanced ? JSON.parse(rulesRaw) : rules,
                  });
                  setModal("");
                  await refresh();
                  setNotice("已保存新草稿，请确认启用");
                })
              }
            >
              保存为新草稿
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
