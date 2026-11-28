import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  post,
  type Case,
  type Doc,
  type Evidence,
  type Requirement,
} from "../api";
import { useCaseQueries } from "../features/cases/useCaseQueries";
import type { SessionState } from "../features/identity/useSession";
import { useRunActivity } from "../features/runs/useRunActivity";
import type { QueryClient } from "./queryClient";
import { useAsyncAction } from "./useAsyncAction";
import { useEditors } from "./useEditors";
import type { WorkspaceNavigation } from "./useWorkspaceRoute";
export type WorkspaceOptions = {
  navigation: WorkspaceNavigation;
  client: QueryClient;
  user: string;
  setUser: SessionState["setUser"];
  notice: string;
  notify: (message: string) => void;
};
export function useWorkspace({
  navigation,
  client,
  user,
  setUser,
  notice,
  notify,
}: WorkspaceOptions) {
  const { selected, tab, archive, setTab } = navigation;
  const {
    busy,
    error: actionError,
    setError,
    act,
    isCurrent,
  } = useAsyncAction();
  const queries = useCaseQueries(client, selected);
  const {
    cases,
    item,
    loadCases: queryLoadCases,
    loadDetail,
    setItem,
  } = queries;
  const loadCases = useCallback(
    (force = true) => {
      return isCurrent() ? queryLoadCases(force) : Promise.resolve([]);
    },
    [queryLoadCases, isCurrent],
  );
  const error = actionError || queries.queryError;
  const queryError = queries.queryError;
  const refresh = async () => {
    if (isCurrent()) await queries.refresh();
  };
  const openCase = (id: string) => {
    if (isCurrent()) navigation.openCase(id);
  };
  const goHome = (archive = false) => {
    if (isCurrent()) navigation.goHome(archive);
  };
  const setSelected = (id: string | null) => (id ? openCase(id) : goHome());
  const [query, setQuery] = useState("");
  const [modal, setModalState] = useState("");
  const setModal = useCallback(
    (value: string) => {
      setError("");
      setModalState(value);
    },
    [setError],
  );
  const setNotice = useCallback(
    (message: string) => {
      if (isCurrent()) notify(message);
    },
    [notify, isCurrent],
  );
  const [chat, setChat] = useState("");
  const {
    source,
    setSource,
    draftCase,
    setDraftCase,
    preview,
    setPreview,
    highlight,
    setHighlight,
    rules,
    setRules,
    rulesRaw,
    setRulesRaw,
    advanced,
    setAdvanced,
    facts,
    setFacts,
    manual,
    setManual,
    manualNote,
    setManualNote,
    correction,
    setCorrection,
    confirm,
    setConfirm: setConfirmState,
    capabilities,
    setCapabilities,
  } = useEditors();
  const setConfirm = useCallback(
    (value: Parameters<typeof setConfirmState>[0]) => {
      setError("");
      setConfirmState(value);
    },
    [setError, setConfirmState],
  );
  const fileInput = useRef<HTMLInputElement>(null),
    uploadPurpose = useRef("material"),
    replaceId = useRef("");
  const chatEnd = useRef<HTMLDivElement>(null);
  const running = item?.runs?.find(
    (r) => r.status === "running" || r.status === "queued",
  );
  const { activity, trace, setTrace } = useRunActivity(
    running,
    loadDetail,
    loadCases,
  );
  useEffect(() => {
    const container = chatEnd.current?.closest(".chat-scroll");
    if (container)
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [item?.messages?.length, tab]);
  const run = async (kind: "checks" | "extract") => {
    if (!item) return;
    await post("/cases/" + item.id + "/" + kind, { revision: item.revision });
    setTrace([]);
    await refresh();
  };
  const openEvidence = async (e: Evidence) => {
    const d = await api<Doc>(
      "/documents/" +
        e.document_id +
        (e.parse_revision_id
          ? "?parse_revision_id=" + encodeURIComponent(e.parse_revision_id)
          : ""),
    );
    if (!isCurrent()) return;
    setPreview(d);
    setHighlight(e);
  };
  const openDoc = async (d: Doc) => {
    const loaded = await api<Doc>("/documents/" + d.id);
    if (!isCurrent()) return;
    setPreview(loaded);
    setHighlight(null);
  };
  const pickUpload = (purpose = "material", replace = "") => {
    uploadPurpose.current = purpose;
    replaceId.current = replace;
    fileInput.current?.click();
  };
  const fileChange = async (file: File) => {
    if (!item) return;
    const data = new FormData();
    data.append("file", file);
    data.append("purpose", uploadPurpose.current);
    data.append("replace_id", replaceId.current);
    const result = await api<{ duplicates?: unknown[] }>(
      "/cases/" + item.id + "/documents",
      {
        method: "POST",
        body: data,
      },
    );
    await refresh();
    setNotice(
      result.duplicates?.length
        ? "材料已接收，正在读取；资料中心存在相同原件，本次版本仍独立保存。"
        : "材料已接收，正在读取",
    );
  };
  const newExample = async () => {
    const c = await post<Case>("/demo");
    await loadCases();
    openCase(c.id);
    setNotice("已创建独立的合成示例，可以自由体验");
  };
  const sendChat = async (text: string) => {
    if (!item || !text.trim()) return;
    await post("/cases/" + item.id + "/messages", {
      revision: item.revision,
      text,
    });
    setChat("");
    await refresh();
  };
  const setRuleEditor = (r: Requirement[]) => {
    setRules(structuredClone(r));
    setRulesRaw(JSON.stringify(r, null, 2));
    setAdvanced(false);
    setModal("rules");
  };
  const openFacts = (values = item?.facts || {}) => {
    setFacts(Object.entries(values).map(([k, v]) => [k, String(v)]));
    setModal("facts");
  };
  const docSources =
    item?.documents?.filter((d) => d.purpose === "source") || [];
  const docMaterials =
    item?.documents?.filter((d) => d.purpose === "material") || [];
  const findingMap = new Map(
    item?.checklist.findings.map((f) => [f.requirement_id, f]),
  );
  const requirements = item?.checklist.requirements || [];
  const confirmed = new Set(
    item?.checklist.attestations.map((a) => a.requirement_id),
  );
  const doneCount = requirements.filter((r) => {
    const f = findingMap.get(r.id);
    return (
      !item?.checklist.stale &&
      f?.evaluation_state === "evaluated" &&
      (f.verdict === "pass" ||
        f.applicability === "not_applicable" ||
        confirmed.has(r.id) ||
        f?.satisfied_by_confirmation)
    );
  }).length;
  const percentage = requirements.length
    ? Math.round((doneCount / requirements.length) * 100)
    : 0;
  return {
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
  };
}
export type WorkspaceState = ReturnType<typeof useWorkspace>;
