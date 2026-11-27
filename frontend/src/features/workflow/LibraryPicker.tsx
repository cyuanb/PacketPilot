import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Case } from "../../api/types";
import { useAsyncAction } from "../../app/useAsyncAction";
import { Dialog } from "../../components/Dialog";
import type { LibraryDetail, LibraryList } from "../library/types";
import type { DocumentLink } from "./types";

export function LibraryPicker({
  item,
  purpose,
  link,
  close,
  saved,
}: {
  item: Case;
  purpose: "source" | "material";
  link?: DocumentLink;
  close: () => void;
  saved: () => Promise<void>;
}) {
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [assets, setAssets] = useState<LibraryList | null>(null);
  const [assetId, setAssetId] = useState(link?.asset_id || ""),
    [detail, setDetail] = useState<LibraryDetail | null>(null);
  const [version, setVersion] = useState(""),
    [category, setCategory] = useState(link?.category || ""),
    [loading, setLoading] = useState(false),
    [loadError, setLoadError] = useState("");
  const { busy, error, act, isCurrent } = useAsyncAction();
  useEffect(() => {
    if (link) return;
    const controller = new AbortController();
    setLoadError("");
    api<LibraryList>("/assets?limit=100&q=" + encodeURIComponent(search), {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setAssets(value);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setLoadError(error.message);
      });
    return () => controller.abort();
  }, [search, attempt, link]);
  useEffect(() => {
    if (!assetId) return;
    const controller = new AbortController();
    setLoading(true);
    setDetail(null);
    setVersion("");
    setLoadError("");
    api<LibraryDetail>("/assets/" + assetId, { signal: controller.signal })
      .then((value) => {
        if (controller.signal.aborted) return;
        setDetail(value);
        setVersion(link?.asset_revision_id || value.latest?.id || "");
        if (!link) setCategory(value.category);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setLoadError(error.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [assetId, link?.asset_revision_id]);
  const selected = detail?.versions.find((value) => value.id === version);
  return (
    <Dialog
      title={
        link
          ? "选择此事项使用的资料版本"
          : purpose === "source"
            ? "从资料中心选择通知"
            : "从资料中心添加材料"
      }
      close={close}
      busy={busy}
      error={error || loadError}
      wide
    >
      <p className="dialog-intro">
        只固定本事项的版本，资料库和其他事项不会自动跟随更新。选择新的通知版本后，需要重新确认并启用要求。
      </p>
      {!link && (
        <>
          <form
            className="workflow-search"
            onSubmit={(event) => {
              event.preventDefault();
              setSearch(query);
              setAttempt((value) => value + 1);
            }}
          >
            <input
              aria-label="查找资料"
              maxLength={100}
              placeholder="按资料名称或分类查找"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <button className="secondary">查找</button>
          </form>
          <label>
            选择资料
            <select
              value={assetId}
              onChange={(event) => setAssetId(event.target.value)}
            >
              <option value="">请选择资料</option>
              {assets?.items.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.title} · {asset.subject_name || "未指定主体"} ·{" "}
                  {asset.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          {assets && assets.total > 100 && (
            <p>匹配超过 100 份，请输入更具体的关键词。</p>
          )}
          {assets?.total === 0 && (
            <p>
              没有匹配资料。<a href="#/library">前往资料中心上传</a>
            </p>
          )}
        </>
      )}
      {loading && <p role="status">正在读取版本…</p>}
      {detail && (
        <>
          <h3>{detail.title}</h3>
          <label>
            固定使用的版本
            <select
              value={version}
              onChange={(event) => setVersion(event.target.value)}
            >
              {detail.versions.map((v) => (
                <option key={v.id} value={v.id} disabled={!v.available}>
                  v{v.version} · {v.filename}
                  {v.id === link?.asset_revision_id ? "（当前）" : ""}
                  {!v.available ? "（原件不可用）" : ""}
                </option>
              ))}
            </select>
          </label>
          {selected && (
            <p className="hint">
              选择版本 v{selected.version}；最新为 v{detail.latest?.version}。
              {selected.origin === "correction"
                ? "此版本含人工校订文本。"
                : "文件会在本事项中读取，解析状态单独保留。"}
            </p>
          )}
          {!link && purpose === "material" && (
            <label>
              本事项的材料分类
              <input
                value={category}
                maxLength={100}
                list="scenario-material-options"
                onChange={(event) => setCategory(event.target.value)}
                placeholder="如简历、成绩单、营业执照；分类仍需结合原文核对"
              />
              <datalist id="scenario-material-options">
                {item.scenario?.materials.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </label>
          )}
          <div className="dialog-actions">
            <button className="secondary" disabled={busy} onClick={close}>
              取消
            </button>
            <button
              className="primary"
              disabled={
                busy ||
                !selected?.available ||
                detail.archived ||
                (link && version === link.asset_revision_id)
              }
              onClick={() =>
                act(async () => {
                  await api(
                    link
                      ? `/documents/${link.document_id}/library-version`
                      : `/cases/${item.id}/document-links`,
                    {
                      method: "POST",
                      body: JSON.stringify({
                        revision: item.revision,
                        asset_revision_id: version,
                        purpose,
                        category,
                      }),
                    },
                  );
                  await saved();
                  if (isCurrent()) close();
                })
              }
            >
              {link ? "确认切换此事项版本" : "加入此事项"}
            </button>
          </div>
        </>
      )}
    </Dialog>
  );
}
