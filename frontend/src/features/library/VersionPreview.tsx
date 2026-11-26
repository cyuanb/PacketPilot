import { useEffect, useState } from "react";
import type { QueryClient } from "../../app/queryClient";
import { useResource } from "../../app/useResource";
import { Dialog } from "../../components/Dialog";
import { fileSize, type LibraryVersion } from "./types";

export function VersionPreview({
  id,
  client,
  close,
}: {
  id: string;
  client: QueryClient;
  close: () => void;
}) {
  const resource = useResource<LibraryVersion>(
    client,
    "/asset-revisions/" + id,
  );
  const version = resource.data;
  const [text, setText] = useState<string | null>(null),
    [error, setError] = useState("");
  const url = "/api/v1/asset-revisions/" + id + "/content";
  const readText =
    !!version?.available &&
    !version.has_text_snapshot &&
    ["text/plain", "text/markdown"].includes(version.mime);
  useEffect(() => {
    const controller = new AbortController();
    setText(null);
    setError("");
    if (readText)
      fetch(url, { credentials: "same-origin", signal: controller.signal })
        .then(async (response) => {
          if (!response.ok) throw new Error("原件暂时无法读取，请重试");
          const bytes = await response.arrayBuffer();
          if (controller.signal.aborted) return;
          try {
            setText(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
          } catch {
            setError("此文件无法按 UTF-8 预览，请下载原件查看。");
          }
        })
        .catch((error) => {
          if (!controller.signal.aborted) setError(error.message);
        });
    return () => controller.abort();
  }, [url, readText]);
  return (
    <Dialog
      title={version ? `${version.filename} · v${version.version}` : "资料版本"}
      close={close}
      error={resource.error?.message || error}
      wide
    >
      {!version ? (
        <p>正在读取版本信息…</p>
      ) : (
        <>
          <div className="preview-meta">
            <span>{fileSize(version.size)}</span>
            <span>{new Date(version.created_at).toLocaleString("zh-CN")}</span>
            {version.available && (
              <a
                className="text-action"
                href={url}
                target="_blank"
                rel="noreferrer"
              >
                打开或下载原件
              </a>
            )}
          </div>
          {!version.available && (
            <p className="form-error">
              原件暂不可用。已保存的版本信息与文本快照仍保留，请检查本地文件或提供新版本。
            </p>
          )}
          {version.origin === "correction" && (
            <p className="subtle-note">
              下方为本次校订文本；原始文件未被改写。
            </p>
          )}
          {version.has_text_snapshot && version.origin !== "correction" && (
            <p className="subtle-note">
              下方为此前保留的文本快照，可能不完整，请结合原件核对。
            </p>
          )}
          {!!version.text_snapshot?.length ? (
            version.text_snapshot.map((page) => (
              <section key={page.number} className="preview-page">
                <h4>{page.label}</h4>
                <pre>{page.text}</pre>
              </section>
            ))
          ) : readText ? (
            <section className="preview-page">
              <pre>
                {error
                  ? "请通过原件链接下载查看。"
                  : text === null
                    ? "正在读取原件文本…"
                    : text || "文件中没有可显示的文本。"}
              </pre>
            </section>
          ) : version.available && version.mime === "application/pdf" ? (
            <iframe className="library-pdf" title="PDF 原件预览" src={url} />
          ) : version.available && version.mime.startsWith("image/") ? (
            <img className="library-image" alt={version.filename} src={url} />
          ) : (
            <p>此格式可通过原件链接下载查看；保存文件不代表已完成内容解析。</p>
          )}
          <details className="library-hash">
            <summary>文件校验信息</summary>
            <code>SHA-256: {version.sha256}</code>
          </details>
        </>
      )}
      {resource.error && (
        <button
          className="secondary"
          onClick={() => resource.reload().catch(() => {})}
        >
          重试
        </button>
      )}
    </Dialog>
  );
}
