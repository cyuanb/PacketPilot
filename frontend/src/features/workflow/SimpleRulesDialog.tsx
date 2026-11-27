import { useEffect, useRef, useState } from "react";
import { api, post } from "../../api/client";
import type { Case, Doc, Requirement } from "../../api/types";
import { useAsyncAction } from "../../app/useAsyncAction";
import { Dialog } from "../../components/Dialog";

type Row = {
  id: string;
  title: string;
  document_type: string;
  kind: string;
  field: string;
  parameter: string;
  quote: string;
  required: boolean;
  source_id: string;
  page: number;
};
const kinds: Record<string, string> = {
  material_presence: "材料存在（有限结构核对）",
  required_field: "必填字段",
  file_format: "文件格式",
  file_size: "文件大小",
  page_count: "PDF 页数",
  date_constraint: "日期不早于",
  manual_review: "本人查看原件确认",
  semantic_requirement: "内容语义核对（需要模型）",
};
const makeRow = (): Row => ({
  id: crypto.randomUUID(),
  title: "",
  document_type: "",
  kind: "required_field",
  field: "",
  parameter: "",
  quote: "",
  required: true,
  source_id: "",
  page: 1,
});

export function SimpleRulesDialog({
  item,
  close,
  saved,
}: {
  item: Case;
  close: () => void;
  saved: () => Promise<void>;
}) {
  const sources = (item.documents || []).filter(
    (d) => d.purpose === "source" && d.parse_status === "ready",
  );
  const [sourceId, setSourceId] = useState(sources[0]?.id || ""),
    [source, setSource] = useState<Doc | null>(null),
    [page, setPage] = useState(1),
    [rows, setRows] = useState<Row[]>([makeRow()]);
  const excerpt = useRef<HTMLTextAreaElement>(null);
  const firstSource = sources[0]?.id;
  useEffect(() => {
    if (!sourceId && firstSource) setSourceId(firstSource);
  }, [sourceId, firstSource]);
  const { busy, error, setError, act, isCurrent } = useAsyncAction();
  useEffect(() => {
    if (!sourceId) return;
    const controller = new AbortController();
    setSource(null);
    setError("");
    api<Doc>("/documents/" + sourceId, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) {
          setSource(value);
          setPage(value.pages[0]?.number || 1);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message);
      });
    return () => controller.abort();
  }, [sourceId, setError]);
  const pageText = source?.pages.find((p) => p.number === page)?.text || "";
  const update = (index: number, value: Partial<Row>) =>
    setRows(rows.map((row, i) => (i === index ? { ...row, ...value } : row)));
  return (
    <Dialog
      title="根据通知建立要求草稿"
      close={close}
      busy={busy}
      error={error}
      wide
    >
      <p className="dialog-intro">
        以接收方通知为依据填写简单要求。场景中的资料建议不是正式清单；每项须引用原文。保存后还需要审阅并启用。
      </p>
      {!sources.length ? (
        <p>先导入可读通知，或提供通知的校订文本。</p>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            act(async () => {
              const requirements: Requirement[] = rows.map((row) => {
                const parameters: Record<string, unknown> = {};
                if (["required_field", "date_constraint"].includes(row.kind)) {
                  if (!row.field.trim())
                    throw new Error("请填写要核对的字段名");
                  parameters.field = row.field.trim();
                }
                if (row.kind === "date_constraint")
                  parameters.not_before = row.parameter;
                if (row.kind === "file_format") {
                  parameters.allowed = row.parameter
                    .split(/[,，\s]+/)
                    .filter(Boolean)
                    .map((value) => value.replace(/^\./, ""));
                  if (!(parameters.allowed as string[]).length)
                    throw new Error("请填写允许的文件扩展名");
                }
                if (["file_size", "page_count"].includes(row.kind)) {
                  const value = Number(row.parameter);
                  if (
                    !Number.isFinite(value) ||
                    value <= 0 ||
                    (row.kind === "page_count" && !Number.isInteger(value))
                  )
                    throw new Error("大小和页数需要填写有效正数");
                  parameters[
                    row.kind === "file_size" ? "max_bytes" : "max_pages"
                  ] =
                    row.kind === "file_size"
                      ? Math.round(value * 1024 * 1024)
                      : value;
                }
                return {
                  id: row.id,
                  title: row.title,
                  document_type: row.document_type,
                  kind: row.kind,
                  parameters,
                  required: row.required,
                  condition: {},
                  explanation: "用户依据原文确认的简单要求",
                  source_evidence: [
                    {
                      document_id: row.source_id || sourceId,
                      page: row.page,
                      quote: row.quote,
                    },
                  ],
                };
              });
              await post(`/cases/${item.id}/rule-sets`, {
                revision: item.revision,
                requirements,
              });
              await saved();
              if (isCurrent()) close();
            });
          }}
        >
          <div className="form-row">
            <label>
              通知来源
              <select
                value={sourceId}
                onChange={(event) => setSourceId(event.target.value)}
              >
                {sources.map((source) => (
                  <option value={source.id} key={source.id}>
                    {source.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              引用位置
              <select
                value={page}
                onChange={(event) => setPage(Number(event.target.value))}
              >
                {source?.pages.map((page) => (
                  <option value={page.number} key={page.number}>
                    {page.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            通知原文（可选择文字后引用）
            <textarea ref={excerpt} readOnly value={pageText} rows={6} />
          </label>
          <p className="hint">
            每条引用会绑定填写时的通知和位置；切换上方来源不会改写已经填写的引用。
          </p>
          {rows.map((row, index) => (
            <fieldset className="simple-rule" key={row.id}>
              <legend>要求 {index + 1}</legend>
              <label>
                要求标题
                <input
                  required
                  maxLength={200}
                  value={row.title}
                  onChange={(event) =>
                    update(index, { title: event.target.value })
                  }
                />
              </label>
              <div className="form-row">
                <label>
                  对应材料
                  <input
                    required
                    maxLength={100}
                    list="simple-material-options"
                    value={row.document_type}
                    onChange={(event) =>
                      update(index, { document_type: event.target.value })
                    }
                  />
                </label>
                <label>
                  核对方式
                  <select
                    value={row.kind}
                    onChange={(event) =>
                      update(index, { kind: event.target.value, parameter: "" })
                    }
                  >
                    {Object.entries(kinds).map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {["required_field", "date_constraint"].includes(row.kind) && (
                <label>
                  字段名称
                  <input
                    required
                    maxLength={100}
                    placeholder="例如：姓名、签发日期"
                    value={row.field}
                    onChange={(event) =>
                      update(index, { field: event.target.value })
                    }
                  />
                </label>
              )}
              {[
                "file_format",
                "file_size",
                "page_count",
                "date_constraint",
              ].includes(row.kind) && (
                <label>
                  {row.kind === "file_format"
                    ? "允许格式（逗号分隔）"
                    : row.kind === "file_size"
                      ? "大小上限（MiB）"
                      : row.kind === "page_count"
                        ? "页数上限"
                        : "不早于日期"}
                  <input
                    required
                    type={row.kind === "date_constraint" ? "date" : "text"}
                    value={row.parameter}
                    onChange={(event) =>
                      update(index, { parameter: event.target.value })
                    }
                  />
                </label>
              )}
              <label>
                原文引用
                <textarea
                  required
                  maxLength={1000}
                  rows={2}
                  value={row.quote}
                  onChange={(event) =>
                    update(index, {
                      quote: event.target.value,
                      source_id: sourceId,
                      page,
                    })
                  }
                />
              </label>
              <small>
                引用：
                {sources.find((source) => source.id === row.source_id)?.title ||
                  "尚未填写"}{" "}
                · 位置 {row.page}
              </small>
              <div className="workflow-actions">
                <button
                  type="button"
                  className="text-action"
                  onClick={() => {
                    const element = excerpt.current;
                    const quote =
                      element?.value.slice(
                        element.selectionStart,
                        element.selectionEnd,
                      ) || "";
                    if (!quote.trim() || quote.length > 1000) {
                      setError(
                        "请在通知原文中选择 1～1000 个字符，或粘贴准确原文。",
                      );
                      return;
                    }
                    update(index, { quote, source_id: sourceId, page });
                  }}
                >
                  引用选中文字
                </button>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={row.required}
                    onChange={(event) =>
                      update(index, { required: event.target.checked })
                    }
                  />
                  必须满足
                </label>
                <button
                  type="button"
                  className="text-action"
                  disabled={rows.length === 1}
                  onClick={() => setRows(rows.filter((_, i) => i !== index))}
                >
                  移除此要求
                </button>
              </div>
            </fieldset>
          ))}
          <datalist id="simple-material-options">
            {item.scenario?.materials.map((name) => (
              <option value={name} key={name} />
            ))}
          </datalist>
          <button
            type="button"
            className="secondary"
            disabled={rows.length >= 80}
            onClick={() => setRows([...rows, makeRow()])}
          >
            添加要求
          </button>
          <div className="dialog-actions">
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={close}
            >
              取消
            </button>
            <button className="primary" disabled={busy || !source}>
              保存要求草稿
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
