import { CaseGuide } from "../workflow/CaseGuide";
import { IssuesPanel } from "../workflow/IssuesPanel";
import { PacketsPanel } from "../delivery/PacketsPanel";
import { ParseWorkspace } from "../parsing/ParseWorkspace";
import { MaterialAssignments } from "../matching/MaterialAssignments";
import {
  Archive,
  BookOpen,
  CalendarDays,
  CircleAlert,
  FolderOpen,
  History,
  ListChecks,
  LoaderCircle,
  MessageSquare,
  Pencil,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  StopCircle,
} from "lucide-react";
import { api, date, post, type Case } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Badge } from "../../components/Badge";
import { ChatPanel } from "../chat/ChatPanel";
import { DocumentsPanel } from "../documents/DocumentsPanel";
import { RequirementsPanel } from "../requirements/RequirementsPanel";
import { ReviewOverview } from "../review/ReviewOverview";
import { HistoryPanel } from "../runs/HistoryPanel";
import { kinds } from "./constants";
import { CaseSubjectsPanel } from "../subjects/CaseSubjectsPanel";
type Props = Pick<
  WorkspaceState,
  | "setSelected"
  | "setDraftCase"
  | "setModal"
  | "act"
  | "setConfirm"
  | "draftCase"
  | "refresh"
  | "busy"
  | "running"
  | "requirements"
  | "run"
  | "tab"
  | "setTab"
  | "docMaterials"
  | "activity"
  | "trace"
  | "findingMap"
  | "confirmed"
  | "openEvidence"
  | "setManual"
  | "setManualNote"
  | "percentage"
  | "doneCount"
  | "openFacts"
  | "pickUpload"
  | "fileChange"
  | "setSource"
  | "openDoc"
  | "docSources"
  | "setRuleEditor"
  | "setNotice"
  | "sendChat"
  | "chatEnd"
  | "chat"
  | "setChat"
  | "loadCases"
> & { item: Case };
export function CaseWorkspace({
  setSelected,
  item,
  setDraftCase,
  setModal,
  act,
  setConfirm,
  draftCase,
  refresh,
  busy,
  running,
  requirements,
  run,
  tab,
  setTab,
  docMaterials,
  activity,
  trace,
  findingMap,
  confirmed,
  openEvidence,
  setManual,
  setManualNote,
  percentage,
  doneCount,
  openFacts,
  pickUpload,
  fileChange,
  setSource,
  openDoc,
  docSources,
  setRuleEditor,
  setNotice,
  sendChat,
  chatEnd,
  chat,
  setChat,
  loadCases,
}: Props) {
  return (
    <div className="case-workspace">
      <div className="case-heading">
        <div>
          <button className="back-link" onClick={() => setSelected(null)}>
            我的申请 / {kinds[item.kind] || "其他申请"}
          </button>
          <h1>{item.title}</h1>
          <div className="case-meta">
            <span>{item.institution || "未填写申请机构"}</span>
            <span>
              <CalendarDays size={15} />
              {item.deadline ? date(item.deadline) + " 截止" : "截止日期待确认"}
            </span>
            <Badge status={item.checklist.status} />
          </div>
        </div>
        <div className="heading-actions">
          <button
            className="secondary"
            onClick={() => {
              setDraftCase({
                title: item.title,
                institution: item.institution,
                kind: item.kind,
                deadline: item.deadline,
              });
              setModal("edit");
            }}
          >
            <Pencil size={16} />
            编辑
          </button>
          <button
            className="secondary"
            onClick={() =>
              act(async () => {
                setConfirm({
                  text: item.archived
                    ? "将此申请恢复到进行中？"
                    : "归档后仍可查看材料和历史。确定归档？",
                  action: async () => {
                    await api("/cases/" + item.id, {
                      method: "PATCH",
                      body: JSON.stringify({
                        ...draftCase,
                        title: item.title,
                        institution: item.institution,
                        kind: item.kind,
                        deadline: item.deadline,
                        revision: item.revision,
                        archived: !item.archived,
                      }),
                    });
                    await refresh();
                  },
                });
              })
            }
          >
            <Archive size={16} />
            {item.archived ? "恢复" : "归档"}
          </button>
          <button
            className="primary"
            disabled={busy || !!running || !requirements.length}
            onClick={() => act(() => run("checks"))}
          >
            {running ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Sparkles size={17} />
            )}{" "}
            {running ? "正在处理" : "AI 预检"}
          </button>
        </div>
      </div>
      <CaseGuide
        item={item}
        setTab={setTab}
        refresh={refresh}
        openFacts={openFacts}
      />
      <CaseSubjectsPanel item={item} onChanged={refresh} />
      <div className="workspace-tabs">
        {(
          [
            ["overview", "检查概览", ListChecks],
            ["issues", "问题与补件", CircleAlert],
            ["documents", "材料库", FolderOpen],
            ["parsing", "解析与校订", BookOpen],
            ["matching", "材料归属", ShieldCheck],
            ["rules", "申请要求", BookOpen],
            ["packets", "材料包与交付", Archive],
            ["chat", "对话助手", MessageSquare],
            ["history", "检查历史", History],
          ] as const
        ).map(([key, label, Icon]) => (
          <button
            key={key}
            className={tab === key ? "selected" : ""}
            onClick={() => setTab(key)}
          >
            <Icon size={17} />
            {label}
            {key === "documents" && <span>{docMaterials.length}</span>}
          </button>
        ))}
      </div>
      {running && (
        <div className="run-bar">
          <LoaderCircle className="spin" size={17} />
          <span>{activity || "任务已接收，正在处理…"}</span>
          <small>{trace.slice(-1)[0] || "进度会自动更新"}</small>
          <button
            onClick={() =>
              act(async () => {
                await post("/runs/" + running.id + "/cancel");
                await refresh();
              })
            }
          >
            <StopCircle size={16} />
            取消
          </button>
        </div>
      )}
      {item.checklist.stale && (
        <div className="stale-banner">
          <RefreshCw size={18} />
          <div>
            <strong>
              {item.checklist.legacy
                ? "旧版检查需要重新核对"
                : "当前结果需要复检"}
            </strong>
            <span>
              {item.checklist.stale_reason || "下方是历史结果，请重新预检。"}
            </span>
          </div>
        </div>
      )}
      {!item.checklist.stale &&
        item.checklist.run_id &&
        (!item.checklist.coverage.complete ||
          !["completed", "waiting_for_input"].includes(
            item.checklist.run_status || "",
          )) && (
          <div className="stale-banner">
            <CircleAlert size={18} />
            <div>
              <strong>本次检查尚未完整完成</strong>
              <span>
                有效结果覆盖 {item.checklist.coverage.evaluated_count} /{" "}
                {item.checklist.coverage.expected_count} 项要求。
                {item.checklist.run_status === "failed"
                  ? "运行失败，已完成的部分已保留。"
                  : "存在未检查或无效的结果。"}{" "}
                请重新预检后再导出。
              </span>
            </div>
          </div>
        )}
      {tab === "overview" && (
        <ReviewOverview
          requirements={requirements}
          item={item}
          setTab={setTab}
          findingMap={findingMap}
          confirmed={confirmed}
          act={act}
          openEvidence={openEvidence}
          setManual={setManual}
          setManualNote={setManualNote}
          setModal={setModal}
          percentage={percentage}
          doneCount={doneCount}
          openFacts={openFacts}
        />
      )}
      {tab === "issues" && (
        <IssuesPanel item={item} refresh={refresh} setTab={setTab} />
      )}
      {tab === "packets" && <PacketsPanel key={item.id} item={item} />}
      {tab === "parsing" && (
        <ParseWorkspace key={item.id} item={item} refresh={refresh} />
      )}
      {tab === "matching" && (
        <MaterialAssignments item={item} refresh={refresh} />
      )}
      {tab === "documents" && (
        <DocumentsPanel
          item={item}
          busy={busy}
          pickUpload={pickUpload}
          act={act}
          fileChange={fileChange}
          setSource={setSource}
          setModal={setModal}
          docMaterials={docMaterials}
          openDoc={openDoc}
          setConfirm={setConfirm}
          refresh={refresh}
        />
      )}
      {tab === "rules" && (
        <RequirementsPanel
          setSource={setSource}
          setModal={setModal}
          docSources={docSources}
          act={act}
          openDoc={openDoc}
          pickUpload={pickUpload}
          running={running}
          busy={busy}
          run={run}
          item={item}
          setRuleEditor={setRuleEditor}
          refresh={refresh}
          setNotice={setNotice}
        />
      )}
      {tab === "chat" && (
        <ChatPanel
          item={item}
          running={running}
          busy={busy}
          act={act}
          sendChat={sendChat}
          activity={activity}
          chatEnd={chatEnd}
          chat={chat}
          setChat={setChat}
          requirements={requirements}
          docMaterials={docMaterials}
          openFacts={openFacts}
          trace={trace}
        />
      )}
      {tab === "history" && (
        <HistoryPanel
          item={item}
          setConfirm={setConfirm}
          setSelected={setSelected}
          loadCases={loadCases}
        />
      )}
      <footer className="workspace-footer">
        <ShieldCheck size={14} />
        预检用于辅助准备，最终材料由你确认。
        <span>
          {item.checklist.checked_at
            ? "最近检查 " +
              new Date(item.checklist.checked_at).toLocaleString("zh-CN")
            : "尚未进行检查"}
        </span>
      </footer>
    </div>
  );
}
