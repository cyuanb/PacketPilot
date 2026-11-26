import { Plus, X } from "lucide-react";
import { post } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Dialog } from "../../components/Dialog";
type Props = Pick<
  WorkspaceState,
  | "modal"
  | "item"
  | "error"
  | "setModal"
  | "facts"
  | "setFacts"
  | "busy"
  | "act"
  | "refresh"
>;
export function FactsDialog({
  modal,
  item,
  error,
  setModal,
  facts,
  setFacts,
  busy,
  act,
  refresh,
}: Props) {
  return (
    <>
      {modal === "facts" && item && (
        <Dialog
          busy={busy}
          error={error}
          title="确认申请背景"
          close={() => setModal("")}
        >
          <p className="dialog-intro">
            只填写已确定的信息。修改后，相关检查需要重新核对。
          </p>
          {facts.map(([k, v], i) => (
            <div className="fact-editor" key={i}>
              <input
                aria-label={"字段" + (i + 1)}
                placeholder="例如：申请类别"
                value={k}
                onChange={(e) =>
                  setFacts(
                    facts.map((f, j) => (j === i ? [e.target.value, f[1]] : f)),
                  )
                }
              />
              <input
                aria-label={"值" + (i + 1)}
                placeholder="例如：本科交流"
                value={v}
                onChange={(e) =>
                  setFacts(
                    facts.map((f, j) => (j === i ? [f[0], e.target.value] : f)),
                  )
                }
              />
              <button
                className="icon-button"
                aria-label="移除此字段"
                onClick={() => setFacts(facts.filter((_, j) => j !== i))}
              >
                <X size={16} />
              </button>
            </div>
          ))}
          <button
            className="text-action"
            onClick={() => setFacts([...facts, ["", ""]])}
          >
            <Plus size={15} />
            添加背景字段
          </button>
          <div className="dialog-actions">
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await post("/cases/" + item.id + "/facts/confirm", {
                    revision: item.revision,
                    facts: Object.fromEntries(facts.filter(([k]) => k.trim())),
                  });
                  setModal("");
                  await refresh();
                })
              }
            >
              确认并保存
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
