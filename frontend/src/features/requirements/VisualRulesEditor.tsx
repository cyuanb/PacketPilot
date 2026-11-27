import { useEffect, useState } from "react";
import { api, post, type Case, type Doc, type Requirement } from "../../api";
import { Dialog } from "../../components/Dialog";

type Condition = {
  all?: Condition[];
  any?: Condition[];
  field?: string;
  op?: string;
  value?: unknown;
};
const kinds: Record<string, string> = {
  material_presence: "材料/数量/配对",
  required_field: "必填字段",
  field_consistency: "同主体字段一致性",
  date_constraint: "日期/有效期间",
  file_format: "文件格式",
  file_size: "文件大小",
  page_count: "PDF 页数",
  semantic_requirement: "内容与语义检查点",
  manual_review: "本人核对原件",
  group: "要求组",
};

function Conditions({
  value,
  change,
  depth = 0,
}: {
  value: Condition;
  change: (value: Condition) => void;
  depth?: number;
}) {
  const type = value.all
    ? "all"
    : value.any
      ? "any"
      : value.field !== undefined
        ? "field"
        : "always";
  const children = value.all || value.any || [];
  return (
    <div className="condition-editor">
      <label>
        适用条件
        <select
          value={type}
          onChange={(e) =>
            change(
              e.target.value === "all"
                ? { all: [{ field: "", op: "eq", value: "" }] }
                : e.target.value === "any"
                  ? { any: [{ field: "", op: "eq", value: "" }] }
                  : e.target.value === "field"
                    ? { field: "", op: "eq", value: "" }
                    : {},
            )
          }
        >
          <option value="always">始终适用</option>
          <option value="field">背景字段判断</option>
          {depth < 5 && (
            <>
              <option value="all">以下条件全部成立</option>
              <option value="any">以下任一条件成立</option>
            </>
          )}
        </select>
      </label>
      {type === "field" && (
        <div className="form-grid">
          <label>
            背景字段名
            <input
              value={value.field || ""}
              onChange={(e) => change({ ...value, field: e.target.value })}
            />
          </label>
          <label>
            比较
            <select
              value={value.op || "eq"}
              onChange={(e) =>
                change({
                  ...value,
                  op: e.target.value,
                  value: e.target.value === "in" ? [] : "",
                })
              }
            >
              <option value="eq">等于</option>
              <option value="ne">不等于</option>
              <option value="in">属于以下值</option>
            </select>
          </label>
          <label>
            值类型
            <select
              value={Array.isArray(value.value) ? "list" : typeof value.value}
              onChange={(e) =>
                change({
                  ...value,
                  value:
                    e.target.value === "boolean"
                      ? true
                      : e.target.value === "number"
                        ? 0
                        : "",
                })
              }
            >
              <option value="string">文本</option>
              <option value="number">数字</option>
              <option value="boolean">是/否</option>
              {value.op === "in" && <option value="list">文本列表</option>}
            </select>
          </label>
          <label>
            比较值
            {typeof value.value === "boolean" ? (
              <select
                value={String(value.value)}
                onChange={(e) =>
                  change({ ...value, value: e.target.value === "true" })
                }
              >
                <option value="true">是</option>
                <option value="false">否</option>
              </select>
            ) : (
              <input
                value={
                  Array.isArray(value.value)
                    ? value.value.join(",")
                    : String(value.value ?? "")
                }
                placeholder={
                  value.op === "in" ? "逗号分隔" : "输入已确认背景值"
                }
                onChange={(e) =>
                  change({
                    ...value,
                    value:
                      value.op === "in"
                        ? e.target.value.split(/[,，]/).map((v) => v.trim())
                        : typeof value.value === "number"
                          ? Number(e.target.value)
                          : e.target.value,
                  })
                }
              />
            )}
          </label>
        </div>
      )}
      {(type === "all" || type === "any") && (
        <>
          {children.map((c, i) => (
            <div key={i}>
              <Conditions
                depth={depth + 1}
                value={c}
                change={(next) =>
                  change({
                    [type]: children.map((v, j) => (i === j ? next : v)),
                  })
                }
              />
              <button
                onClick={() =>
                  change({ [type]: children.filter((_, j) => i !== j) })
                }
              >
                删除条件
              </button>
            </div>
          ))}
          <button
            onClick={() =>
              change({
                [type]: [...children, { field: "", op: "eq", value: "" }],
              })
            }
          >
            增加条件
          </button>
        </>
      )}
    </div>
  );
}

type Trial = {
  conflicts: { requirements: string[]; message: string; resolved: boolean }[];
  report: {
    status: string;
    findings: { requirement_id: string; verdict: string; reason: string }[];
  };
  notice: string;
};

export function VisualRulesEditor({
  item,
  close,
  saved,
}: {
  item: Case;
  close: () => void;
  saved: () => Promise<void>;
}) {
  const [baseRevision] = useState(item.revision);
  const [rules, setRules] = useState<Requirement[]>(
    structuredClone(
      item.rule_sets?.find((s) => s.status === "active")?.requirements || [],
    ),
  );
  const [sources, setSources] = useState<Doc[]>([]);
  const [selected, setSelected] = useState(rules[0]?.id || "");
  const [error, setError] = useState("");
  const [trial, setTrial] = useState<Trial | null>(null);
  const [busy, setBusy] = useState(false);
  const stale = item.revision !== baseRevision;
  useEffect(() => {
    let live = true;
    Promise.all(
      (item.documents || [])
        .filter((d) => d.purpose === "source" && d.parse_status === "ready")
        .map((d) => api<Doc>(`/documents/${d.id}`)),
    )
      .then((v) => {
        if (live) setSources(v);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [item.id, baseRevision]);
  const active = rules.find((r) => r.id === selected);
  const update = (changes: Partial<Requirement>) => {
    setRules(rules.map((r) => (r.id === selected ? { ...r, ...changes } : r)));
    setTrial(null);
  };
  const param = (key: string, value: unknown) => {
    if (!active) return;
    const p = { ...active.parameters };
    if (value === "" || value === undefined) delete p[key];
    else p[key] = value;
    update({ parameters: p });
  };
  const add = () => {
    const source = sources[0];
    const page = source?.pages[0];
    const r: Requirement = {
      id: crypto.randomUUID(),
      title: "",
      kind: "material_presence",
      document_type: "",
      required: true,
      condition: {},
      parameters: {},
      source_evidence:
        source && page
          ? [
              {
                document_id: source.id,
                parse_revision_id: source.parse_revision_id,
                page: page.number,
                quote: "",
              },
            ]
          : [],
      explanation: "",
    };
    setRules([...rules, r]);
    setSelected(r.id);
    setTrial(null);
  };
  const action = async (work: () => Promise<void>) => {
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
  const field = (key: string, label: string, type = "text") => (
    <label key={key}>
      {label}
      <input
        type={type}
        value={String(active?.parameters[key] ?? "")}
        onChange={(e) =>
          param(
            key,
            type === "number" && e.target.value !== ""
              ? Number(e.target.value)
              : e.target.value,
          )
        }
      />
    </label>
  );
  const selection = (
    key: string,
    label: string,
    values: Record<string, string>,
  ) => (
    <label>
      {label}
      <select
        value={String(active?.parameters[key] ?? "")}
        onChange={(e) => param(key, e.target.value)}
      >
        {Object.entries(values).map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
  const sourceEvidence = active?.source_evidence || [];
  const sourceEditor = (index: number) => {
    const evidence = sourceEvidence[index];
    const source = sources.find((d) => d.id === evidence.document_id);
    const page = source?.pages.find((p) => p.number === evidence.page);
    const change = (e: Partial<typeof evidence>) =>
      update({
        source_evidence: sourceEvidence.map((v, i) =>
          i === index ? { ...v, ...e } : v,
        ),
      });
    return (
      <fieldset key={index}>
        <legend>通知引用 {index + 1}</legend>
        <div className="form-grid">
          <label>
            来源版本
            <select
              value={evidence.document_id}
              onChange={(e) => {
                const d = sources.find((d) => d.id === e.target.value);
                change({
                  document_id: e.target.value,
                  parse_revision_id: d?.parse_revision_id,
                  page: d?.pages[0]?.number || 1,
                  quote: "",
                });
              }}
            >
              {!source && (
                <option value={evidence.document_id}>
                  历史来源（请重新选择）
                </option>
              )}
              {sources.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title} · v{d.version}
                </option>
              ))}
            </select>
          </label>
          <label>
            页/段落
            <select
              value={evidence.page}
              onChange={(e) =>
                change({ page: Number(e.target.value), quote: "" })
              }
            >
              {source?.pages.map((p) => (
                <option key={p.number} value={p.number}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <pre className="source-excerpt">{page?.text}</pre>
        <label>
          支持本要求的原文片段
          <textarea
            rows={3}
            value={evidence.quote}
            onChange={(e) => change({ quote: e.target.value })}
          />
        </label>
        <button
          onClick={() =>
            update({
              source_evidence: sourceEvidence.filter((_, i) => i !== index),
            })
          }
        >
          删除此引用
        </button>
      </fieldset>
    );
  };
  return (
    <Dialog title="可视化要求编辑与试运行" close={close} wide>
      <div className="visual-rule-toolbar">
        <label>
          载入已有版本
          <select
            defaultValue=""
            onChange={(e) => {
              const version = item.rule_sets?.find(
                (r) => r.id === e.target.value,
              );
              if (version) {
                setRules(structuredClone(version.requirements));
                setSelected(version.requirements[0]?.id || "");
                setTrial(null);
              }
            }}
          >
            <option value="">当前启用要求/空白草稿</option>
            {item.rule_sets?.map((r) => (
              <option key={r.id} value={r.id}>
                v{r.version} · {r.status}
              </option>
            ))}
          </select>
        </label>
        <button onClick={add}>新增要求或组</button>
      </div>
      {stale && (
        <p role="alert">事项已变化，请关闭后重新打开编辑器，避免覆盖新版本。</p>
      )}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
      <div className="visual-rule-layout">
        <nav aria-label="要求树">
          {rules.map((r) => (
            <button
              key={r.id}
              className={r.id === selected ? "selected" : ""}
              onClick={() => setSelected(r.id)}
            >
              {rules.some(
                (g) =>
                  Array.isArray(g.parameters.children) &&
                  g.parameters.children.includes(r.id),
              )
                ? "↳ "
                : ""}
              {r.kind === "group" ? "▣ " : ""}
              {r.title || "未命名要求"}
            </button>
          ))}
        </nav>
        <div className="visual-rule-detail">
          {active ? (
            <>
              <div className="form-grid">
                <label>
                  要求名称
                  <input
                    value={active.title}
                    onChange={(e) => update({ title: e.target.value })}
                  />
                </label>
                <label>
                  检查方式
                  <select
                    value={active.kind}
                    onChange={(e) =>
                      update({ kind: e.target.value, parameters: {} })
                    }
                  >
                    {Object.entries(kinds).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v}
                      </option>
                    ))}
                  </select>
                </label>
                {selection("severity", "严重程度", {
                  "": "阻塞项",
                  warning: "提醒项",
                  info: "信息项",
                })}
                <label>
                  是否必需
                  <select
                    value={String(active.required)}
                    onChange={(e) =>
                      update({ required: e.target.value === "true" })
                    }
                  >
                    <option value="true">必需</option>
                    <option value="false">建议</option>
                  </select>
                </label>
              </div>
              <Conditions
                value={active.condition as Condition}
                change={(c) =>
                  update({ condition: c as Record<string, unknown> })
                }
              />
              {active.kind === "group" ? (
                <fieldset>
                  <legend>组内关系</legend>
                  {selection("operator", "满足方式", {
                    "": "全部满足",
                    all: "全部满足",
                    any: "任一满足",
                    at_least: "至少满足指定数量",
                  })}
                  {active.parameters.operator === "at_least" &&
                    field("min_count", "最少通过子项数", "number")}
                  {rules
                    .filter((r) => r.id !== active.id)
                    .map((r) => (
                      <label key={r.id}>
                        <input
                          type="checkbox"
                          checked={(
                            (active.parameters.children as string[]) || []
                          ).includes(r.id)}
                          onChange={(e) =>
                            param(
                              "children",
                              e.target.checked
                                ? [
                                    ...((active.parameters
                                      .children as string[]) || []),
                                    r.id,
                                  ]
                                : (
                                    (active.parameters.children as string[]) ||
                                    []
                                  ).filter((id) => id !== r.id),
                            )
                          }
                        />
                        {r.title || "未命名要求"}
                      </label>
                    ))}
                </fieldset>
              ) : (
                <>
                  <fieldset>
                    <legend>材料与主体范围</legend>
                    <div className="form-grid">
                      <label>
                        材料类型
                        <input
                          list="scene-material-types"
                          value={active.document_type}
                          onChange={(e) =>
                            update({ document_type: e.target.value })
                          }
                        />
                        <datalist id="scene-material-types">
                          {item.scenario?.materials.map((m) => (
                            <option key={m} value={m} />
                          ))}
                        </datalist>
                      </label>
                      {field("slot_id", "材料槽位标识（可留空）")}
                      {selection("subject_role", "主体角色", {
                        "": "不限制角色",
                        applicant: "申请人",
                        recommender: "推荐人",
                        organization: "组织",
                        representative: "经办人",
                        contact: "联系人",
                        other: "其他",
                      })}
                      <label>
                        具体主体（角色多人时必选）
                        <select
                          value={String(active.parameters.subject_id || "")}
                          onChange={(e) => param("subject_id", e.target.value)}
                        >
                          <option value="">由唯一角色确定/不限制</option>
                          {item.subjects?.map((s) => (
                            <option
                              key={`${s.subject_id}:${s.role}`}
                              value={s.subject_id}
                            >
                              {s.name} · {s.role}
                            </option>
                          ))}
                        </select>
                      </label>
                      {selection("variant", "材料形式", {
                        "": "不限",
                        original: "原件",
                        translation: "译件",
                      })}
                    </div>
                  </fieldset>
                  {active.kind === "material_presence" && (
                    <div className="form-grid">
                      {field("min_count", "最少份数", "number")}
                      {field("max_count", "最多份数", "number")}
                      {selection("distinct_by", "按什么区分独立材料", {
                        "": "原件内容哈希",
                        original: "原件内容哈希",
                        document: "独立文档",
                        issuer: "独立出具方",
                      })}
                      <label>
                        <input
                          type="checkbox"
                          checked={!!active.parameters.requires_pair}
                          onChange={(e) =>
                            param("requires_pair", e.target.checked)
                          }
                        />
                        需要原件与译件配对
                      </label>
                    </div>
                  )}
                  {[
                    "required_field",
                    "field_consistency",
                    "date_constraint",
                  ].includes(active.kind) && field("field", "核对的字段标签")}
                  {active.kind === "field_consistency" && (
                    <label>
                      涉及材料类型（逗号分隔）
                      <input
                        value={(
                          (active.parameters.document_types as string[]) || []
                        ).join(",")}
                        onChange={(e) =>
                          param(
                            "document_types",
                            e.target.value
                              .split(/[,，]/)
                              .map((v) => v.trim())
                              .filter(Boolean),
                          )
                        }
                      />
                    </label>
                  )}
                  {active.kind === "date_constraint" && (
                    <div className="form-grid">
                      {field("not_before", "不早于（含当日）", "date")}
                      {field("not_after", "不晚于（含当日）", "date")}
                      {selection("reference", "参照日期", {
                        "": "仅固定边界",
                        deadline: "事项截止日期",
                        today: "本次检查日期",
                      })}
                      {field("offset_days", "参照偏移天数", "number")}
                      {field(
                        "max_age_days",
                        "相对参照日期最多已过去天数",
                        "number",
                      )}
                      {field(
                        "end_field",
                        "有效期结束字段（配合起始字段覆盖参照日）",
                      )}
                    </div>
                  )}
                  {active.kind === "file_format" && (
                    <label>
                      允许扩展名（逗号分隔）
                      <input
                        value={(
                          (active.parameters.allowed as string[]) || []
                        ).join(",")}
                        onChange={(e) =>
                          param(
                            "allowed",
                            e.target.value
                              .split(/[,，]/)
                              .map((v) => v.trim())
                              .filter(Boolean),
                          )
                        }
                      />
                    </label>
                  )}
                  {active.kind === "file_size" &&
                    field("max_bytes", "最大字节数", "number")}
                  {active.kind === "page_count" &&
                    field("max_pages", "最大 PDF 页数", "number")}
                  {active.kind === "semantic_requirement" && (
                    <label>
                      逐项内容检查点（每行一项）
                      <textarea
                        rows={4}
                        value={(
                          (active.parameters.criteria as string[]) || []
                        ).join("\n")}
                        onChange={(e) =>
                          param(
                            "criteria",
                            e.target.value.split("\n").filter((v) => v.trim()),
                          )
                        }
                      />
                      <small>
                        模型必须逐项引用各份对应材料；未知、遗漏或不完整输入不能被标为通过。
                      </small>
                    </label>
                  )}
                </>
              )}
              <div className="form-grid">
                {field("source_valid_until", "来源有效至（可留空）", "date")}
                {field(
                  "conflict_resolution",
                  "多来源冲突处理说明（存在冲突时填写）",
                )}
              </div>
              <label>
                要求解释
                <input
                  value={active.explanation}
                  onChange={(e) => update({ explanation: e.target.value })}
                />
              </label>
              {sourceEvidence.map((_, i) => sourceEditor(i))}
              <button
                disabled={!sources.length || sourceEvidence.length >= 10}
                onClick={() =>
                  update({
                    source_evidence: [
                      ...sourceEvidence,
                      {
                        document_id: sources[0].id,
                        parse_revision_id: sources[0].parse_revision_id,
                        page: sources[0].pages[0]?.number || 1,
                        quote: "",
                      },
                    ],
                  })
                }
              >
                增加通知引用
              </button>
              <button
                onClick={() => {
                  setRules(
                    rules
                      .filter((r) => r.id !== selected)
                      .map((r) =>
                        r.kind === "group"
                          ? {
                              ...r,
                              parameters: {
                                ...r.parameters,
                                children: (
                                  (r.parameters.children as string[]) || []
                                ).filter((id) => id !== selected),
                              },
                            }
                          : r,
                      ),
                  );
                  setSelected("");
                  setTrial(null);
                }}
              >
                删除当前要求
              </button>
            </>
          ) : (
            <p>新增要求，或从左侧选择要编辑的节点。</p>
          )}
        </div>
      </div>
      {trial && (
        <section className="rule-trial">
          <h3>草稿试运行：{trial.report.status}</h3>
          <p>{trial.notice}</p>
          {trial.conflicts.map((c, i) => (
            <p key={i} className="warning-text">
              {c.resolved ? "已记录处理说明：" : "未解决冲突："}
              {c.message}（
              {c.requirements
                .map((id) => rules.find((r) => r.id === id)?.title)
                .join(" / ")}
              ）
            </p>
          ))}
          {trial.report.findings.map((f) => (
            <p key={f.requirement_id}>
              <strong>
                {rules.find((r) => r.id === f.requirement_id)?.title}
              </strong>{" "}
              · {f.verdict} · {f.reason}
            </p>
          ))}
        </section>
      )}
      <div className="dialog-actions">
        <button
          disabled={busy || stale || !rules.length}
          onClick={() =>
            action(async () =>
              setTrial(
                await post(`/cases/${item.id}/rules/preview`, {
                  revision: baseRevision,
                  requirements: rules,
                }),
              ),
            )
          }
        >
          检查来源冲突并试运行
        </button>
        <button
          className="primary"
          disabled={busy || stale || !rules.length}
          onClick={() =>
            action(async () => {
              await post(`/cases/${item.id}/rule-sets`, {
                revision: baseRevision,
                requirements: rules,
              });
              await saved();
              close();
            })
          }
        >
          保存为新草稿
        </button>
      </div>
      <p className="hint">
        保存不自动启用；在要求列表确认版本后启用。模型或模板更新不会改写当前要求。
      </p>
    </Dialog>
  );
}
