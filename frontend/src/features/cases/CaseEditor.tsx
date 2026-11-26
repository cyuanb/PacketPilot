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
                    : await post<Case>("/cases", draftCase);
                setModal("");
                setDraftCase({
                  title: "",
                  institution: "",
                  kind: "exchange",
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
            <label>
              申请名称
              <input
                required
                placeholder="例如：秋季校际交流申请"
                value={draftCase.title}
                onChange={(e) =>
                  setDraftCase({ ...draftCase, title: e.target.value })
                }
              />
            </label>
            <label>
              申请机构
              <input
                placeholder="学校、组织或项目名称"
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
