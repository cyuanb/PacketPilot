import { ChevronDown, History } from "lucide-react";
import { api, statusLabels, type Case } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Badge } from "../../components/Badge";
type Props = Pick<
  WorkspaceState,
  "setConfirm" | "setSelected" | "loadCases"
> & { item: Case };
export function HistoryPanel({
  item,
  setConfirm,
  setSelected,
  loadCases,
}: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>检查与处理记录</h2>
          <p>保留每次运行的范围、版本与结果</p>
        </div>
      </div>
      {item.runs?.map((r) => (
        <details className="history-item" key={r.id}>
          <summary>
            <span className="history-icon">
              <History size={18} />
            </span>
            <div>
              <strong>
                {
                  (
                    {
                      check: "材料预检",
                      extract: "要求提取",
                      chat: "对话分析",
                      parse: "文件读取",
                    } as Record<string, string>
                  )[r.kind]
                }
              </strong>
              <small>
                {new Date(r.created_at).toLocaleString("zh-CN")} · 修订{" "}
                {r.revision}
              </small>
            </div>
            <Badge
              status={
                r.status === "completed"
                  ? "pass"
                  : r.status === "failed"
                    ? "fail"
                    : "unknown"
              }
            >
              {
                (
                  {
                    completed: "已完成",
                    failed: "未完全完成",
                    running: "处理中",
                    queued: "排队中",
                    cancelled: "已取消",
                    waiting_for_input: "等待回复",
                  } as Record<string, string>
                )[r.status]
              }
            </Badge>
            <ChevronDown size={16} />
          </summary>
          <div className="history-body">
            {r.error && <p className="form-error">{r.error}</p>}
            <p>{r.result.answer || "本次运行未生成文字说明。"}</p>
            {r.result.findings?.map((f) => (
              <p key={f.requirement_id}>
                <strong>
                  {f.requirement_id} · {statusLabels[f.verdict]}
                </strong>{" "}
                {f.reason}
              </p>
            ))}
            <small>
              {r.model ? "模型：" + r.model + " · " : ""}
              {r.skill_hash
                ? "Skill：" + r.skill_hash.slice(0, 12)
                : "确定性处理"}{" "}
              · {r.id}
            </small>
          </div>
        </details>
      ))}
      <div className="panel-footer">
        <span className="muted">
          删除申请会清除事项关联和历史，资料中心保留原件。
        </span>
        <button
          className="text-action danger"
          onClick={() =>
            setConfirm({
              text: "永久删除此申请的材料关联、对话与历史？资料中心仍保留原件和版本。事项记录删除后不可撤销。",
              action: async () => {
                await api("/cases/" + item.id, { method: "DELETE" });
                setSelected(null);
                await loadCases();
              },
            })
          }
        >
          删除申请
        </button>
      </div>
    </section>
  );
}
