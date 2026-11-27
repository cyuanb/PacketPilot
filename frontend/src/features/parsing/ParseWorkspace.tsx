import { useEffect, useState } from "react";
import { api, post, type Case } from "../../api";

type Region = {
  id: string;
  text: string;
  confidence?: number;
  box: number[][];
  confirmed?: boolean;
};
type Page = {
  number: number;
  text: string;
  label: string;
  status?: string;
  method?: string;
  regions?: Region[];
};
type Field = {
  id: string;
  label: string;
  value: string;
  page: number;
  confirmed: boolean;
  region_id?: string;
};
type Parse = {
  id: string;
  version: number;
  method: string;
  status: string;
  pages: Page[];
  fields: Field[];
  note: string;
  created_at: string;
};
type History = { current_parse_id: string; items: Parse[] };
type Capability = {
  available: boolean;
  scope: string;
  max_pages: number;
  models_ready: boolean;
  enabled: boolean;
};

export function ParseWorkspace({
  item,
  refresh,
}: {
  item: Case;
  refresh: () => Promise<void>;
}) {
  const [documentId, setDocumentId] = useState(item.documents?.[0]?.id || "");
  const [history, setHistory] = useState<History | null>(null);
  const [selected, setSelected] = useState("");
  const [pageNumber, setPageNumber] = useState(1);
  const [highlight, setHighlight] = useState("");
  const [text, setText] = useState("");
  const [fieldId, setFieldId] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [capability, setCapability] = useState<Capability | null>(null);
  const doc = item.documents?.find((d) => d.id === documentId);
  const parsed = history?.items.find((p) => p.id === selected);
  const page = parsed?.pages.find((p) => p.number === pageNumber);
  const current = selected === history?.current_parse_id;
  useEffect(() => {
    let live = true;
    api<Capability>("/capabilities/ocr")
      .then((c) => {
        if (live) setCapability(c);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    if (!item.documents?.some((d) => d.id === documentId))
      setDocumentId(item.documents?.[0]?.id || "");
  }, [item.documents, documentId]);
  useEffect(() => {
    let live = true;
    setHistory(null);
    setError("");
    if (documentId)
      api<History>(`/documents/${documentId}/parses`)
        .then((h) => {
          if (live) {
            setHistory(h);
            setSelected(h.current_parse_id);
            setPageNumber(h.items[0]?.pages[0]?.number || 1);
          }
        })
        .catch((e) => {
          if (live) setError(e.message);
        });
    return () => {
      live = false;
    };
  }, [documentId, item.revision, retry]);
  useEffect(() => {
    setText(page?.text || "");
    setFieldId("");
    setHighlight("");
    setConfirm(false);
  }, [page, selected]);
  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };
  const image = doc && /pdf|image\//.test(doc.mime);
  return (
    <section className="panel parse-workspace">
      <div className="panel-header">
        <div>
          <h2>原件与解析校订</h2>
          <p>
            {capability?.available
              ? "本机 CPU OCR 已就绪"
              : "本机 OCR 暂不可用，仍可阅读原件和人工校订"}
          </p>
          <p className="hint">
            {capability?.scope}。扫描 PDF 每次最多识别{" "}
            {capability?.max_pages || 30} 页，其余页面保留待核对状态。
          </p>
        </div>
        <button onClick={() => setRetry((n) => n + 1)}>刷新解析状态</button>
      </div>
      <div className="parse-controls">
        <label>
          材料或通知
          <select
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
          >
            {item.documents?.map((d) => (
              <option value={d.id} key={d.id}>
                {d.title} · {d.purpose === "source" ? "通知" : "材料"}
              </option>
            ))}
          </select>
        </label>
        <label>
          解析历史
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            {history?.items.map((p) => (
              <option value={p.id} key={p.id}>
                v{p.version} · {p.method} · {p.status}
                {p.id === history.current_parse_id
                  ? "（当前）"
                  : "（历史只读）"}
              </option>
            ))}
          </select>
        </label>
        <label>
          页/段落
          <select
            value={pageNumber}
            onChange={(e) => setPageNumber(Number(e.target.value))}
          >
            {parsed?.pages.map((p) => (
              <option key={p.number} value={p.number}>
                {p.label} · {p.status || parsed.status}
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={!doc || busy || doc.parse_status === "queued"}
          onClick={() =>
            act(async () => {
              await post(`/documents/${documentId}/parses`, {
                revision: item.revision,
              });
              await refresh();
            })
          }
        >
          重新解析原件
        </button>
      </div>
      {parsed?.note && <p className="hint">{parsed.note}</p>}
      {doc?.purpose === "source" && (
        <p className="warning-text">
          通知解析变化后，引用旧解析的要求需要重新确认；历史检查引用仍保留。
        </p>
      )}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      {!doc && <p>先上传材料或通知。</p>}
      {doc && (
        <div className="parse-columns">
          <div className="original-pane">
            <h3>原件 · 第 {pageNumber} 页</h3>
            {image ? (
              <div className="page-canvas">
                <img
                  src={`/api/v1/documents/${documentId}/pages/${pageNumber}/image`}
                  alt={`${doc.title} 第 ${pageNumber} 页原件`}
                />
                {page?.regions
                  ?.filter((r) => r.box?.length)
                  .map((r) => {
                    const x = Math.min(...r.box.map((p) => p[0])),
                      y = Math.min(...r.box.map((p) => p[1]));
                    const right = Math.max(...r.box.map((p) => p[0])),
                      bottom = Math.max(...r.box.map((p) => p[1]));
                    return (
                      <button
                        key={r.id}
                        aria-label={`定位 ${r.text}`}
                        title={`${r.text} (${Math.round((r.confidence || 0) * 100)}%)`}
                        className={`ocr-region ${highlight === r.id ? "active" : ""}`}
                        style={{
                          left: `${x * 100}%`,
                          top: `${y * 100}%`,
                          width: `${(right - x) * 100}%`,
                          height: `${(bottom - y) * 100}%`,
                        }}
                        onClick={() => setHighlight(r.id)}
                      />
                    );
                  })}
              </div>
            ) : (
              <>
                <p>此格式提供原件下载和文本视图。</p>
                <a
                  href={`/api/v1/documents/${documentId}/content`}
                  target="_blank"
                  rel="noreferrer"
                >
                  查看/下载原件
                </a>
                <pre>{page?.text}</pre>
              </>
            )}
          </div>
          <div className="correction-pane">
            <h3>字段候选</h3>
            <p className="hint">
              候选来自当前解析，不自动视为已确认事实；点选字段可定位与单独校订。
            </p>
            <div className="field-candidates">
              {parsed?.fields
                .filter((f) => f.page === pageNumber)
                .map((f) => (
                  <button
                    key={f.id}
                    className={fieldId === f.id ? "selected" : ""}
                    onClick={() => {
                      setFieldId(f.id);
                      setText(f.value);
                      setHighlight(f.region_id || "");
                      setConfirm(false);
                    }}
                  >
                    <strong>{f.label}</strong>
                    <span>{f.value}</span>
                    <small>{f.confirmed ? "人工已确认" : "待确认候选"}</small>
                  </button>
                ))}
            </div>
            <button
              onClick={() => {
                setFieldId("");
                setText(page?.text || "");
              }}
            >
              校订整页文本
            </button>
            <label>
              {fieldId ? "字段值" : "本页文本"}
              <textarea
                rows={fieldId ? 3 : 13}
                value={text}
                readOnly={!current}
                onChange={(e) => setText(e.target.value)}
              />
            </label>
            {!fieldId && (
              <label>
                <input
                  type="checkbox"
                  checked={confirm}
                  disabled={!current}
                  onChange={(e) => setConfirm(e.target.checked)}
                />
                我已对照原件，确认本页全部内容已覆盖
              </label>
            )}
            <p className="hint">
              字段校订只确认这个字段；整页校订会清除旧区域定位。原件始终不变，校订结果保存为新的解析版本。
            </p>
            <button
              className="primary"
              disabled={
                busy ||
                !current ||
                !page ||
                !text.trim() ||
                doc.parse_status === "queued"
              }
              onClick={() =>
                act(async () => {
                  await post(`/documents/${documentId}/page-corrections`, {
                    revision: item.revision,
                    parse_revision_id: selected,
                    page: pageNumber,
                    field_id: fieldId,
                    text,
                    confirm_page: !fieldId && confirm,
                  });
                  await refresh();
                  setRetry((n) => n + 1);
                })
              }
            >
              保存校订版本
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
