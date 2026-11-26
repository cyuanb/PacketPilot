import type { WorkspaceState } from "../app/useWorkspace";
import { Dialog } from "./Dialog";
type Props = Pick<
  WorkspaceState,
  "confirm" | "error" | "setConfirm" | "busy" | "act"
>;
export function ConfirmationDialog({
  confirm,
  error,
  setConfirm,
  busy,
  act,
}: Props) {
  return (
    <>
      {confirm && (
        <Dialog
          busy={busy}
          error={error}
          title="请确认操作"
          close={() => setConfirm(null)}
        >
          <p>{confirm.text}</p>
          <div className="dialog-actions">
            <button className="secondary" disabled={busy} onClick={() => setConfirm(null)}>
              取消
            </button>
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await confirm.action();
                  setConfirm(null);
                })
              }
            >
              确认
            </button>
          </div>
        </Dialog>
      )}
    </>
  );
}
