import { ExternalLink, FileText, Info, Pencil } from "lucide-react";
import { post } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Badge } from "../../components/Badge";
import { Dialog } from "../../components/Dialog";
import { Empty } from "../../components/Empty";
import { MaterialReviewControl } from "./MaterialReviewControl";
type Props = Pick<
  WorkspaceState,
  | "preview"
  | "error"
  | "setPreview"
  | "setModal"
  | "highlight"
  | "setCorrection"
  | "modal"
  | "item"
  | "correction"
  | "busy"
  | "act"
  | "refresh"
>;
export function DocumentPreview({
  preview,
  error,
  setPreview,
  setModal,
  highlight,
  setCorrection,
  modal,
  item,
  correction,
  busy,
  act,
  refresh,
}: Props) {
  return (
    <>
      {preview && (
        <Dialog
          busy={busy}
          error={error}
          title={preview.title}
          close={() => {
            setPreview(null);
            setModal("");
          }}
          wide
        >
          <div className="preview-meta">
            <Badge
              status={preview.parse_status === "ready" ? "pass" : "unknown"}
            >
              {preview.parse_status === "ready" ? "可读取" : "需要核对"}
            </Badge>
            <span>
              版本 {preview.version} ·{" "}
              {preview.parse_method === "user_corrected"
                ? "人工校订文本"
                : "原文提取"}
            </span>
            <a
              className="text-action"
              href={"/api/v1/documents/" + preview.id + "/content"}
              target="_blank"
              rel="noreferrer"
            >
              打开原件 <ExternalLink size={14} />
            </a>
          </div>
          {preview.parse_note && (
            <div className="subtle-note">
              <Info size={16} />
              {preview.parse_note}
            </div>
          )}
          {item && preview.purpose === "material" && (
            <MaterialReviewControl
              item={item}
              document={preview}
              changed={async (doc) => {
                setPreview(doc);
                await refresh();
              }}
            />
          )}
          {preview.pages.map((p) => (
            <section
              className={
                "preview-page " +
                (highlight?.page === p.number ? "highlighted" : "")
              }
              key={p.number}
            >
              <h4>{p.label}</h4>
              <pre>{p.text}</pre>
              {highlight?.page === p.number && (
                <blockquote>
                  <strong>引用片段</strong>
                  <p>{highlight.quote}</p>
                </blockquote>
              )}
            </section>
          ))}
          {!preview.pages.length && (
            <Empty
              icon={<FileText size={25} />}
              title="尚无可读取文本"
              text="打开原件核对内容，或提供校订文本。"
            />
          )}
          <div className="panel-footer">
            <button
              className="secondary"
              onClick={() => {
                setCorrection(preview.pages.map((p) => p.text).join("\n\n"));
                setModal("correction");
              }}
            >
              <Pencil size={15} />
              提供校订文本
            </button>
          </div>
          {modal === "correction" && item && (
            <div className="correction-form">
              <label>
                校订文本
                <textarea
                  className="large-textarea"
                  value={correction}
                  onChange={(e) => setCorrection(e.target.value)}
                />
              </label>
              <button
                className="primary"
                disabled={busy || !correction.trim()}
                onClick={() =>
                  act(async () => {
                    await post("/documents/" + preview.id + "/correction", {
                      revision: item.revision,
                      text: correction,
                    });
                    setPreview(null);
                    setModal("");
                    await refresh();
                  })
                }
              >
                保存为新版本
              </button>
            </div>
          )}
        </Dialog>
      )}
    </>
  );
}
