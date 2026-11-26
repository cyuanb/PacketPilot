import {
  BookOpen,
  Check,
  LoaderCircle,
  Paperclip,
  Plus,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { type Case } from "../../api";
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
> & { item: Case };
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
}: Props) {
  return (
    <div className="chat-grid">
      <section className="panel chat-panel">
        <div className="panel-header">
          <div className="assistant-title">
            <span className="assistant-icon">
              <Sparkles size={20} />
            </span>
            <div>
              <h2>齐备助手</h2>
              <p>基于这份申请的通知、材料和已确认背景</p>
            </div>
          </div>
        </div>
        <div className="chat-scroll">
          {!item.messages?.length && (
            <div className="chat-welcome">
              <span className="large-assistant">
                <Sparkles size={28} />
              </span>
              <h2>一起把申请准备清楚</h2>
              <p>我会查看要求与材料，把问题和依据一起告诉你。</p>
              <div className="suggestions">
                {[
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
                <div className="message-body">{m.content}</div>
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
        <section className="panel small-panel">
          <h3>处理进度</h3>
          {trace.length ? (
            trace.map((t, i) => (
              <div className="trace-item" key={i}>
                <Check size={13} />
                {t}
              </div>
            ))
          ) : (
            <p>分析开始后，这里会显示正在进行的操作。</p>
          )}
        </section>
      </aside>
    </div>
  );
}
