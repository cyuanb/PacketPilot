import { Archive, FileText, Plus, RefreshCw } from "lucide-react";
import { useState } from "react";
import { api } from "../../api/client";
import type { QueryClient } from "../../app/queryClient";
import { useAsyncAction } from "../../app/useAsyncAction";
import { useResource } from "../../app/useResource";
import { AssetEditor } from "./AssetEditor";
import { UploadDialog } from "./UploadDialog";
import { VersionPreview } from "./VersionPreview";
import {
  fileSize,
  type Duplicate,
  type LibraryDetail as Detail,
} from "./types";

export function DuplicateNotice({ duplicates }: { duplicates: Duplicate[] }) {
  if (!duplicates.length) return null;
  return (
    <div className="library-duplicate" role="status">
      <strong>已保存独立版本，发现原件相同的已有版本</strong>
      <p>
        原件的文件哈希和大小相同，校订文本可能不同，不会自动合并资料。以下为匹配的已有版本，最多显示
        20 条。
      </p>
      <ul>
        {duplicates.map((item) => (
          <li key={item.revision_id}>
            <a href={"#/library/" + item.asset_id}>
              {item.title} · v{item.version}
              {item.archived ? "（已归档）" : ""}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function LibraryDetail({
  id,
  client,
  initialDuplicates = [],
}: {
  id: string;
  client: QueryClient;
  initialDuplicates?: Duplicate[];
}) {
  const resource = useResource<Detail>(client, "/assets/" + id);
  const asset = resource.data;
  const [editing, setEditing] = useState(false),
    [uploading, setUploading] = useState(false),
    [preview, setPreview] = useState<string | null>(null);
  const [duplicates, setDuplicates] = useState(initialDuplicates);
  const { act, busy, error } = useAsyncAction();
  const saved = (asset: Detail) => {
    client.invalidate("/assets?");
    client.set("/assets/" + id, asset);
    setEditing(false);
  };
  if (!asset)
    return (
      <div className="library-page">
        <a className="back-link" href="#/library">
          返回资料中心
        </a>
        <p role={resource.error ? "alert" : "status"}>
          {resource.error?.message || "正在读取资料…"}
        </p>
        {resource.error && (
          <button
            className="secondary"
            onClick={() => resource.reload().catch(() => {})}
          >
            重试
          </button>
        )}
      </div>
    );
  return (
    <div className="library-page">
      <a className="back-link" href="#/library">
        资料中心 / {asset.category || "未分类"}
      </a>
      <div className="page-heading">
        <div>
          <h1>{asset.title}</h1>
          <p>
            {asset.subject_name
              ? `${asset.subject_name}${asset.subject_label ? " · " + asset.subject_label : ""}`
              : "收集箱 · 尚未指定主体"}
            {asset.subject_archived ? " · 主体已归档" : ""}
            {asset.archived ? " · 资料已归档" : ""}
          </p>
        </div>
        <div className="library-actions">
          {asset.archived && (
            <button
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    "永久清除这份已归档资料？仍有事项或冻结包引用时会被阻止。已导出的备份和外部副本不随之删除。",
                  )
                )
                  act(async () => {
                    await api("/assets/" + asset.id + "/purge", {
                      method: "DELETE",
                      body: JSON.stringify({ revision: asset.revision }),
                    });
                    client.invalidate("/assets?");
                    window.location.hash = "#/library";
                  });
              }}
            >
              永久清除
            </button>
          )}
          <button className="secondary" onClick={() => setEditing(true)}>
            整理资料
          </button>
          <button
            className="primary"
            disabled={asset.archived}
            onClick={() => setUploading(true)}
          >
            <Plus size={16} />
            上传新版本
          </button>
        </div>
      </div>
      {(error || resource.error) && (
        <p role="alert" className="form-error">
          {error || resource.error?.message}
        </p>
      )}
      <DuplicateNotice duplicates={duplicates} />
      <div className="library-detail-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>版本历史</h2>
              <p>旧版本和原件保持不变，事项不会自动改用新版本。</p>
            </div>
            <span>{asset.versions.length} 个版本</span>
          </div>
          {asset.versions.map((version) => (
            <article className="library-version" key={version.id}>
              <FileText size={22} />
              <div>
                <strong>
                  v{version.version} · {version.filename}
                </strong>
                <p>
                  {fileSize(version.size)} ·{" "}
                  {new Date(version.created_at).toLocaleString("zh-CN")}
                  {version.origin === "correction" ? " · 含校订文本" : ""}
                </p>
                {!version.available && <small>原件暂不可用</small>}
              </div>
              <button
                className="secondary"
                onClick={() => setPreview(version.id)}
              >
                查看版本
              </button>
            </article>
          ))}
        </section>
        <aside>
          <section className="panel library-usage">
            <h2>使用位置</h2>
            <p>显示仍在事项中保留的材料版本。</p>
            {asset.usages.length ? (
              <ul>
                {asset.usages.map((usage) => (
                  <li key={usage.document_id}>
                    <a href={"#/cases/" + usage.case_id + "/overview"}>
                      {usage.case_title}
                    </a>
                    <span>
                      资料 v{usage.version} ·{" "}
                      {usage.active ? "当前材料" : "历史材料"} ·{" "}
                      {usage.purpose === "source" ? "通知依据" : "申请材料"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>当前未用于任何事项。</p>
            )}
          </section>
          <section className="panel library-usage">
            <h2>保管与整理</h2>
            <p>
              从事项移除材料或删除事项后，资料中心仍保留原件。归档只隐藏资料，不删除版本。
            </p>
            <div className="library-actions">
              {asset.archived && (
                <button
                  disabled={busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "永久清除这份已归档资料？仍有事项或冻结包引用时会被阻止。已导出的备份和外部副本不随之删除。",
                      )
                    )
                      act(async () => {
                        await api("/assets/" + asset.id + "/purge", {
                          method: "DELETE",
                          body: JSON.stringify({ revision: asset.revision }),
                        });
                        client.invalidate("/assets?");
                        window.location.hash = "#/library";
                      });
                  }}
                >
                  永久清除
                </button>
              )}
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    saved(
                      await api<Detail>("/assets/" + id, {
                        method: "PATCH",
                        body: JSON.stringify({
                          revision: asset.revision,
                          title: asset.title,
                          category: asset.category,
                          subject_id: asset.subject_id,
                          archived: !asset.archived,
                        }),
                      }),
                    );
                  })
                }
              >
                <Archive size={16} />
                {asset.archived ? "恢复资料" : "归档资料"}
              </button>
              <button
                className="text-action"
                onClick={() => resource.reload().catch(() => {})}
              >
                <RefreshCw size={15} />
                刷新
              </button>
            </div>
          </section>
        </aside>
      </div>
      {editing && (
        <AssetEditor
          asset={asset}
          close={() => setEditing(false)}
          saved={saved}
        />
      )}
      {uploading && (
        <UploadDialog
          asset={asset}
          close={() => setUploading(false)}
          saved={(result) => {
            saved(result.asset);
            setDuplicates(result.duplicates);
            setUploading(false);
          }}
        />
      )}
      {preview && (
        <VersionPreview
          id={preview}
          client={client}
          close={() => setPreview(null)}
        />
      )}
    </div>
  );
}
