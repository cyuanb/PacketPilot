import {
  BookOpen,
  Check,
  CircleAlert,
  Download,
  Eye,
  FileText,
  ListChecks,
  MessageSquare,
  Pencil,
} from "lucide-react";
import { type Case } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Badge } from "../../components/Badge";
import { Empty } from "../../components/Empty";
type Props = Pick<
  WorkspaceState,
  | "requirements"
  | "setTab"
  | "findingMap"
  | "confirmed"
  | "act"
  | "openEvidence"
  | "setManual"
  | "setManualNote"
  | "setModal"
  | "percentage"
  | "doneCount"
  | "openFacts"
> & { item: Case };
export function ReviewOverview({
  requirements,
  item,
  setTab,
  findingMap,
  confirmed,
  act,
  openEvidence,
  setManual,
  setManualNote,
  setModal,
  percentage,
  doneCount,
  openFacts,
}: Props) {
  return (
    <div className="overview-grid">
      <section className="panel checklist-panel">
        <div className="panel-header">
          <div>
            <h2>材料准备清单</h2>
            <p>逐项核对要求，点击依据查看原文</p>
          </div>
          <span className="count-label">
            {requirements.length} 项要求 ·{" "}
            {item.checklist.stale
              ? "历史结果仅供参考"
              : item.checklist.coverage.evaluated_count + " 项已有有效结果"}
          </span>
        </div>
        {!requirements.length ? (
          <Empty
            icon={<ListChecks size={28} />}
            title="先把要求整理清楚"
            text="导入申请通知，提取并审阅要求后，开始核对材料。"
            action={
              <button className="primary" onClick={() => setTab("rules")}>
                整理申请要求
              </button>
            }
          />
        ) : (
          <div className="findings-list">
            {requirements.map((r) => {
              const f = findingMap.get(r.id);
              const good =
                !item.checklist.stale &&
                f?.evaluation_state === "evaluated" &&
                (f?.verdict === "pass" ||
                  f?.applicability === "not_applicable" ||
                  confirmed.has(r.id));
              return (
                <div className={"finding " + (good ? "good" : "")} key={r.id}>
                  <span
                    className={
                      "finding-icon " +
                      (good ? "pass" : f?.verdict || "unknown")
                    }
                  >
                    {good ? (
                      <Check size={18} />
                    ) : f?.verdict === "conflict" ? (
                      <CircleAlert size={18} />
                    ) : (
                      <FileText size={18} />
                    )}
                  </span>
                  <div className="finding-content">
                    <div className="finding-heading">
                      <h3>
                        {r.title}
                        {!r.required && (
                          <small className="advisory-label">建议项</small>
                        )}
                      </h3>
                      <Badge
                        status={
                          item.checklist.stale
                            ? "stale"
                            : good
                              ? "pass"
                              : f?.verdict || "unknown"
                        }
                      >
                        {item.checklist.stale
                          ? "历史结果"
                          : f?.evaluation_state === "not_evaluated"
                            ? "尚未检查"
                            : f?.evaluation_state === "invalid"
                              ? "需重查"
                              : f?.applicability === "not_applicable"
                                ? "不适用"
                                : confirmed.has(r.id)
                                  ? "本人已确认"
                                  : undefined}
                      </Badge>
                    </div>
                    <p>{f?.reason || r.explanation || "等待执行检查"}</p>
                    {f?.next_action && !good && (
                      <div className="next-action">{f.next_action}</div>
                    )}
                    {!!f?.field_coverage?.length && (
                      <details className="review-coverage">
                        <summary>逐材料字段覆盖</summary>
                        {f.field_coverage.map((c, i) => (
                          <div key={c.document_id + ":" + i}>
                            <strong>
                              {item.documents?.find(
                                (d) => d.id === c.document_id,
                              )?.title || "历史材料"}{" "}
                              · {c.field}
                            </strong>
                            <span>
                              {(
                                {
                                  covered: "已唯一读取",
                                  missing: "未读取到字段",
                                  unreadable: "材料未完整读取",
                                  ambiguous: "多个值，需确认主体",
                                  invalid: "格式尚未确认",
                                } as Record<string, string>
                              )[c.status] || c.status}
                            </span>
                            {c.values.length > 0 && (
                              <p>{c.values.join(" / ")}</p>
                            )}
                            {c.evidence[0] && (
                              <button
                                className="text-action"
                                onClick={() =>
                                  act(() => openEvidence(c.evidence[0]))
                                }
                              >
                                查看字段原文
                              </button>
                            )}
                          </div>
                        ))}
                      </details>
                    )}
                    {!!f?.material_matches?.length && (
                      <details className="review-coverage">
                        <summary>候选材料的核对依据</summary>
                        {f.material_matches.map((m, i) => (
                          <div key={m.document_id + ":" + i}>
                            <strong>
                              {item.documents?.find(
                                (d) => d.id === m.document_id,
                              )?.title || "历史材料"}
                            </strong>
                            <span>{m.reason}</span>
                            {m.evidence[0] && (
                              <button
                                className="text-action"
                                onClick={() =>
                                  act(() => openEvidence(m.evidence[0]))
                                }
                              >
                                查看材料原文
                              </button>
                            )}
                          </div>
                        ))}
                      </details>
                    )}
                    <div className="evidence-actions">
                      {r.source_evidence.map((e, i) => (
                        <button
                          key={"s" + i}
                          onClick={() => act(() => openEvidence(e))}
                        >
                          <BookOpen size={13} />
                          要求依据
                        </button>
                      ))}
                      {f?.evidence.slice(0, 3).map((e, i) => (
                        <button
                          key={"m" + i}
                          onClick={() => act(() => openEvidence(e))}
                        >
                          <FileText size={13} />
                          材料证据 {i + 1}
                        </button>
                      ))}
                      {f?.method === "manual" &&
                        f.applicability === "applicable" &&
                        !confirmed.has(r.id) &&
                        item.checklist.can_export && (
                          <button
                            onClick={() => {
                              setManual(r.id);
                              setManualNote("");
                              setModal("manual");
                            }}
                          >
                            <Eye size={13} />
                            人工确认
                          </button>
                        )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
      <aside className="overview-side">
        <section className="panel progress-panel">
          <h3>这份申请，准备到哪了？</h3>
          <div
            className="progress-ring"
            style={
              {
                "--progress": percentage + "%",
              } as React.CSSProperties
            }
          >
            <div>
              <strong>
                {item.checklist.stale ? "—" : doneCount}
                <small> / {requirements.length}</small>
              </strong>
              <span>已处理的要求</span>
            </div>
          </div>
          <p>
            {item.checklist.status === "ready"
              ? "所有当前要求已处理，可以进行最终复核。"
              : "从一个小问题开始，让准备更进一步。"}
          </p>
          <button className="secondary full" onClick={() => setTab("chat")}>
            <MessageSquare size={16} />
            和齐呈一起梳理
          </button>
        </section>
        <section className="panel small-panel">
          <div className="mini-heading">
            <h3>申请背景</h3>
            <button
              aria-label="编辑申请背景"
              className="icon-button"
              onClick={() => openFacts()}
            >
              <Pencil size={15} />
            </button>
          </div>
          {Object.entries(item.facts).map(([k, v]) => (
            <div className="fact-line" key={k}>
              <span>{k}</span>
              <strong>{String(v)}</strong>
            </div>
          ))}
          {!Object.keys(item.facts).length && (
            <p>补充申请类别等背景，让条件检查更准确。</p>
          )}
          <button className="text-action" onClick={() => openFacts()}>
            补充或修改背景
          </button>
        </section>
        <section className="export-card">
          <Download size={21} />
          <h3>带着清单，继续准备</h3>
          <p>导出当前检查结果，保留依据与待办。</p>
          {item.checklist.can_export ? (
            <div>
              <a
                className="text-action"
                href={"/api/v1/cases/" + item.id + "/export?format=html"}
              >
                下载 HTML
              </a>
              <a
                className="text-action"
                href={"/api/v1/cases/" + item.id + "/export?format=md"}
              >
                Markdown
              </a>
            </div>
          ) : (
            <span className="muted">完成当前版本检查后可导出</span>
          )}
        </section>
      </aside>
    </div>
  );
}
