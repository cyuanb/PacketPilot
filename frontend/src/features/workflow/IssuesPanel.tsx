import { useEffect, useState } from "react";
import { api, post } from "../../api/client";
import type { Case } from "../../api/types";
import { useAsyncAction } from "../../app/useAsyncAction";
import { Dialog } from "../../components/Dialog";
import type { Tab } from "../../app/routes";
import type { Issue, IssueList } from "./types";

const labels: Record<string, string> = {
  open: "待处理",
  requested: "已索取",
  submitted: "已补件，待复检",
  resolved: "已解决",
  exception: "本次检查例外",
  retired: "要求已移除",
};
export function IssuesPanel({
  item,
  refresh,
  setTab,
}: {
  item: Case;
  refresh: () => Promise<void>;
  setTab: (tab: Tab) => void;
}) {
  const [data, setData] = useState<IssueList | null>(null),
    [loadError, setLoadError] = useState(""),
    [closed, setClosed] = useState(false);
  const [editing, setEditing] = useState<Issue | null>(null),
    [status, setStatus] = useState("requested"),
    [note, setNote] = useState("");
  const [history, setHistory] = useState<
    { action: string; note: string; case_revision: number; at: string }[] | null
  >(null);
  const { act, error, busy, isCurrent } = useAsyncAction();
  const [attempt, setAttempt] = useState(0);
  const path = `/cases/${item.id}/issues`;
  useEffect(() => {
    const controller = new AbortController();
    setLoadError("");
    api<IssueList>(
      item.checklist.can_export ? path + "/sync" : path,
      item.checklist.can_export
        ? {
            method: "POST",
            body: JSON.stringify({ revision: item.revision }),
            signal: controller.signal,
          }
        : { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setLoadError(error.message);
      });
    return () => controller.abort();
  }, [
    path,
    item.revision,
    item.checklist.run_id,
    item.checklist.can_export,
    attempt,
  ]);
  const items = data?.items || [];
  const shown = items.filter(
    (issue) =>
      closed ||
      (issue.status !== "retired" &&
        (issue.stale || issue.status !== "resolved")),
  );
  return (
    <section className="panel issues-panel">
      <div className="panel-header">
        <div>
          <h2>问题与补件</h2>
          <p>
            记录进展不会改写检查结论；只有当前有效检查或本人确认才能解决问题。
          </p>
        </div>
        <button
          className="secondary"
          disabled={busy}
          onClick={() =>
            act(async () => {
              await refresh();
              setAttempt((value) => value + 1);
            })
          }
        >
          刷新
        </button>
      </div>
      {(loadError || error) && (
        <p role="alert" className="form-error">
          {loadError || error}
        </p>
      )}
      {!item.checklist.can_export && (
        <p className="subtle-note">
          尚无当前完整检查。请处理输入变化后运行基础预检或 AI
          预检，旧问题仅供参考。
        </p>
      )}
      <div className="issues-toolbar">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={closed}
            onChange={(event) => setClosed(event.target.checked)}
          />
          包含已解决或移除的要求
        </label>
        <button className="text-action" onClick={() => setTab("documents")}>
          前往补充材料
        </button>
        <button className="text-action" onClick={() => setTab("overview")}>
          查看依据与人工确认
        </button>
      </div>
      {!shown.length && (
        <p className="issues-empty">
          {data?.can_sync
            ? "当前没有需要展示的问题；仍请结合检查概览确认准备情况。"
            : "完成检查后，这里会形成可追踪的问题和补件任务。"}
        </p>
      )}
      {shown.map((issue) => (
        <article className="issue-card" key={issue.id}>
          <div className="workflow-section-heading">
            <h3>{issue.title}</h3>
            <span
              className={
                "badge " +
                (issue.stale
                  ? "stale"
                  : issue.status === "resolved"
                    ? "pass"
                    : "unknown")
              }
            >
              {issue.stale ? "历史状态 · " : ""}
              {labels[issue.status]}
            </span>
          </div>
          <p>{issue.reason}</p>
          <p>
            <strong>下一步：</strong>
            {issue.next_action || "无"}
          </p>
          <small>
            {issue.required ? "必需要求" : "建议项"} · 检查修订{" "}
            {issue.checked_revision}
            {issue.stale ? " · 需复检后确认状态" : ""}
          </small>
          {issue.note && <blockquote>{issue.note}</blockquote>}
          {issue.status === "exception" && (
            <p className="hint">
              例外不是通过；输入变化或重新检查后需要重新说明。
            </p>
          )}
          <div className="workflow-actions">
            {!["resolved", "retired"].includes(issue.status) && (
              <button
                className="secondary"
                onClick={() => {
                  setEditing(issue);
                  setStatus("requested");
                  setNote("");
                }}
              >
                更新补件进展
              </button>
            )}
            <button
              className="text-action"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const events = await api<
                    {
                      action: string;
                      note: string;
                      case_revision: number;
                      at: string;
                    }[]
                  >(`/issues/${issue.id}/events`);
                  if (isCurrent()) setHistory(events);
                })
              }
            >
              查看处理记录
            </button>
          </div>
        </article>
      ))}
      {editing && (
        <Dialog
          title="更新补件进展"
          close={() => setEditing(null)}
          busy={busy}
          error={error}
        >
          <h3>{editing.title}</h3>
          <p className="dialog-intro">
            “已索取”和“已补件”都不会直接关闭问题。请上传材料并再次检查。
          </p>
          <label>
            处理状态
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="requested">已索取</option>
              <option value="submitted">已补件，等待复检</option>
              <option value="open">继续处理</option>
              <option value="exception" disabled={editing.stale}>
                记录本次检查的例外
              </option>
            </select>
          </label>
          <label>
            处理说明
            <textarea
              rows={3}
              maxLength={2000}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <div className="dialog-actions">
            <button
              className="primary"
              disabled={busy || (status === "exception" && !note.trim())}
              onClick={() =>
                act(async () => {
                  const result = await api<IssueList>(`/issues/${editing.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({
                      revision: item.revision,
                      issue_revision: editing.revision,
                      status,
                      note,
                    }),
                  });
                  if (isCurrent()) {
                    setData(result);
                    setEditing(null);
                  }
                })
              }
            >
              保存进展
            </button>
          </div>
        </Dialog>
      )}
      {history && (
        <Dialog title="问题处理记录" close={() => setHistory(null)}>
          {history.map((event, index) => (
            <div className="issue-event" key={index}>
              <strong>
                {event.action.startsWith("user.")
                  ? labels[event.action.slice(5)]
                  : (
                      {
                        opened: "形成问题",
                        resolved: "已解决",
                        reopened: "重新打开",
                        rechecked: "重新核对",
                        requirement_removed: "要求已移除",
                      } as Record<string, string>
                    )[event.action] || event.action}
              </strong>
              <p>{event.note || "依据当前检查更新"}</p>
              <small>
                修订 {event.case_revision} ·{" "}
                {new Date(event.at).toLocaleString("zh-CN")}
              </small>
            </div>
          ))}
        </Dialog>
      )}
    </section>
  );
}
