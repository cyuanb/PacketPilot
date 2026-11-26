import { FileText, Inbox, Plus, Search } from "lucide-react";
import { useState } from "react";
import type { QueryClient } from "../../app/queryClient";
import { useResource } from "../../app/useResource";
import { Empty } from "../../components/Empty";
import { DuplicateNotice } from "./LibraryDetail";
import { UploadDialog } from "./UploadDialog";
import { fileSize, type Duplicate, type LibraryList } from "./types";

export function LibraryPage({
  client,
  inbox,
}: {
  client: QueryClient;
  inbox: boolean;
}) {
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [category, setCategory] = useState(""),
    [filterCategory, setFilterCategory] = useState("");
  const [archived, setArchived] = useState(false),
    [offset, setOffset] = useState(0),
    [uploading, setUploading] = useState(false),
    [duplicates, setDuplicates] = useState<Duplicate[]>([]);
  const resource = useResource<LibraryList>(
    client,
    `/assets?inbox=${inbox}&include_archived=${archived}&q=${encodeURIComponent(search)}&category=${encodeURIComponent(filterCategory)}&limit=40&offset=${offset}`,
  );
  return (
    <div className="library-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">DOCUMENT LIBRARY</div>
          <h1>{inbox ? "收集箱" : "资料中心"}</h1>
          <p>
            {inbox
              ? "先保存原件，再确认资料属于谁。指定主体后会移出收集箱。"
              : "独立保管个人与组织资料，保留每个原件版本和使用位置。"}
          </p>
        </div>
        <button className="primary" onClick={() => setUploading(true)}>
          <Plus size={18} />
          上传资料
        </button>
      </div>
      <DuplicateNotice duplicates={duplicates} />
      <form
        className="library-filters"
        onSubmit={(event) => {
          event.preventDefault();
          setSearch(query);
          setFilterCategory(category);
          setOffset(0);
        }}
      >
        <label className="search-box">
          <Search size={16} />
          <input
            aria-label="搜索资料"
            maxLength={100}
            placeholder="资料名称或分类"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          分类
          <input
            maxLength={100}
            placeholder="全部分类"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          />
        </label>
        <button className="secondary">筛选</button>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={archived}
            onChange={(event) => {
              setArchived(event.target.checked);
              setOffset(0);
            }}
          />
          包含已归档
        </label>
      </form>
      {resource.error && (
        <p role="alert" className="form-error">
          {resource.error.message}
          <button
            className="text-action"
            onClick={() => resource.reload().catch(() => {})}
          >
            重试
          </button>
        </p>
      )}
      {resource.pending && <p role="status">正在读取资料…</p>}
      <div className="library-grid">
        {resource.data?.items.map((asset) => (
          <a
            className="panel library-card"
            href={"#/library/" + asset.id}
            key={asset.id}
          >
            <div className="library-card-top">
              <FileText size={24} />
              <span>
                {asset.archived
                  ? "已归档"
                  : asset.inbox
                    ? "待确认主体"
                    : asset.category || "未分类"}
              </span>
            </div>
            <h2>{asset.title}</h2>
            <small>资料标识 {asset.id.slice(0, 8)}</small>
            <p>
              {asset.subject_name || "尚未指定主体"}
              {asset.subject_label ? " · " + asset.subject_label : ""}
            </p>
            <div className="library-card-meta">
              <span>
                v{asset.latest?.version || "—"} ·{" "}
                {fileSize(asset.latest?.size || 0)}
              </span>
              <span>{asset.case_count} 个事项使用</span>
            </div>
            {asset.latest && !asset.latest.available && (
              <small>原件暂不可用，可查看版本记录</small>
            )}
          </a>
        ))}
      </div>
      {!resource.pending && resource.data?.total === 0 && (
        <Empty
          icon={<Inbox size={30} />}
          title={
            search || filterCategory
              ? "没有匹配的资料"
              : inbox
                ? "收集箱为空"
                : "把第一份资料放进来"
          }
          text="可以直接上传文件，也可在事项中上传。相同内容会提示重复，不会自动合并或覆盖版本。"
        />
      )}
      {resource.data && resource.data.total > 0 && (
        <div className="subject-pagination">
          <span>
            共 {resource.data.total} 份 · 第 {Math.floor(offset / 40) + 1} 页
          </span>
          <button
            className="secondary"
            disabled={!offset || resource.pending}
            onClick={() => setOffset(offset - 40)}
          >
            上一页
          </button>
          <button
            className="secondary"
            disabled={offset + 40 >= resource.data.total || resource.pending}
            onClick={() => setOffset(offset + 40)}
          >
            下一页
          </button>
        </div>
      )}
      {uploading && (
        <UploadDialog
          close={() => setUploading(false)}
          saved={(result) => {
            setUploading(false);
            setDuplicates(result.duplicates);
            client.set("/assets/" + result.asset.id, result.asset);
            client.invalidate("/assets?");
            resource.reload().catch(() => {});
          }}
        />
      )}
    </div>
  );
}
