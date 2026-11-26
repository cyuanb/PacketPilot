import { FileText, Info, RefreshCw, Trash2, Upload } from "lucide-react";
import { api } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Badge } from "../../components/Badge";
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
>;
export function DocumentsPanel({
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
              aria-label={"删除" + d.title}
              onClick={() =>
                setConfirm({
                  text: "删除此材料的所有版本及受影响的历史检查？此操作不可撤销。",
                  action: async () => {
                    await api("/documents/" + d.id, {
                      method: "DELETE",
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
  );
}
