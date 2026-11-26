import { post } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Dialog } from "../../components/Dialog";
type Props = Pick<
  WorkspaceState,
  | "modal"
  | "item"
  | "error"
  | "source"
  | "setModal"
  | "act"
  | "refresh"
  | "setSource"
  | "busy"
>;
export function TextSourceDialog({
  modal,
  item,
  error,
  source,
  setModal,
  act,
  refresh,
  setSource,
  busy,
}: Props) {
  return (
    <>
      {modal === "source" && item && (
        <Dialog
          busy={busy}
          error={error}
          title={source.purpose === "source" ? "导入申请通知" : "添加材料文本"}
          close={() => setModal("")}
          wide
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await post("/cases/" + item.id + "/sources/text", source);
                setModal("");
                await refresh();
              });
            }}
          >
            <label>
              标题
              <input
                required
                value={source.title}
                onChange={(e) =>
                  setSource({ ...source, title: e.target.value })
                }
              />
            </label>
            <label>
              正文
              <textarea
                className="large-textarea"
                required
                placeholder="粘贴完整的通知或材料内容，保留原始要求和日期…"
                value={source.text}
                onChange={(e) => setSource({ ...source, text: e.target.value })}
              />
            </label>
            <p className="hint">
              齐呈会保留原文，并将每一项检查关联到具体依据。
            </p>
            <div className="dialog-actions">
              <button className="primary" disabled={busy}>
                保存原文
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </>
  );
}
