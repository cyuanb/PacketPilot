import { useEffect, useState } from "react";
import { api, post, type Case } from "../../api";

type Entry = {
  document_id: string;
  path: string;
  content: "original" | "parsed_text";
};
type Packet = {
  id: string;
  title: string;
  sha256: string;
  created_at: string;
  changed: boolean;
  case_revision: number;
  manifest: {
    entries: (Entry & { sha256: string; size: number })[];
    warnings: string[];
  };
  diff: {
    added: string[];
    removed: string[];
    changed: string[];
    rules_changed: boolean;
    case_changed: boolean;
  };
  delivery_status: string;
  deliveries: {
    id: string;
    status: string;
    channel: string;
    recipient: string;
    reference: string;
    note: string;
    occurred_at: string;
  }[];
};
const states: Record<string, string> = {
  not_recorded: "未记录提交",
  submitted: "用户记录已提交",
  received: "用户记录已收到",
  returned: "用户记录退回",
};

export function PacketsPanel({ item }: { item: Case }) {
  const materials = (item.documents || []).filter(
    (d) => d.purpose === "material",
  );
  const [entries, setEntries] = useState<Entry[]>([]);
  const [title, setTitle] = useState(item.title + "材料包");
  const [packets, setPackets] = useState<Packet[]>([]);
  const [preview, setPreview] = useState<{
    warnings: string[];
    entries: (Entry & { size: number })[];
  } | null>(null);
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requestKey, setRequestKey] = useState(crypto.randomUUID());
  const [delivery, setDelivery] = useState("");
  const [event, setEvent] = useState({
    status: "submitted",
    channel: "",
    recipient: item.institution,
    reference: "",
    note: "",
    occurred_at: "",
  });
  const load = () =>
    api<Packet[]>(`/cases/${item.id}/packets`).then(setPackets);
  useEffect(() => {
    let active = true;
    api<Packet[]>(`/cases/${item.id}/packets`)
      .then((v) => {
        if (active) setPackets(v);
      })
      .catch((e) => {
        if (active) setError(String(e.message));
      });
    return () => {
      active = false;
    };
  }, [item.id, item.revision]);
  useEffect(() => {
    setPreview(null);
    setAck(false);
  }, [item.revision]);
  const change = (next: Entry[]) => {
    setEntries(next);
    setPreview(null);
    setAck(false);
    setRequestKey(crypto.randomUUID());
  };
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
  const body = {
    revision: item.revision,
    title,
    entries,
    request_key: requestKey,
    acknowledge_warnings: ack,
  };
  const move = (index: number, step: number) => {
    const next = [...entries];
    const to = index + step;
    if (to < 0 || to >= next.length) return;
    [next[index], next[to]] = [next[to], next[index]];
    change(next);
  };
  return (
    <div className="delivery-layout">
      <section className="panel delivery-builder">
        <h2>准备材料包</h2>
        <p className="hint">
          选择实际材料和版本，编辑包内目录与名称。冻结后内容不再变化；下载不会自动记录提交。
        </p>
        {item.scenario?.output && (
          <p className="hint">
            {item.scenario.title}建议：{item.scenario.output.naming}。
            {item.scenario.output.notice}
          </p>
        )}
        <label>
          材料包名称
          <input
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setPreview(null);
              setRequestKey(crypto.randomUUID());
            }}
          />
        </label>
        <div className="packet-select">
          {materials.map((d) => (
            <label key={d.id}>
              <input
                type="checkbox"
                checked={entries.some((e) => e.document_id === d.id)}
                onChange={(e) =>
                  change(
                    e.target.checked
                      ? [
                          ...entries,
                          {
                            document_id: d.id,
                            path: `${item.scenario?.output?.folder || "materials"}/${String(entries.length + 1).padStart(2, "0")}_${d.filename.replace(/[<>:"|?*\\/]/g, "_")}`,
                            content: "original",
                          },
                        ]
                      : entries.filter((v) => v.document_id !== d.id),
                  )
                }
              />
              {d.title} · v{d.version} ·{" "}
              {d.parse_status === "ready" ? "可读" : "待核对"}
            </label>
          ))}
        </div>
        {!materials.length && <p>先在材料库上传或引用材料。</p>}
        {entries.map((entry, index) => (
          <div className="packet-entry" key={entry.document_id}>
            <strong>{index + 1}</strong>
            <label>
              包内路径
              <input
                aria-label={`材料 ${index + 1} 路径`}
                value={entry.path}
                onChange={(e) =>
                  change(
                    entries.map((v, i) =>
                      i === index ? { ...v, path: e.target.value } : v,
                    ),
                  )
                }
              />
            </label>
            <label>
              内容
              <select
                value={entry.content}
                onChange={(e) =>
                  change(
                    entries.map((v, i) =>
                      i === index
                        ? {
                            ...v,
                            content: e.target.value as Entry["content"],
                            path:
                              e.target.value === "parsed_text"
                                ? v.path.replace(/\.[^/.]+$/, "") +
                                  "_解析文本.txt"
                                : `${item.scenario?.output?.folder || "materials"}/${materials.find((d) => d.id === v.document_id)?.filename}`,
                          }
                        : v,
                    ),
                  )
                }
              >
                <option value="original">原件</option>
                <option value="parsed_text">解析/校订文本（TXT）</option>
              </select>
            </label>
            <button onClick={() => move(index, -1)} disabled={index === 0}>
              ↑
            </button>
            <button
              onClick={() => move(index, 1)}
              disabled={index === entries.length - 1}
            >
              ↓
            </button>
          </div>
        ))}
        <div className="workflow-actions">
          <button
            disabled={busy || !entries.length || !title.trim()}
            onClick={() =>
              act(async () =>
                setPreview(
                  await post(`/cases/${item.id}/packets/preview`, body),
                ),
              )
            }
          >
            预览与校验
          </button>
          <button
            className="primary"
            disabled={busy || !preview || (preview.warnings.length > 0 && !ack)}
            onClick={() =>
              act(async () => {
                await post(`/cases/${item.id}/packets`, body);
                setPreview(null);
                setRequestKey(crypto.randomUUID());
                await load();
              })
            }
          >
            冻结材料包
          </button>
        </div>
        {preview && (
          <div className="packet-preview">
            <h3>冻结前核对</h3>
            <p>
              {preview.entries.length} 个文件，共{" "}
              {Math.round(
                preview.entries.reduce((n, e) => n + e.size, 0) / 1024,
              )}{" "}
              KiB；将附目录与 SHA256 清单。
            </p>
            {preview.warnings.map((w) => (
              <p key={w} className="warning-text">
                {w}
              </p>
            ))}
            {!!preview.warnings.length && (
              <label>
                <input
                  type="checkbox"
                  checked={ack}
                  onChange={(e) => setAck(e.target.checked)}
                />
                我已核对提示，仍需保留当前材料版本
              </label>
            )}
          </div>
        )}
        {error && (
          <p role="alert" className="error-text">
            {error}
          </p>
        )}
      </section>
      <section className="panel">
        <h2>冻结与交付历史</h2>
        {!packets.length && <p className="hint">尚无冻结材料包。</p>}
        {packets.map((p) => (
          <article className="frozen-packet" key={p.id}>
            <h3>{p.title}</h3>
            <p>
              {new Date(p.created_at).toLocaleString()} · 事项版本{" "}
              {p.case_revision} · {states[p.delivery_status]}
            </p>
            <code className="hash-line">SHA256 {p.sha256}</code>
            {p.changed && (
              <p className="warning-text">
                当前事项已变化，冻结包保持原样。新增 {p.diff.added.length}、移除{" "}
                {p.diff.removed.length}、内容/归属变化 {p.diff.changed.length}{" "}
                项；{p.diff.rules_changed ? "要求版本已改变。" : ""}
                需要新版本时重新生成包。
              </p>
            )}
            <details>
              <summary>文件目录与冻结提示</summary>
              {p.manifest.entries.map((e) => (
                <p key={e.path}>
                  {e.path} · {e.content === "original" ? "原件" : "派生文本"} ·{" "}
                  {e.size} bytes
                </p>
              ))}
              {p.manifest.warnings.map((w) => (
                <p key={w}>{w}</p>
              ))}
            </details>
            <div className="workflow-actions">
              <a
                className="button secondary"
                href={`/api/v1/packets/${p.id}/download`}
              >
                下载冻结包
              </a>
              <button
                onClick={() => {
                  setDelivery(delivery === p.id ? "" : p.id);
                  setEvent({
                    status: "submitted",
                    channel: "",
                    recipient: item.institution,
                    reference: "",
                    note: "",
                    occurred_at: "",
                  });
                }}
              >
                记录交付/回执
              </button>
            </div>
            {p.deliveries.map((e) => (
              <div className="delivery-event" key={e.id}>
                <strong>{states[e.status]}</strong>
                <span>
                  {new Date(e.occurred_at).toLocaleString()} · {e.channel} →{" "}
                  {e.recipient}
                </span>
                <p>
                  {e.reference} {e.note}
                </p>
              </div>
            ))}
            {delivery === p.id && (
              <form
                className="delivery-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(async () => {
                    await post(`/packets/${p.id}/deliveries`, {
                      ...event,
                      occurred_at: new Date(event.occurred_at).toISOString(),
                    });
                    setDelivery("");
                    await load();
                  });
                }}
              >
                <p className="hint">
                  这是你的人工记录，不会发送文件或向接收方查询。
                </p>
                <label>
                  状态
                  <select
                    value={event.status}
                    onChange={(e) =>
                      setEvent({ ...event, status: e.target.value })
                    }
                  >
                    <option value="submitted">已提交</option>
                    <option value="received">收到回执</option>
                    <option value="returned">被退回</option>
                  </select>
                </label>
                {(
                  [
                    ["channel", "交付渠道"],
                    ["recipient", "接收方"],
                    ["reference", "回执/流水编号"],
                    ["note", "记录说明"],
                    ["occurred_at", "发生时间"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key}>
                    {label}
                    <input
                      type={key === "occurred_at" ? "datetime-local" : "text"}
                      required={[
                        "channel",
                        "recipient",
                        "occurred_at",
                      ].includes(key)}
                      value={event[key]}
                      onChange={(e) =>
                        setEvent({ ...event, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
                <button className="primary" disabled={busy}>
                  保存记录
                </button>
              </form>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
