import type { Case } from "../../api/types";
import { post } from "../../api/client";
import type { Tab } from "../../app/routes";
import { useAsyncAction } from "../../app/useAsyncAction";

export function CaseGuide({
  item,
  setTab,
  refresh,
  openFacts,
}: {
  item: Case;
  setTab: (tab: Tab) => void;
  refresh: () => Promise<void>;
  openFacts: (facts?: Record<string, string | number | boolean>) => void;
}) {
  const { act, busy, error } = useAsyncAction();
  const scenario = item.scenario;
  const hasSubject = !!item.subjects?.some(
    (subject) => subject.role === "applicant",
  );
  const sources = (item.documents || []).filter(
    (document) =>
      document.purpose === "source" && document.parse_status === "ready",
  );
  const currentSources = new Set(sources.map((source) => source.id));
  const requirements = item.checklist.requirements;
  const rulesCurrent =
    !!requirements.length &&
    requirements.every((rule) =>
      rule.source_evidence.every((e) => currentSources.has(e.document_id)),
    );
  const running = item.runs?.some((run) =>
    ["queued", "running"].includes(run.status),
  );
  return (
    <section className="panel case-guide">
      <div className="workflow-section-heading">
        <div>
          <h2>{scenario?.title || "材料准备流程"}</h2>
          <p>
            {scenario?.description ||
              "确认要求、固定资料版本，再按问题补件和复检。"}
          </p>
        </div>
        {scenario && (
          <span className="badge unknown">起步配置 v{scenario.version}</span>
        )}
      </div>
      {scenario && (
        <>
          <p className="hint">{scenario.notice}</p>
          <div className="scenario-hints">
            <span>办理路径：{scenario.stages.join(" → ")}</span>
            <span>
              建议角色：{scenario.roles.map((role) => role.label).join("、")}
            </span>
            <span>可能涉及：{scenario.materials.join("、")}（以通知为准）</span>
          </div>
        </>
      )}
      <ol className="workflow-steps">
        <li>
          <strong>1 · 主体</strong>
          <span>
            {hasSubject ? "已指定申请主体" : "在下方卡片关联申请主体"}
          </span>
        </li>
        <li>
          <strong>2 · 通知与要求</strong>
          <span>
            {rulesCurrent
              ? `${requirements.length} 项已启用要求`
              : sources.length
                ? "审阅并启用当前通知要求"
                : "先导入接收方通知"}
          </span>
          <button className="text-action" onClick={() => setTab("rules")}>
            处理要求
          </button>
        </li>
        <li>
          <strong>3 · 材料版本</strong>
          <span>
            {item.document_links?.filter((link) => link.purpose === "material")
              .length || 0}{" "}
            份材料已固定版本
          </span>
          <button className="text-action" onClick={() => setTab("documents")}>
            选择与补充
          </button>
        </li>
        <li>
          <strong>4 · 检查与补件</strong>
          <span>
            {item.checklist.stale
              ? "输入已变化，需要复检"
              : "基础检查不调用模型，语义项保留待确认"}
          </span>
          <button className="text-action" onClick={() => setTab("issues")}>
            查看问题
          </button>
        </li>
      </ol>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      <div className="workflow-actions">
        <button
          className="primary"
          disabled={
            busy || running || !rulesCurrent || (!!scenario && !hasSubject)
          }
          onClick={() =>
            act(async () => {
              await post(`/cases/${item.id}/checks/basic`, {
                revision: item.revision,
              });
              await refresh();
              setTab("issues");
            })
          }
        >
          {busy ? "正在检查…" : "运行基础预检"}
        </button>
        <button
          className="secondary"
          onClick={() =>
            openFacts({
              ...Object.fromEntries(
                (scenario?.facts || []).map((name) => [name, ""]),
              ),
              ...item.facts,
            })
          }
        >
          确认事项背景
        </button>
        <span className="hint">当前可导出检查清单，尚不生成材料包。</span>
      </div>
    </section>
  );
}
