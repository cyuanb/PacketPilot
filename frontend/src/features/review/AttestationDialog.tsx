import { post } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Dialog } from "../../components/Dialog";
type Props = Pick<
  WorkspaceState,
  | "modal"
  | "item"
  | "error"
  | "setModal"
  | "manualNote"
  | "setManualNote"
  | "busy"
  | "act"
  | "manual"
  | "refresh"
>;
export function AttestationDialog({
  modal,
  item,
  error,
  setModal,
  manualNote,
  setManualNote,
  busy,
  act,
  manual,
  refresh,
}: Props) {
  return (
    <>
      {modal === "manual" && item && (
        <Dialog
          busy={busy}
          error={error}
          title="记录人工检查"
          close={() => setModal("")}
        >
          <p className="dialog-intro">
            请先查看原件，确认签署、盖章或其他需要本人核对的要求。记录仅对当前材料版本有效。
          </p>
          <label>
            确认说明
            <textarea
              required
              placeholder="说明你核对了什么…"
              value={manualNote}
              onChange={(e) => setManualNote(e.target.value)}
            />
          </label>
          <div className="dialog-actions">
            <button
              className="primary"
              disabled={busy || !manualNote.trim()}
              onClick={() =>
                act(async () => {
                  await post("/cases/" + item.id + "/attestations", {
                    revision: item.revision,
                    requirement_id: manual,
                    note: manualNote,
                  });
                  setModal("");
                  await refresh();
                })
              }
            >
              我已核对，记录确认
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
