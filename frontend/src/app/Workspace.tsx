import {
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  LoaderCircle,
  ShieldCheck,
  X,
} from "lucide-react";
import { Sidebar } from "../app/Sidebar";
import { ConfirmationDialog } from "../components/ConfirmationDialog";
import { CaseEditor } from "../features/cases/CaseEditor";
import { CaseWorkspace } from "../features/cases/CaseWorkspace";
import { Dashboard } from "../features/cases/Dashboard";
import { FactsDialog } from "../features/cases/FactsDialog";
import { DocumentPreview } from "../features/documents/DocumentPreview";
import { TextSourceDialog } from "../features/documents/TextSourceDialog";
import { RequirementsEditor } from "../features/requirements/RequirementsEditor";
import { AttestationDialog } from "../features/review/AttestationDialog";
import { SettingsDialog } from "../features/settings/SettingsDialog";
import { useWorkspace, type WorkspaceOptions } from "./useWorkspace";
import { useResource } from "./useResource";
import { SubjectsPage } from "../features/subjects/SubjectsPage";
import type { WorkspaceInfo } from "../features/subjects/types";
import { LibraryPage } from "../features/library/LibraryPage";
import { LibraryDetail } from "../features/library/LibraryDetail";
export function Workspace(options: WorkspaceOptions) {
  const workspace = useResource<WorkspaceInfo>(options.client, "/workspace");
  const {
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
    busy,
    pickUpload,
    fileChange,
    setSource,
    docMaterials,
    openDoc,
    setConfirm,
    refresh,
    docSources,
    running,
    run,
    setRuleEditor,
    setNotice,
    sendChat,
    activity,
    chatEnd,
    chat,
    setChat,
    trace,
    setSelected,
    loadCases,
    modal,
    error,
    queryError,
    draftCase,
    setDraftCase,
    openCase,
    setItem,
    source,
    facts,
    setFacts,
    advanced,
    setRulesRaw,
    rules,
    setRules,
    rulesRaw,
    setError,
    setAdvanced,
    manualNote,
    manual,
    capabilities,
    preview,
    setPreview,
    highlight,
    setCorrection,
    correction,
    confirm,
    selected,
    archive,
    cases,
    setCapabilities,
    user,
    setUser,
    goHome,
    newExample,
    query,
    setQuery,
    tab,
    fileInput,
    notice,
  } = useWorkspace(options);
  return (
    <div className="app-shell">
      <Sidebar
        library={options.navigation.library}
        goLibrary={options.navigation.goLibrary}
        workspace={workspace.data}
        showSubjects={!!options.navigation.subjects}
        goSubjects={options.navigation.goSubjects}
        setSelected={setSelected}
        selected={selected}
        archive={archive}
        cases={cases}
        setModal={setModal}
        openCase={openCase}
        act={act}
        setCapabilities={setCapabilities}
        user={user}
        setUser={setUser}
        goHome={goHome}
      />
      <main className="main">
        <header className="topbar">
          <div>
            <span>工作空间</span>
            <ChevronRight size={14} />
            <strong>
              {options.navigation.library
                ? options.navigation.assetId
                  ? "资料详情"
                  : options.navigation.library === "inbox"
                    ? "收集箱"
                    : "资料中心"
                : options.navigation.subjects
                  ? "主体档案"
                  : selected
                    ? item?.title || "正在加载"
                    : "我的申请"}
            </strong>
          </div>
          <span className="topbar-note">
            <ShieldCheck size={15} /> 材料准备，由你掌控
          </span>
        </header>
        {error && (
          <div role="alert" className="error-banner">
            <CircleAlert size={18} />
            {error}
            {queryError ? (
              <button
                className="text-action"
                disabled={busy}
                onClick={() => act(refresh)}
              >
                重新加载
              </button>
            ) : (
              <button
                className="icon-button"
                aria-label="关闭错误"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            )}
          </div>
        )}
        {options.navigation.library ? (
          options.navigation.assetId ? (
            <LibraryDetail
              id={options.navigation.assetId}
              client={options.client}
            />
          ) : (
            <LibraryPage
              client={options.client}
              inbox={options.navigation.library === "inbox"}
            />
          )
        ) : options.navigation.subjects ? (
          <SubjectsPage client={options.client} />
        ) : !selected ? (
          <Dashboard
            archive={archive}
            setModal={setModal}
            busy={busy}
            act={act}
            newExample={newExample}
            cases={cases}
            query={query}
            setQuery={setQuery}
            openCase={openCase}
          />
        ) : !item ? (
          <div className="boot">
            {queryError ? (
              "暂时无法读取申请，请重试或返回申请列表。"
            ) : (
              <>
                <LoaderCircle className="spin" /> 正在读取申请…
              </>
            )}
          </div>
        ) : (
          <CaseWorkspace
            setSelected={setSelected}
            item={item}
            setDraftCase={setDraftCase}
            setModal={setModal}
            act={act}
            setConfirm={setConfirm}
            draftCase={draftCase}
            refresh={refresh}
            busy={busy}
            running={running}
            requirements={requirements}
            run={run}
            tab={tab}
            setTab={setTab}
            docMaterials={docMaterials}
            activity={activity}
            trace={trace}
            findingMap={findingMap}
            confirmed={confirmed}
            openEvidence={openEvidence}
            setManual={setManual}
            setManualNote={setManualNote}
            percentage={percentage}
            doneCount={doneCount}
            openFacts={openFacts}
            pickUpload={pickUpload}
            fileChange={fileChange}
            setSource={setSource}
            openDoc={openDoc}
            docSources={docSources}
            setRuleEditor={setRuleEditor}
            setNotice={setNotice}
            sendChat={sendChat}
            chatEnd={chatEnd}
            chat={chat}
            setChat={setChat}
            loadCases={loadCases}
          />
        )}
      </main>
      <input
        type="file"
        hidden
        ref={fileInput}
        accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (f) act(() => fileChange(f));
        }}
      />
      {notice && (
        <div className="toast" role="status">
          <CheckCircle2 size={18} />
          {notice}
        </div>
      )}
      <CaseEditor
        modal={modal}
        error={error}
        setModal={setModal}
        act={act}
        item={item}
        draftCase={draftCase}
        setDraftCase={setDraftCase}
        loadCases={loadCases}
        openCase={openCase}
        setItem={setItem}
        busy={busy}
      />
      <TextSourceDialog
        modal={modal}
        item={item}
        error={error}
        source={source}
        setModal={setModal}
        act={act}
        refresh={refresh}
        setSource={setSource}
        busy={busy}
      />
      <FactsDialog
        modal={modal}
        item={item}
        error={error}
        setModal={setModal}
        facts={facts}
        setFacts={setFacts}
        busy={busy}
        act={act}
        refresh={refresh}
      />
      <RequirementsEditor
        modal={modal}
        item={item}
        error={error}
        setModal={setModal}
        advanced={advanced}
        setRulesRaw={setRulesRaw}
        rules={rules}
        setRules={setRules}
        rulesRaw={rulesRaw}
        setError={setError}
        setAdvanced={setAdvanced}
        busy={busy}
        act={act}
        refresh={refresh}
        setNotice={setNotice}
      />
      <AttestationDialog
        modal={modal}
        item={item}
        error={error}
        setModal={setModal}
        manualNote={manualNote}
        setManualNote={setManualNote}
        busy={busy}
        act={act}
        manual={manual}
        refresh={refresh}
      />
      <SettingsDialog
        modal={modal}
        error={error}
        setModal={setModal}
        capabilities={capabilities}
        busy={busy}
        act={act}
        setNotice={setNotice}
      />
      <DocumentPreview
        preview={preview}
        error={error}
        setPreview={setPreview}
        setModal={setModal}
        highlight={highlight}
        setCorrection={setCorrection}
        modal={modal}
        item={item}
        correction={correction}
        busy={busy}
        act={act}
        refresh={refresh}
      />
      <ConfirmationDialog
        confirm={confirm}
        error={error}
        setConfirm={setConfirm}
        busy={busy}
        act={act}
      />
    </div>
  );
}
