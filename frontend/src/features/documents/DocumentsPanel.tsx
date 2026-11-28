import type { Case } from "../../api/types";
import { CaseLibraryLinks } from "../workflow/CaseLibraryLinks";
import { FileText, Info, RefreshCw, Trash2, Upload } from "lucide-react";
import { api } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Badge } from "../../components/Badge";
import { MaterialReviewControl } from "./MaterialReviewControl";
type Props = Pick<
  WorkspaceState,
  | "busy"
  | "pickUpload"
  | "act"
  | "fileChange"
  | "setSource"
  | "setModal"
  | "docMaterials"
  | "openDoc"
  | "setConfirm"
  | "refresh"
> & { item: Case };
export function DocumentsPanel({
  item,
  busy,
  pickUpload,
  act,
  fileChange,
  setSource,
  setModal,
  docMaterials,
  openDoc,
  setConfirm,
  refresh,
}: Props) {
  return (
    <>
      <CaseLibraryLinks item={item} purpose="material" refresh={refresh} />
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>你的申请材料</h2>
            <p>上传、替换与校订都会让关联检查重新核对</p>
          </div>
          <button
            className="primary"
            disabled={busy}
            onClick={() => pickUpload()}
          >
            <Upload size={17} />
            上传材料
          </button>
        </div>
        <div
          className="upload-zone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files[0];
            if (f) act(() => fileChange(f));
          }}
        >
          <Upload size={28} />
          <strong>
            把材料拖到这里，或{" "}
            <button onClick={() => pickUpload()}>选择文件</button>
          </strong>
          <p>PDF、DOCX、TXT、MD 或图片 · 单文件最大 20 MiB</p>
          <button
            className="text-action"
            onClick={() => {
              setSource({
                title: "补充材料",
                text: "",
                purpose: "material",
                category: "",
              });
              setModal("source");
            }}
          >
            也可以粘贴材料文本
          </button>
        </div>
        <div className="document-list">
          {!!docMaterials.length && (
            <p className="material-review-help">
              “确认本版材料”表示你已核对当前原件与归属信息。它与“可读取”“要求通过”分别记录；换版、校订或归属变化后需重新确认。
            </p>
          )}
          {docMaterials.map((d) => (
            <div className="document-row" key={d.id}>
              <span className="document-icon">
                <FileText size={23} />
                <small>{d.filename.split(".").pop()?.toUpperCase()}</small>
              </span>
              <button
                className="document-name"
                onClick={() => act(() => openDoc(d))}
              >
                <strong>{d.title}</strong>
                <span>
                  版本 {d.version} · {(d.size / 1024).toFixed(1)} KB
                  {d.parse_note ? " · " + d.parse_note : ""}
                </span>
              </button>
              <Badge status={d.parse_status === "ready" ? "pass" : "unknown"}>
                {(
                  {
                    ready: "可读取",
                    queued: "排队中",
                    failed: "读取失败",
                    needs_review: "需核对原件",
                  } as Record<string, string>
                )[d.parse_status] || d.parse_status}
              </Badge>
              <MaterialReviewControl
                item={item}
                document={d}
                changed={async () => {
                  await refresh();
                }}
              />
              <button
                className="icon-button"
                title="替换材料"
                aria-label={"替换" + d.title}
                onClick={() => pickUpload("material", d.id)}
              >
                <RefreshCw size={17} />
              </button>
              <button
                className="icon-button danger"
                aria-label={"从事项移除" + d.title}
                onClick={() =>
                  setConfirm({
                    text: "从事项移除此材料的所有版本及受影响的检查记录？资料中心仍保留原件和版本。",
                    action: async () => {
                      await api("/case-document-links/" + d.id, {
                        method: "DELETE",
                        body: JSON.stringify({ revision: item.revision }),
                      });
                      await refresh();
                    },
                  })
                }
              >
                <Trash2 size={17} />
              </button>
            </div>
          ))}
        </div>
        {!docMaterials.length && (
          <div className="subtle-note">
            <Info size={16} />
            先上传手边已有的材料，不必一次准备齐全。
          </div>
        )}
      </section>
    </>
  );
}
