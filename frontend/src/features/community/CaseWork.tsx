import { useEffect, useState } from "react";
import { api, post, type Case } from "../../api";

type Work = {
  id: string;
  kind: string;
  title: string;
  status: string;
  note?: string;
  due_at?: string | null;
  timezone?: string;
  reminder_minutes?: number;
  revision: number;
  reminder: boolean;
  overdue: boolean;
};
const labels: Record<string, string> = {
  task: "行动任务",
  question: "待答问题",
  suggestion: "待审阅建议",
  deadline: "外部截止",
  expiry: "资料到期",
  draft: "工作草稿",
};
const statuses: Record<string, string> = {
  todo: "待处理",
  doing: "进行中",
  waiting: "等待输入",
  done: "已完成/已采纳",
  dismissed: "已取消/不采纳",
};
export function CaseWork({ item }: { item: Case }) {
  const [rows, setRows] = useState<Work[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [history, setHistory] = useState("");
  const [editing, setEditing] = useState<Work | null>(null);
  const [draft, setDraft] = useState({
    kind: "task",
    title: "",
    note: "",
    due_at: "",
    reminder_minutes: 1440,
  });
  const load = async () => setRows(await api<Work[]>(`/cases/${item.id}/work`));
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [item.id]);
  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await work();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel community-panel">
      <h2>任务计划与期限</h2>
      <p>
        任务、待答问题和草稿保存在服务端。采纳建议不会自动改写背景、材料或检查结论。
      </p>
      <div className="workflow-actions">
        <button
          disabled={busy}
          onClick={() =>
            act(async () => {
              await post(`/cases/${item.id}/work/suggest`);
            })
          }
        >
          从当前问题生成待审阅建议
        </button>
        <a href={`/api/v1/cases/${item.id}/calendar.ics`}>导出日历</a>
        <button onClick={() => load()}>刷新</button>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          act(async () => {
            const body = {
              ...draft,
              status: editing?.status || "todo",
              revision: editing?.revision,
              due_at: draft.due_at
                ? new Date(draft.due_at).toISOString()
                : null,
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            };
            if (editing)
              await api(`/work/${editing.id}`, {
                method: "PUT",
                body: JSON.stringify(body),
              });
            else await post(`/cases/${item.id}/work`, body);
            setEditing(null);
            setDraft({ ...draft, title: "", note: "" });
          });
        }}
      >
        <div className="form-grid">
          <label>
            类型
            <select
              value={draft.kind}
              onChange={(e) => setDraft({ ...draft, kind: e.target.value })}
            >
              {Object.entries(labels).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label>
            标题
            <input
              required
              value={draft.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            />
          </label>
          <label>
            时间（本机时区）
            <input
              type="datetime-local"
              value={draft.due_at}
              onChange={(e) => setDraft({ ...draft, due_at: e.target.value })}
            />
          </label>
          <label>
            提前提醒分钟
            <input
              type="number"
              min="0"
              value={draft.reminder_minutes}
              onChange={(e) =>
                setDraft({ ...draft, reminder_minutes: Number(e.target.value) })
              }
            />
          </label>
        </div>
        <label>
          说明/待答内容/草稿
          <textarea
            value={draft.note}
            onChange={(e) => setDraft({ ...draft, note: e.target.value })}
          />
        </label>
        <button className="primary" disabled={busy}>
          保存任务或草稿
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {rows.map((w) => (
        <article className="work-card" key={w.id}>
          <button
            onClick={() => {
              setEditing(w);
              const d = w.due_at ? new Date(w.due_at) : null;
              setDraft({
                kind: w.kind,
                title: w.title,
                note: w.note || "",
                due_at: d
                  ? new Date(d.getTime() - d.getTimezoneOffset() * 60000)
                      .toISOString()
                      .slice(0, 16)
                  : "",
                reminder_minutes: w.reminder_minutes ?? 1440,
              });
            }}
          >
            编辑/继续草稿
          </button>
          <h3>
            {w.title} <small>{labels[w.kind]}</small>
          </h3>
          <p className={w.overdue ? "warning-text" : ""}>
            {w.due_at ? new Date(w.due_at).toLocaleString() : "无期限"}{" "}
            {w.overdue ? "已逾期" : w.reminder ? "进入提醒期" : ""}
          </p>
          <p className="preserve-text">{w.note}</p>
          <select
            aria-label={`${w.title}状态`}
            value={w.status}
            disabled={busy}
            onChange={(e) =>
              act(async () => {
                await api(`/work/${w.id}`, {
                  method: "PUT",
                  body: JSON.stringify({
                    kind: w.kind,
                    title: w.title,
                    note: w.note || "",
                    due_at: w.due_at || null,
                    timezone: w.timezone || "Asia/Shanghai",
                    reminder_minutes: w.reminder_minutes ?? 1440,
                    status: e.target.value,
                    revision: w.revision,
                  }),
                });
              })
            }
          >
            {Object.entries(statuses).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <button
            onClick={() =>
              act(async () =>
                setHistory(
                  JSON.stringify(await api(`/work/${w.id}/history`), null, 2),
                ),
              )
            }
          >
            查看变更记录
          </button>
        </article>
      ))}
      {history && (
        <details open>
          <summary>任务历史</summary>
          <pre>{history}</pre>
        </details>
      )}
    </section>
  );
}

export function ProcessingPanel({
  item,
  refresh,
}: {
  item: Case;
  refresh: () => Promise<void>;
}) {
  const [selected, setSelected] = useState<
      { document_id: string; pages: string; rotation: number }[]
    >([]),
    [title, setTitle] = useState("加工材料"),
    [operation, setOperation] = useState("pdf"),
    [size, setSize] = useState(1600),
    [quality, setQuality] = useState(85),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  return (
    <section className="panel community-panel">
      <h2>材料加工</h2>
      <p>
        按选择顺序合并 PDF/图片，可按页拆分与旋转；图片可调整尺寸和 JPEG
        质量。输出另存为新资料，原件保持不变。
      </p>
      <label>
        成果名称
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        加工方式
        <select
          value={operation}
          onChange={(e) => setOperation(e.target.value)}
        >
          <option value="pdf">生成 PDF（合并/选页/旋转）</option>
          <option value="image">调整单张图片</option>
        </select>
      </label>
      {item.documents
        ?.filter((d) => d.purpose === "material" && /pdf|image\//.test(d.mime))
        .map((d) => (
          <label key={d.id}>
            <input
              type="checkbox"
              checked={selected.some((s) => s.document_id === d.id)}
              onChange={(e) =>
                setSelected(
                  e.target.checked
                    ? [
                        ...selected,
                        { document_id: d.id, pages: "", rotation: 0 },
                      ]
                    : selected.filter((s) => s.document_id !== d.id),
                )
              }
            />
            {d.title}
          </label>
        ))}
      {selected.map((s, i) => (
        <div className="form-grid work-card" key={s.document_id}>
          <strong>
            {i + 1} ·{" "}
            {item.documents?.find((d) => d.id === s.document_id)?.title}
          </strong>
          <label>
            页码（逗号分隔；留空全部）
            <input
              value={s.pages}
              onChange={(e) =>
                setSelected(
                  selected.map((v, j) =>
                    j === i ? { ...v, pages: e.target.value } : v,
                  ),
                )
              }
            />
          </label>
          <label>
            顺时针旋转
            <select
              value={s.rotation}
              onChange={(e) =>
                setSelected(
                  selected.map((v, j) =>
                    j === i ? { ...v, rotation: Number(e.target.value) } : v,
                  ),
                )
              }
            >
              {[0, 90, 180, 270].map((v) => (
                <option value={v} key={v}>
                  {v}°
                </option>
              ))}
            </select>
          </label>
          <button
            disabled={i === 0}
            onClick={() => {
              const next = [...selected];
              [next[i - 1], next[i]] = [next[i], next[i - 1]];
              setSelected(next);
            }}
          >
            上移
          </button>
        </div>
      ))}
      {operation === "image" && (
        <div className="form-grid">
          <label>
            最长边像素
            <input
              type="number"
              min="300"
              max="4000"
              value={size}
              onChange={(e) => setSize(Number(e.target.value))}
            />
          </label>
          <label>
            JPEG 质量
            <input
              type="number"
              min="40"
              max="95"
              value={quality}
              onChange={(e) => setQuality(Number(e.target.value))}
            />
          </label>
        </div>
      )}
      <button
        className="primary"
        disabled={busy || !selected.length}
        onClick={async () => {
          setBusy(true);
          try {
            await post(`/cases/${item.id}/derivatives`, {
              revision: item.revision,
              title,
              operation,
              max_dimension: size,
              quality,
              selections: selected.map((s) => ({
                ...s,
                pages: s.pages ? s.pages.split(/[,，]/).map(Number) : [],
              })),
            });
            await refresh();
            setMessage("已生成新材料并加入解析队列，请预览核对。");
          } catch (e) {
            setMessage(e instanceof Error ? e.message : "加工失败");
          } finally {
            setBusy(false);
          }
        }}
      >
        生成独立派生文件
      </button>
      <p role="status">{message}</p>
    </section>
  );
}
