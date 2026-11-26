import { useState } from "react";
import { api } from "../../api/client";
import { useAsyncAction } from "../../app/useAsyncAction";
import { Dialog } from "../../components/Dialog";
import { fileSize, type LibraryAsset, type UploadResult } from "./types";

export function UploadDialog({
  asset,
  close,
  saved,
}: {
  asset?: LibraryAsset;
  close: () => void;
  saved: (result: UploadResult) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const { busy, error, act, isCurrent } = useAsyncAction();
  const tooLarge = !!file && file.size > 20 * 1024 * 1024;
  return (
    <Dialog
      title={asset ? "上传新版本" : "上传到资料中心"}
      close={close}
      busy={busy}
      error={error}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!file) return;
          act(async () => {
            const data = new FormData();
            data.append("file", file);
            if (asset) data.append("revision", String(asset.revision));
            const result = await api<UploadResult>(
              asset ? `/assets/${asset.id}/versions` : "/assets",
              { method: "POST", body: data },
            );
            if (isCurrent()) saved(result);
          });
        }}
      >
        <p className="dialog-intro">
          {asset
            ? "上传后会新增一个资料版本，旧版本和事项中正在使用的材料保持不变。"
            : "无需先建立事项。资料会先进入收集箱，再由你确认主体和分类。"}
        </p>
        <label>
          选择文件
          <input
            type="file"
            required
            accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>
        <p className="hint">
          PDF、DOCX、TXT、Markdown、PNG 或 JPEG；单文件上限 20
          MiB。保存原件不代表已完成内容解析。
        </p>
        {file && (
          <p className="library-file-name">
            {file.name} · {fileSize(file.size)}
          </p>
        )}
        {tooLarge && (
          <p role="alert" className="form-error">
            文件超过 20 MiB，请选择较小的文件。
          </p>
        )}
        <div className="dialog-actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={close}
          >
            取消
          </button>
          <button
            className="primary"
            disabled={busy || !file || tooLarge || file.size === 0}
          >
            {busy ? "正在保存…" : asset ? "保存新版本" : "保存资料"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
