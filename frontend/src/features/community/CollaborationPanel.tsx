import { useEffect, useState } from "react";
import { api, post, type Case, type Doc } from "../../api";
type Grant = {
  id: string;
  role: string;
  username?: string;
  expires_at: string;
  revoked: boolean;
  title?: string;
};
type Submission = {
  id: string;
  filename: string;
  status: string;
  note: string;
};
type Detail = {
  grants: Grant[];
  comments: {
    id: string;
    content: string;
    decision: string;
    stale: boolean;
    page: number;
    quote: string;
  }[];
  submissions: Submission[];
};
export function CollaborationPanel({
  item,
  refresh,
}: {
  item: Case;
  refresh: () => Promise<void>;
}) {
  const [data, setData] = useState<Detail | null>(null),
    [role, setRole] = useState("reviewer"),
    [docs, setDocs] = useState<string[]>([]),
    [token, setToken] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = async () =>
    setData(await api<Detail>(`/cases/${item.id}/collaboration`));
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [item.id, item.revision]);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel community-panel">
      <h2>收集与他人复核</h2>
      <p>
        授权固定材料版本；更换文件不自动授权新版。收集者只能提交指定任务，不能查看已有材料。邀请码由你自行转交。
      </p>
      <label>
        授权用途
        <select
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setDocs([]);
          }}
        >
          <option value="reviewer">查看、评论与复核所选材料</option>
          <option value="reader">仅查看所选材料</option>
          <option value="collector">限定材料收集（不共享已有资料）</option>
        </select>
      </label>
      {role !== "collector" &&
        item.documents
          ?.filter((d) => d.purpose === "material")
          .map((d) => (
            <label key={d.id}>
              <input
                type="checkbox"
                checked={docs.includes(d.id)}
                onChange={(e) =>
                  setDocs(
                    e.target.checked
                      ? [...docs, d.id]
                      : docs.filter((id) => id !== d.id),
                  )
                }
              />
              {d.title} · v{d.version}
            </label>
          ))}
      <button
        disabled={busy || (role !== "collector" && !docs.length)}
        onClick={() =>
          act(async () => {
            const v = await post<{ token: string }>(
              `/cases/${item.id}/invitations`,
              { role, document_ids: docs, days: 7 },
            );
            setToken(v.token);
          })
        }
      >
        创建 7 天邀请
      </button>
      {token && (
        <div className="packet-preview">
          <p>邀请码只显示一次，请交给指定协助者，在登录页“接受邀请”使用。</p>
          <code>{token}</code>
          <button
            onClick={() => {
              navigator.clipboard.writeText(token);
            }}
          >
            复制
          </button>
          <button onClick={() => setToken("")}>隐藏邀请码</button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {data?.grants.map((g) => (
        <div className="work-card" key={g.id}>
          <strong>
            {g.username || "待接受"} · {g.role}
          </strong>
          <p>
            {g.revoked
              ? "已撤销"
              : `有效至 ${new Date(g.expires_at).toLocaleString()}`}
          </p>
          <button
            disabled={busy || g.revoked}
            onClick={() =>
              act(async () => {
                await api(`/invitations/${g.id}`, { method: "DELETE" });
              })
            }
          >
            撤销授权
          </button>
        </div>
      ))}
      <h3>收集提交</h3>
      {data?.submissions.map((s) => (
        <div className="work-card" key={s.id}>
          <strong>
            {s.filename} · {s.status}
          </strong>
          <p>{s.note}</p>
          {s.status === "submitted" && (
            <>
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await post(`/submissions/${s.id}/review`, {
                      decision: "accept",
                      note: "所有者接收，待核对",
                      category: "",
                    });
                    await refresh();
                  })
                }
              >
                接收到事项并解析
              </button>
              <button
                disabled={busy}
                onClick={() => {
                  const note = window.prompt("退回原因");
                  if (note)
                    act(async () => {
                      await post(`/submissions/${s.id}/review`, {
                        decision: "return",
                        note,
                      });
                    });
                }}
              >
                退回补充
              </button>
            </>
          )}
        </div>
      ))}
      <h3>位置评论与复核意见</h3>
      {data?.comments.map((c) => (
        <article className="work-card" key={c.id}>
          <strong>
            {c.decision} · 第 {c.page} 页{" "}
            {c.stale ? "（历史版本，需重新复核）" : ""}
          </strong>
          <blockquote>{c.quote}</blockquote>
          <p>{c.content}</p>
        </article>
      ))}
    </section>
  );
}

export function SharedPortal() {
  const [grants, setGrants] = useState<Grant[]>([]),
    [selected, setSelected] = useState(""),
    [detail, setDetail] = useState<{
      role: string;
      documents: Doc[];
      submissions: Submission[];
    } | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [docId, setDocId] = useState(""),
    [page, setPage] = useState(1),
    [quote, setQuote] = useState(""),
    [content, setContent] = useState(""),
    [decision, setDecision] = useState("comment");
  const load = async () => {
    setGrants(await api<Grant[]>("/shared"));
    if (selected) setDetail(await api(`/shared/${selected}`));
  };
  useEffect(() => {
    setDetail(null);
    load().catch((e) => setError(e.message));
  }, [selected]);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
      setDetail(null);
    } finally {
      setBusy(false);
    }
  };
  const doc = detail?.documents.find((d) => d.id === docId);
  return (
    <section className="panel community-panel">
      <h2>收到的协作授权</h2>
      <button onClick={() => load()}>刷新授权</button>
      <label>
        协作事项
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">选择授权</option>
          {grants.map((g) => (
            <option key={g.id} value={g.id}>
              {g.title} · {g.role}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      {detail?.documents.map((d) => (
        <details key={d.id}>
          <summary>{d.title}</summary>
          <a href={`/api/v1/shared/${selected}/documents/${d.id}/content`}>
            下载授权原件
          </a>
          {d.pages.map((p) => (
            <pre key={p.number}>
              {p.label}\n{p.text}
            </pre>
          ))}
          {detail.role === "reviewer" && (
            <button
              onClick={() => {
                setDocId(d.id);
                setPage(d.pages[0]?.number || 1);
              }}
            >
              评论/复核此版本
            </button>
          )}
        </details>
      ))}
      {doc && detail?.role === "reviewer" && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              await post(`/shared/${selected}/comments`, {
                document_id: doc.id,
                parse_revision_id: doc.parse_revision_id,
                page,
                quote,
                content,
                decision,
              });
              setContent("");
            });
          }}
        >
          <h3>{doc.title} · 复核</h3>
          <label>
            页码
            <input
              type="number"
              min="1"
              value={page}
              onChange={(e) => setPage(Number(e.target.value))}
            />
          </label>
          <label>
            原文定位片段
            <textarea
              value={quote}
              onChange={(e) => setQuote(e.target.value)}
            />
          </label>
          <label>
            意见
            <textarea
              required
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </label>
          <select
            aria-label="复核结论"
            value={decision}
            onChange={(e) => setDecision(e.target.value)}
          >
            <option value="comment">评论</option>
            <option value="approved">本次复核认可</option>
            <option value="returned">请补充或修改</option>
          </select>
          <button disabled={busy}>保存意见（不改变机器结论）</button>
        </form>
      )}
      {detail?.role === "collector" && (
        <>
          <p>你只能向本收集任务上传，无法查看事项其他资料。</p>
          <input
            type="file"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f)
                act(async () => {
                  const body = new FormData();
                  body.append("file", f);
                  await api(`/shared/${selected}/submissions`, {
                    method: "POST",
                    body,
                  });
                });
            }}
          />
          {detail.submissions.map((s) => (
            <p key={s.id}>
              {s.filename} · {s.status} · {s.note}
            </p>
          ))}
        </>
      )}
    </section>
  );
}
