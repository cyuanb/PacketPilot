import { useEffect, useState } from "react";
import { api, post } from "../../api";
import { SharedPortal } from "./CollaborationPanel";

export function AccountEntry() {
  const [mode, setMode] = useState(""),
    [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [token, setToken] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <details className="account-entry">
      <summary>接受邀请 / 使用恢复码重置密码</summary>
      <label>
        操作
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="">选择操作</option>
          <option value="invite">接受邀请（新账号或现有账号）</option>
          <option value="recover">使用离线恢复码</option>
        </select>
      </label>
      {mode && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              await post(
                mode === "invite" ? "/invitations/accept" : "/account/recover",
                mode === "invite"
                  ? { username, password, token }
                  : { username, new_password: password, recovery_code: token },
              );
              setMessage("操作完成，请使用上述账号密码登录。");
              setToken("");
              setPassword("");
            } catch (e) {
              setMessage(e instanceof Error ? e.message : "失败");
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            账号
            <input
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
          <label>
            {mode === "invite" ? "现有密码或新账号密码" : "新密码"}
            <input
              type="password"
              minLength={12}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label>
            {mode === "invite" ? "邀请码" : "离线恢复码"}
            <input
              required
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </label>
          <button disabled={busy}>确认</button>
          <p role="status">{message}</p>
        </form>
      )}
    </details>
  );
}

type Job = {
  id: string;
  case_id: string;
  kind: string;
  status: string;
  attempt: number;
  error: string;
};
export function AccountTools() {
  const [sessions, setSessions] = useState<
      { id: string; current: boolean; expires_at: string }[]
    >([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [reminders, setReminders] = useState<
      { id: string; case_id: string; title: string; overdue: boolean }[]
    >([]),
    [message, setMessage] = useState(""),
    [code, setCode] = useState(""),
    [password, setPassword] = useState(""),
    [backup, setBackup] = useState<File | null>(null),
    [preview, setPreview] = useState(false),
    [busy, setBusy] = useState(false);
  const load = async () => {
    setSessions(await api("/account/sessions"));
    setJobs((await api<{ jobs: Job[] }>("/diagnostics")).jobs);
    setReminders(await api("/reminders"));
  };
  useEffect(() => {
    load().catch((e) => setMessage(e.message));
  }, []);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setMessage("");
    try {
      await fn();
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="community-hub">
      <SharedPortal />
      <section className="panel community-panel">
        <h2>站内待办提醒</h2>
        {reminders.length ? (
          reminders.map((r) => (
            <p key={r.id}>
              <a href={`#/cases/${r.case_id}/work`}>{r.title}</a> ·{" "}
              {r.overdue ? "已逾期" : "临近期限"}
            </p>
          ))
        ) : (
          <p>没有进入提醒期的任务。</p>
        )}
      </section>
      <section className="panel community-panel">
        <h2>账号与会话</h2>
        {sessions.map((s) => (
          <p key={s.id}>
            {s.current ? "当前会话" : "其他会话"} · 到期{" "}
            {new Date(s.expires_at).toLocaleString()}
            <button
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await api(`/account/sessions/${s.id}`, { method: "DELETE" });
                  if (s.current) location.reload();
                })
              }
            >
              撤销
            </button>
          </p>
        ))}
        <label>
          确认当前密码
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button
          disabled={busy || !password}
          onClick={() =>
            act(async () => {
              const r = await post<{ recovery_code: string }>(
                "/account/recovery-code",
                { password },
              );
              setPassword("");
              setCode(r.recovery_code);
            })
          }
        >
          生成新的离线恢复码
        </button>
        {code && (
          <div>
            <p>只显示一次，请离线保管；新码会替换旧码。</p>
            <code>{code}</code>
            <button onClick={() => setCode("")}>已保存，隐藏</button>
          </div>
        )}
      </section>
      <section className="panel community-panel">
        <h2>数据备份与恢复</h2>
        <p>
          备份包含当前空间的事项、资料原件与冻结包，不含密码、会话或外部授权。文件包含个人资料，请自行保管。恢复创建独立副本，不覆盖当前数据。
        </p>
        <a href="/api/v1/data/backup">下载完整数据备份</a>
        <label>
          选择数据备份
          <input
            type="file"
            accept=".zip"
            onChange={(e) => {
              setBackup(e.target.files?.[0] || null);
              setPreview(false);
            }}
          />
        </label>
        <button
          disabled={busy || !backup}
          onClick={() =>
            act(async () => {
              const body = new FormData();
              body.append("file", backup!);
              const r = await api<{ cases: number; files: number }>(
                "/data/restore-preview",
                { method: "POST", body },
              );
              setMessage(`校验通过：${r.cases} 个事项，${r.files} 个原件。`);
              setPreview(true);
            })
          }
        >
          校验并预览
        </button>
        <button
          disabled={busy || !backup || !preview}
          onClick={() =>
            act(async () => {
              const body = new FormData();
              body.append("file", backup!);
              const r = await api<{ notice: string }>("/data/restore", {
                method: "POST",
                body,
              });
              setMessage(r.notice);
              setPreview(false);
            })
          }
        >
          确认恢复为独立副本
        </button>
      </section>
      <section className="panel community-panel">
        <h2>任务诊断与恢复</h2>
        <p>
          只列任务状态与错误摘要，不展示材料正文。模型任务有步骤和时间上限；失败可按当前输入重试。
        </p>
        <button onClick={() => load()}>刷新</button>
        {jobs.map((j) => (
          <div className="work-card" key={j.id}>
            <span>
              {j.kind} · {j.status} · 尝试 {j.attempt}
            </span>
            <p>{j.error}</p>
            {["failed", "cancelled"].includes(j.status) && (
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await post(`/runs/${j.id}/retry`);
                    setMessage("已按当前输入创建重试任务");
                  })
                }
              >
                重试
              </button>
            )}
          </div>
        ))}
      </section>
      {message && (
        <p role="status" className="packet-preview">
          {message}
        </p>
      )}
    </div>
  );
}
