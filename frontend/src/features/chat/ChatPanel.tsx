import {
  BookOpen,
  LoaderCircle,
  Paperclip,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { type Case } from "../../api";
import { MessageBody } from "./MessageBody";
import { useEffect } from "react";
import type { WorkspaceState } from "../../app/useWorkspace";
type Props = Pick<
  WorkspaceState,
  | "running"
  | "busy"
  | "act"
  | "sendChat"
  | "activity"
  | "chatEnd"
  | "chat"
  | "setChat"
  | "requirements"
  | "docMaterials"
  | "openFacts"
  | "trace"
> & {
  item: Case;
  compact?: boolean;
  onExtract?: () => void;
  onCheck?: () => void;
};
export function ChatPanel({
  item,
  running,
  busy,
  act,
  sendChat,
  activity,
  chatEnd,
  chat,
  setChat,
  requirements,
  docMaterials,
  openFacts,
  trace,
  compact = false,
  onExtract,
  onCheck,
}: Props) {
  useEffect(() => {
    const container = chatEnd.current?.closest(".chat-scroll");
    if (container) container.scrollTop = container.scrollHeight;
  }, [item.id, item.messages?.length, compact, chatEnd]);
  const latest = item.runs?.find((r) => r.result.skill);
  const labels: Record<string, string> = {
    get_case_context: "读取事项与已确认背景",
    read_document: "阅读文档原文",
    save_requirement_draft: "保存要求草稿",
    run_checks: "执行规则检查",
    record_semantic_findings: "保存有证据的语义核验",
    propose_facts: "提出背景修改建议",
    ask_user: "记录待确认问题",
    recall_conversation: "回查本事项对话",
  };
  return (
    <div
      className={
        "chat-grid agent-workspace " + (compact ? "agent-compact" : "")
      }
    >
      <section className="panel chat-panel">
        <div className="panel-header">
          <div className="assistant-title">
            <span className="assistant-icon">
              <Sparkles size={20} />
            </span>
            <div>
              <h2>齐备助手</h2>
              <p>读通知、查材料、追问未知条件，和你一起完成申请准备</p>
            </div>
          </div>
        </div>
        <div className="agent-actions">
          {onExtract && (
            <button disabled={busy || !!running} onClick={onExtract}>
              AI 提取通知要求
            </button>
          )}
          {onCheck && (
            <button
              disabled={busy || !!running || !requirements.length}
              onClick={onCheck}
            >
              AI 核对当前材料
            </button>
          )}
          <span>本申请内连续对话 · 背景变更需你确认</span>
        </div>
        <div className="chat-scroll" aria-live="polite">
          {!item.messages?.length && (
            <div className="chat-welcome">
              <span className="large-assistant">
                <Sparkles size={28} />
              </span>
              <h2>告诉齐备，你想完成什么</h2>
              <p>
                我会按任务流程调用工具、读取依据；条件不明时先问你，检查结果和修改建议都会保留。
              </p>
              <div className="suggestions">
                {[
                  "请帮我梳理这份申请，下一步先做什么？",
                  "我现在还缺哪些材料？",
                  "帮我解释需要人工确认的地方",
                  "补件后有哪些变化？",
                ].map((s) => (
                  <button
                    disabled={!!running || busy}
                    key={s}
                    onClick={() => act(() => sendChat(s))}
                  >
                    {s}
                    <Plus size={15} />
                  </button>
                ))}
              </div>
            </div>
          )}
          {item.messages?.map((m) => (
            <div className={"message " + m.role} key={m.id}>
              {m.role === "assistant" && (
                <span className="message-avatar">
                  <Sparkles size={16} />
                </span>
              )}
              <div>
                <small>{m.role === "user" ? "你" : "齐备助手"}</small>
                <MessageBody text={m.content} />
              </div>
            </div>
          ))}
          {running && (
            <div className="thinking">
              <LoaderCircle size={16} className="spin" />
              {activity || "正在查看材料…"}
            </div>
          )}
          <div ref={chatEnd} />
        </div>
        <form
          className="chat-composer"
          onSubmit={(e) => {
            e.preventDefault();
            act(() => sendChat(chat));
          }}
        >
          <textarea
            aria-label="发送给齐备助手"
            placeholder="告诉齐备，你想确认什么…"
            value={chat}
            onChange={(e) => setChat(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (chat.trim() && !running && !busy) act(() => sendChat(chat));
              }
            }}
          />
          <div>
            <span>Enter 发送 · Shift + Enter 换行</span>
            <button
              className="primary"
              aria-label="发送消息"
              disabled={!chat.trim() || !!running || busy}
            >
              <Send size={18} />
            </button>
          </div>
        </form>
      </section>
      <aside>
        <section className="panel small-panel">
          <h3>本次对话使用</h3>
          <div className="context-item">
            <BookOpen size={18} />
            <span>{requirements.length} 项有效要求</span>
          </div>
          <div className="context-item">
            <Paperclip size={18} />
            <span>{docMaterials.length} 份申请材料</span>
          </div>
          <div className="context-item">
            <ShieldCheck size={18} />
            <span>修订版本 {item.revision}</span>
          </div>
          <button className="text-action" onClick={() => openFacts()}>
            查看申请背景
          </button>
        </section>
        {item.runs
          ?.filter((r) => r.result.proposed_facts)
          .slice(0, 1)
          .map((r) => (
            <section className="panel small-panel" key={r.id}>
              <h3>待确认的背景</h3>
              <p>助手提出了背景修改，确认后才会用于检查。</p>
              <button
                className="secondary"
                onClick={() =>
                  openFacts({
                    ...item.facts,
                    ...r.result.proposed_facts,
                  })
                }
              >
                查看修改建议
              </button>
            </section>
          ))}
        <section className="panel small-panel agent-execution">
          <h3>{running ? "正在执行" : "最近一次助手执行"}</h3>
          {latest ? (
            <>
              <p>
                <strong>{latest.result.skill?.label}</strong> ·{" "}
                {(
                  {
                    queued: "排队中",
                    running: "执行中",
                    completed: "已完成",
                    waiting_for_input: "等待你确认",
                    failed: "未完成",
                    cancelled: "已取消",
                  } as Record<string, string>
                )[latest.status] || latest.status}
              </p>
              <details>
                <summary>查看本次 Skill 流程</summary>
                <ol>
                  {latest.result.skill?.steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </details>
              {!!latest.result.memory && (
                <p className="hint">
                  已载入 {latest.result.memory.turns} 轮历史对话
                  {latest.result.memory.window_limited
                    ? "；更早内容可按关键词回查"
                    : ""}
                  。
                </p>
              )}
              <ol className="agent-tool-steps">
                {latest.result.tool_steps?.map((step) => (
                  <li key={step.id} data-status={step.status}>
                    <span>{labels[step.name] || step.name}</span>
                    <small>
                      {step.status === "completed"
                        ? "完成"
                        : step.status === "failed"
                          ? "失败"
                          : ["failed", "cancelled"].includes(latest.status)
                            ? "中断"
                            : "执行中"}
                    </small>
                  </li>
                ))}
              </ol>
              {latest.error && (
                <p role="status" className="warning-text">
                  {latest.error}。明确规则仍可通过“基础预检”核对。
                </p>
              )}
              {!latest.result.tool_steps?.length && (
                <p className="hint">尚无已执行的工具记录。</p>
              )}
            </>
          ) : (
            <p>发起任务后，将显示实际使用的 Skill 与工具执行结果。</p>
          )}
          {running && !latest && trace.map((t, i) => <p key={i}>{t}</p>)}
        </section>
      </aside>
    </div>
  );
}
