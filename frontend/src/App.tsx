import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  FileCheck2,
  LayoutGrid,
  Archive,
  Settings,
  Plus,
  Search,
  ArrowUpRight,
  ChevronRight,
  FileText,
  Upload,
  Check,
  Clock3,
  CircleAlert,
  Sparkles,
  X,
  CalendarDays,
  ShieldCheck,
  MoreHorizontal,
  Download,
  RefreshCw,
  Send,
  BookOpen,
  Paperclip,
  CheckCircle2,
  FolderOpen,
  LogOut,
  LoaderCircle,
  History,
  MessageSquare,
  ListChecks,
  Trash2,
  Eye,
  Pencil,
  StopCircle,
  Layers,
  ExternalLink,
  Info,
  ChevronDown,
} from "lucide-react";
import {
  api,
  post,
  date,
  statusLabels,
  type Case,
  type Doc,
  type Evidence,
  type Requirement,
  type Run,
} from "./api";

type Tab = "overview" | "documents" | "rules" | "chat" | "history";
const kinds: Record<string, string> = {
  exchange: "校际交流",
  scholarship: "奖学金",
  grant: "项目申报",
  other: "其他申请",
};
const verdictIcon = (status: string) =>
  status === "pass" || status === "ready" ? (
    <CheckCircle2 size={17} />
  ) : status === "not_ready" || status === "unknown" ? (
    <Clock3 size={17} />
  ) : (
    <CircleAlert size={17} />
  );

function Badge({ status, children }: { status: string; children?: ReactNode }) {
  return (
    <span className={"badge " + status}>
      {verdictIcon(status)}
      {children || statusLabels[status] || status}
    </span>
  );
}
function Dialog({
  title,
  children,
  close,
  wide = false,
  error = "",
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
  error?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={"dialog " + (wide ? "wide" : "")}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <header>
        <h2>{title}</h2>
        <button className="icon-button" aria-label="关闭" onClick={close}>
          <X size={20} />
        </button>
      </header>
      <div className="dialog-body">
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {children}
      </div>
    </dialog>
  );
}
function Empty({
  icon,
  title,
  text,
  action,
}: {
  icon: ReactNode;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<string | null>(null),
    [loading, setLoading] = useState(true);
  const [cases, setCases] = useState<Case[]>([]),
    [selected, setSelected] = useState<string | null>(() => {
      const match = window.location.hash.match(/^#case\/([0-9a-f-]{36})/);
      return match ? match[1] : null;
    }),
    [item, setItem] = useState<Case | null>(null);
  const [tab, setTab] = useState<Tab>("overview"),
    [archive, setArchive] = useState(false),
    [query, setQuery] = useState("");
  useEffect(() => {
    window.history.replaceState(
      null,
      "",
      selected ? "#case/" + selected : window.location.pathname,
    );
  }, [selected]);
  const [modal, setModal] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [chat, setChat] = useState(""),
    [activity, setActivity] = useState(""),
    [trace, setTrace] = useState<string[]>([]);
  const [source, setSource] = useState({
    title: "申请通知",
    text: "",
    purpose: "source",
    category: "",
  });
  const [draftCase, setDraftCase] = useState({
    title: "",
    institution: "",
    kind: "exchange",
    deadline: "",
  });
  const [preview, setPreview] = useState<Doc | null>(null),
    [highlight, setHighlight] = useState<Evidence | null>(null);
  const [rules, setRules] = useState<Requirement[]>([]),
    [rulesRaw, setRulesRaw] = useState(""),
    [advanced, setAdvanced] = useState(false);
  const [facts, setFacts] = useState<[string, string][]>([]),
    [manual, setManual] = useState(""),
    [manualNote, setManualNote] = useState("");
  const [correction, setCorrection] = useState(""),
    [confirm, setConfirm] = useState<{
      text: string;
      action: () => Promise<void>;
    } | null>(null);
  const [capabilities, setCapabilities] = useState<{
    model: string;
    model_configured: boolean;
    ocr: boolean;
    inference: string;
  } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null),
    uploadPurpose = useRef("material"),
    replaceId = useRef("");
  const chatEnd = useRef<HTMLDivElement>(null);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  useEffect(() => {
    const navigate = () => {
      const match = window.location.hash.match(/^#case\/([0-9a-f-]{36})/);
      setSelected(match ? match[1] : null);
      setPreview(null);
      setModal("");
      setTab("overview");
    };
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, []);
  const loadCases = useCallback(
    async () => setCases(await api<Case[]>("/cases")),
    [],
  );
  const loadDetail = useCallback(async () => {
    if (selected) {
      const loaded = await api<Case>("/cases/" + selected);
      if (selectedRef.current === selected) setItem(loaded);
    }
  }, [selected]);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    api<{ username: string }>("/me")
      .then((x) => setUser(x.username))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (user) loadCases().catch((e) => setError(e.message));
  }, [user, loadCases]);
  useEffect(() => {
    setItem(null);
    setTrace([]);
    setActivity("");
    if (selected) loadDetail().catch((e) => setError(e.message));
  }, [selected, loadDetail]);
  const running = item?.runs?.find(
    (r) => r.status === "running" || r.status === "queued",
  );
  useEffect(() => {
    if (!running) return;
    setTrace([]);
    setActivity(running.kind === "parse" ? "正在读取材料内容" : "");
    const stream = new EventSource("/api/v1/runs/" + running.id + "/events");
    const stage = (e: Event) => {
      const d = JSON.parse((e as MessageEvent).data);
      if (d.message) setActivity(d.message);
    };
    const tool = (e: Event) => {
      const d = JSON.parse((e as MessageEvent).data);
      setTrace((t) => [
        ...t.slice(-15),
        (
          {
            get_case_context: "读取申请背景",
            read_document: "查看材料原文",
            save_requirement_draft: "整理要求草稿",
            run_checks: "逐项核对材料",
            record_semantic_findings: "保存内容检查",
            propose_facts: "整理待确认背景",
            ask_user: "确认关键信息",
          } as Record<string, string>
        )[d.name] || "正在处理",
      ]);
    };
    const done = () => {
      stream.close();
      setActivity("");
      loadDetail().catch(() => {});
      loadCases().catch(() => {});
    };
    stream.addEventListener("stage.changed", stage);
    stream.addEventListener("tool.started", tool);
    stream.addEventListener("done", done);
    const timer = setInterval(() => loadDetail().catch(() => {}), 2500);
    return () => {
      stream.close();
      clearInterval(timer);
    };
  }, [running?.id, loadDetail, loadCases]);
  useEffect(() => {
    if (tab === "chat")
      chatEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [item?.messages?.length, tab]);
  useEffect(() => {
    if (notice) {
      const timer = setTimeout(() => setNotice(""), 4500);
      return () => clearTimeout(timer);
    }
  }, [notice]);
  const refresh = async () => {
    await loadDetail();
    await loadCases();
  };
  const openCase = (id: string) => {
    setSelected(id);
    setTab("overview");
  };
  const run = async (kind: "checks" | "extract") => {
    if (!item) return;
    await post("/cases/" + item.id + "/" + kind, { revision: item.revision });
    setTrace([]);
    await refresh();
  };
  const openEvidence = async (e: Evidence) => {
    const d = await api<Doc>("/documents/" + e.document_id);
    setPreview(d);
    setHighlight(e);
  };
  const openDoc = async (d: Doc) => {
    setPreview(await api<Doc>("/documents/" + d.id));
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
    await api("/cases/" + item.id + "/documents", {
      method: "POST",
      body: data,
    });
    await refresh();
    setNotice("材料已接收，正在读取");
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
        confirmed.has(r.id))
    );
  }).length;
  const percentage = requirements.length
    ? Math.round((doneCount / requirements.length) * 100)
    : 0;

  if (loading)
    return (
      <div className="boot">
        <LoaderCircle className="spin" /> 正在打开齐呈…
      </div>
    );
  if (!user)
    return (
      <div className="login-page">
        <div className="login-story">
          <div className="brand">
            <span className="brand-icon">
              <FileCheck2 />
            </span>
            <strong>
              齐呈 <small>PacketPilot</small>
            </strong>
          </div>
          <div>
            <span className="eyebrow">从容准备，安心出发</span>
            <h1>
              每一份材料，
              <br />
              都有据可查。
            </h1>
            <p>
              把通知、材料和待办放在一起。
              <br />
              齐呈陪你核对细节，补齐每一步。
            </p>
            <div className="login-papers">
              <div>
                <CheckCircle2 />
                申请表 <span>已核对</span>
              </div>
              <div>
                <FileText />
                成绩证明 <span>有据可查</span>
              </div>
              <div>
                <Sparkles />
                下一步 <span>清楚明了</span>
              </div>
            </div>
          </div>
          <span className="login-foot">有依据的预检 · 有条理的申请</span>
        </div>
        <div className="login-form">
          <div>
            <span className="eyebrow">YOUR APPLICATION, TOGETHER</span>
            <h2>欢迎来到齐呈</h2>
            <p>登录你的材料准备工作台</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                act(async () => {
                  const u = await post<{ username: string }>("/auth/login", {
                    username: f.get("username"),
                    password: f.get("password"),
                  });
                  setUser(u.username);
                });
              }}
            >
              <label>
                账号
                <input
                  name="username"
                  defaultValue="owner"
                  autoComplete="username"
                  required
                />
              </label>
              <label>
                密码
                <input
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                />
              </label>
              {error && <p className="form-error">{error}</p>}
              <button className="primary login-submit" disabled={busy}>
                {busy ? <LoaderCircle className="spin" size={18} /> : null}
                进入工作台
              </button>
            </form>
            <p className="login-help">
              首次使用？请使用本地初始化时配置的账号。
              <br />
              原件保存在本机，必要文本片段会发送至配置的模型服务。
            </p>
          </div>
        </div>
      </div>
    );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => {
            setSelected(null);
            setArchive(false);
          }}
        >
          <span className="brand-icon">
            <FileCheck2 size={25} />
          </span>
          <strong>
            齐呈<small>PacketPilot</small>
          </strong>
        </button>
        <div className="workspace-label">
          个人工作空间 <ChevronDown size={14} />
        </div>
        <nav>
          <button
            className={!selected && !archive ? "active" : ""}
            onClick={() => {
              setSelected(null);
              setArchive(false);
            }}
          >
            <LayoutGrid size={19} />
            我的申请<span>{cases.filter((c) => !c.archived).length}</span>
          </button>
          <button
            className={!selected && archive ? "active" : ""}
            onClick={() => {
              setSelected(null);
              setArchive(true);
            }}
          >
            <Archive size={19} />
            已归档
          </button>
        </nav>
        <div className="sidebar-section">
          <span>最近申请</span>
          <button
            className="icon-button"
            aria-label="新建申请"
            onClick={() => setModal("new")}
          >
            <Plus size={16} />
          </button>
        </div>
        <div className="recent-list">
          {cases
            .filter((c) => !c.archived)
            .slice(0, 5)
            .map((c) => (
              <button
                key={c.id}
                className={selected === c.id ? "selected" : ""}
                onClick={() => openCase(c.id)}
              >
                <span className={"small-case-icon " + c.kind}>
                  <FileText size={15} />
                </span>
                <span>{c.title}</span>
              </button>
            ))}
          {!cases.length && <p>新建申请后，会显示在这里</p>}
        </div>
        <div className="sidebar-bottom">
          <div className="quiet-card">
            <ShieldCheck size={20} />
            <strong>每个结论，都能追溯</strong>
            <p>
              保留材料与要求的版本，
              <br />
              让每次补件有迹可循。
            </p>
          </div>
          <button
            className="settings-link"
            onClick={() =>
              act(async () => {
                setCapabilities(await api("/capabilities"));
                setModal("settings");
              })
            }
          >
            <Settings size={18} />
            设置与连接
          </button>
          <div className="account">
            <span className="avatar">{user.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{user}</strong>
              <small>本地工作空间</small>
            </div>
            <button
              className="icon-button"
              aria-label="退出登录"
              onClick={() =>
                act(async () => {
                  await post("/auth/logout");
                  setUser(null);
                  setSelected(null);
                })
              }
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <span>工作空间</span>
            <ChevronRight size={14} />
            <strong>{selected ? item?.title || "正在加载" : "我的申请"}</strong>
          </div>
          <span className="topbar-note">
            <ShieldCheck size={15} /> 材料准备，由你掌控
          </span>
        </header>
        {error && (
          <div role="alert" className="error-banner">
            <CircleAlert size={18} />
            {error}
            <button
              className="icon-button"
              aria-label="关闭错误"
              onClick={() => setError("")}
            >
              <X size={16} />
            </button>
          </div>
        )}
        {!selected ? (
          <div className="dashboard">
            <div className="page-heading">
              <div>
                <div className="eyebrow">APPLICATION WORKSPACE</div>
                <h1>{archive ? "已归档申请" : "我的申请"}</h1>
                <p>
                  {archive
                    ? "保留每一次准备的记录，随时回来查看。"
                    : "把复杂的申请，变成清楚的下一步。"}
                </p>
              </div>
              <button className="primary" onClick={() => setModal("new")}>
                <Plus size={18} />
                新建申请
              </button>
            </div>
            {!archive && (
              <div className="welcome-banner">
                <div>
                  <span className="mini-label">
                    <Sparkles size={15} /> 齐呈，陪你准备每一步
                  </span>
                  <h2>
                    少一点遗漏，
                    <br className="mobile-only" />
                    多一份从容。
                  </h2>
                  <p>
                    导入申请通知，让要求成为清单。
                    <br />
                    上传已有材料，每个问题都附有依据。
                  </p>
                  <button
                    className="text-action"
                    disabled={busy}
                    onClick={() => act(newExample)}
                  >
                    体验一个示例申请 <ArrowUpRight size={16} />
                  </button>
                </div>
                <div className="paper-art" aria-hidden="true">
                  <div className="paper-back"></div>
                  <div className="paper-front">
                    <span className="paper-title">
                      申请材料清单 <FileCheck2 size={22} />
                    </span>
                    <i></i>
                    <div>
                      <span>
                        <Check size={12} />
                      </span>
                      <b></b>
                    </div>
                    <div>
                      <span>
                        <Check size={12} />
                      </span>
                      <b></b>
                    </div>
                    <div>
                      <span className="unchecked"></span>
                      <b></b>
                    </div>
                  </div>
                  <span className="paper-stamp">
                    <ShieldCheck size={23} />
                    每一步，都清楚
                  </span>
                </div>
              </div>
            )}
            <div className="stats-row">
              <div>
                <span className="stat-icon">
                  <FolderOpen size={20} />
                </span>
                <div>
                  <small>进行中的申请</small>
                  <strong>{cases.filter((c) => !c.archived).length}</strong>
                </div>
              </div>
              <div>
                <span className="stat-icon amber">
                  <ListChecks size={20} />
                </span>
                <div>
                  <small>还需要处理</small>
                  <strong>
                    {
                      cases.filter(
                        (c) => !c.archived && c.checklist.status !== "ready",
                      ).length
                    }
                  </strong>
                </div>
              </div>
              <div>
                <span className="stat-icon mint">
                  <CheckCircle2 size={20} />
                </span>
                <div>
                  <small>可最终复核</small>
                  <strong>
                    {
                      cases.filter(
                        (c) => !c.archived && c.checklist.status === "ready",
                      ).length
                    }
                  </strong>
                </div>
              </div>
            </div>
            <div className="section-toolbar">
              <div className="filter-tabs">
                <button className="selected">
                  {archive ? "已归档" : "全部申请"}
                  <span>
                    {cases.filter((c) => c.archived === archive).length}
                  </span>
                </button>
              </div>
              <div className="search-box">
                <Search size={17} />
                <input
                  aria-label="搜索申请"
                  placeholder="搜索申请名称或机构"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
            </div>
            <div className="case-grid">
              {cases
                .filter(
                  (c) =>
                    c.archived === archive &&
                    (c.title + c.institution).includes(query),
                )
                .map((c) => (
                  <button
                    className="case-card"
                    key={c.id}
                    onClick={() => openCase(c.id)}
                  >
                    <div className="case-card-top">
                      <span className={"case-icon " + c.kind}>
                        <FileText size={23} />
                      </span>
                      <Badge status={c.checklist.status} />
                    </div>
                    <h3>{c.title}</h3>
                    <p>{c.institution || "尚未填写申请机构"}</p>
                    <div className="case-card-progress">
                      <span>{kinds[c.kind] || "其他申请"}</span>
                      <span>
                        {c.checklist.stale
                          ? "—"
                          : c.checklist.findings.filter(
                              (f) => f.verdict === "pass",
                            ).length}{" "}
                        / {c.checklist.requirements.length} 项已检查
                      </span>
                    </div>
                    <div className="progress-track">
                      <i
                        style={{
                          width:
                            (!c.checklist.stale &&
                            c.checklist.requirements.length
                              ? (c.checklist.findings.filter(
                                  (f) => f.verdict === "pass",
                                ).length /
                                  c.checklist.requirements.length) *
                                100
                              : 0) + "%",
                        }}
                      />
                    </div>
                    <div className="case-card-bottom">
                      <span>
                        <CalendarDays size={14} />
                        {c.deadline
                          ? date(c.deadline) + " 截止"
                          : "截止日期待确认"}
                      </span>
                      <span>
                        进入申请 <ChevronRight size={15} />
                      </span>
                    </div>
                  </button>
                ))}
            </div>
            {!cases.filter(
              (c) =>
                c.archived === archive &&
                (c.title + c.institution).includes(query),
            ).length && (
              <Empty
                icon={<FolderOpen size={30} />}
                title={query ? "没有找到匹配的申请" : "从你的第一份申请开始"}
                text="新建一个申请，或体验合成示例，看看齐呈如何帮助你。"
                action={
                  <button className="secondary" onClick={() => setModal("new")}>
                    <Plus size={16} />
                    新建申请
                  </button>
                }
              />
            )}
            <div className="dashboard-footer">
              <FileCheck2 size={16} />
              <span>齐呈帮助你检查准备情况，最终材料仍由你确认。</span>
              <span>PacketPilot · 0.1</span>
            </div>
          </div>
        ) : !item ? (
          <div className="boot">
            <LoaderCircle className="spin" /> 正在读取申请…
          </div>
        ) : (
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
                    {item.deadline
                      ? date(item.deadline) + " 截止"
                      : "截止日期待确认"}
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
                  {running ? "正在处理" : "重新预检"}
                </button>
              </div>
            </div>
            <div className="workspace-tabs">
              {(
                [
                  ["overview", "检查概览", ListChecks],
                  ["documents", "材料库", FolderOpen],
                  ["rules", "申请要求", BookOpen],
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
                    {item.checklist.stale_reason ||
                      "下方是历史结果，请重新预检。"}
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
                        : item.checklist.coverage.evaluated_count +
                          " 项已有有效结果"}
                    </span>
                  </div>
                  {!requirements.length ? (
                    <Empty
                      icon={<ListChecks size={28} />}
                      title="先把要求整理清楚"
                      text="导入申请通知，提取并审阅要求后，开始核对材料。"
                      action={
                        <button
                          className="primary"
                          onClick={() => setTab("rules")}
                        >
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
                          <div
                            className={"finding " + (good ? "good" : "")}
                            key={r.id}
                          >
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
                                    <small className="advisory-label">
                                      建议项
                                    </small>
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
                              <p>
                                {f?.reason || r.explanation || "等待执行检查"}
                              </p>
                              {f?.next_action && !good && (
                                <div className="next-action">
                                  {f.next_action}
                                </div>
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
                                            act(() =>
                                              openEvidence(c.evidence[0]),
                                            )
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
                                            act(() =>
                                              openEvidence(m.evidence[0]),
                                            )
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
                    <button
                      className="secondary full"
                      onClick={() => setTab("chat")}
                    >
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
                          href={
                            "/api/v1/cases/" + item.id + "/export?format=html"
                          }
                        >
                          下载 HTML
                        </a>
                        <a
                          className="text-action"
                          href={
                            "/api/v1/cases/" + item.id + "/export?format=md"
                          }
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
            )}
            {tab === "documents" && (
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>你的申请材料</h2>
                    <p>上传、替换与校订都会让关联检查重新核对</p>
                  </div>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => pickUpload()}
                  >
                    <Upload size={17} />
                    上传材料
                  </button>
                </div>
                <div
                  className="upload-zone"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const f = e.dataTransfer.files[0];
                    if (f) act(() => fileChange(f));
                  }}
                >
                  <Upload size={28} />
                  <strong>
                    把材料拖到这里，或{" "}
                    <button onClick={() => pickUpload()}>选择文件</button>
                  </strong>
                  <p>PDF、DOCX、TXT、MD 或图片 · 单文件最大 20 MiB</p>
                  <button
                    className="text-action"
                    onClick={() => {
                      setSource({
                        title: "补充材料",
                        text: "",
                        purpose: "material",
                        category: "",
                      });
                      setModal("source");
                    }}
                  >
                    也可以粘贴材料文本
                  </button>
                </div>
                <div className="document-list">
                  {docMaterials.map((d) => (
                    <div className="document-row" key={d.id}>
                      <span className="document-icon">
                        <FileText size={23} />
                        <small>
                          {d.filename.split(".").pop()?.toUpperCase()}
                        </small>
                      </span>
                      <button
                        className="document-name"
                        onClick={() => act(() => openDoc(d))}
                      >
                        <strong>{d.title}</strong>
                        <span>
                          版本 {d.version} · {(d.size / 1024).toFixed(1)} KB
                          {d.parse_note ? " · " + d.parse_note : ""}
                        </span>
                      </button>
                      <Badge
                        status={d.parse_status === "ready" ? "pass" : "unknown"}
                      >
                        {(
                          {
                            ready: "可读取",
                            queued: "排队中",
                            failed: "读取失败",
                            needs_review: "需核对原件",
                          } as Record<string, string>
                        )[d.parse_status] || d.parse_status}
                      </Badge>
                      <button
                        className="icon-button"
                        title="替换材料"
                        aria-label={"替换" + d.title}
                        onClick={() => pickUpload("material", d.id)}
                      >
                        <RefreshCw size={17} />
                      </button>
                      <button
                        className="icon-button danger"
                        aria-label={"删除" + d.title}
                        onClick={() =>
                          setConfirm({
                            text: "删除此材料的所有版本及受影响的历史检查？此操作不可撤销。",
                            action: async () => {
                              await api("/documents/" + d.id, {
                                method: "DELETE",
                              });
                              await refresh();
                            },
                          })
                        }
                      >
                        <Trash2 size={17} />
                      </button>
                    </div>
                  ))}
                </div>
                {!docMaterials.length && (
                  <div className="subtle-note">
                    <Info size={16} />
                    先上传手边已有的材料，不必一次准备齐全。
                  </div>
                )}
              </section>
            )}
            {tab === "rules" && (
              <div className="rules-layout">
                <section className="panel">
                  <div className="panel-header">
                    <div>
                      <h2>申请依据</h2>
                      <p>以你提供的通知为准，每项要求保留出处</p>
                    </div>
                    <button
                      className="secondary"
                      onClick={() => {
                        setSource({
                          title: "申请通知",
                          text: "",
                          purpose: "source",
                          category: "",
                        });
                        setModal("source");
                      }}
                    >
                      <Plus size={16} />
                      粘贴通知
                    </button>
                  </div>
                  {docSources.map((d) => (
                    <div className="source-row" key={d.id}>
                      <BookOpen size={22} />
                      <button onClick={() => act(() => openDoc(d))}>
                        <strong>{d.title}</strong>
                        <small>
                          版本 {d.version} ·{" "}
                          {d.parse_status === "ready" ? "可读取" : "需确认"}
                        </small>
                      </button>
                      <button
                        className="icon-button"
                        aria-label={"替换" + d.title}
                        onClick={() => pickUpload("source", d.id)}
                      >
                        <RefreshCw size={16} />
                      </button>
                    </div>
                  ))}
                  <div className="panel-footer">
                    <button
                      className="text-action"
                      onClick={() => pickUpload("source")}
                    >
                      <Upload size={15} />
                      上传通知文件
                    </button>
                    <button
                      className="primary"
                      disabled={!!running || busy || !docSources.length}
                      onClick={() => act(() => run("extract"))}
                    >
                      <Sparkles size={16} />
                      提取要求草稿
                    </button>
                  </div>
                </section>
                <section className="panel">
                  <div className="panel-header">
                    <div>
                      <h2>要求版本</h2>
                      <p>审阅草稿后启用，检查才会采用这份依据</p>
                    </div>
                  </div>
                  {!item.rule_sets?.length ? (
                    <Empty
                      icon={<Layers size={27} />}
                      title="还没有要求草稿"
                      text="先添加通知，再让齐呈整理其中的申请要求。"
                    />
                  ) : (
                    item.rule_sets.map((rs) => (
                      <div className="rule-version" key={rs.id}>
                        <div className="rule-version-title">
                          <h3>
                            版本 {rs.version}{" "}
                            <span>{rs.requirements.length} 项要求</span>
                          </h3>
                          <Badge
                            status={rs.status === "active" ? "pass" : "unknown"}
                          >
                            {
                              (
                                {
                                  active: "当前使用",
                                  draft: "待审阅",
                                  superseded: "历史版本",
                                  source_removed: "来源已移除",
                                } as Record<string, string>
                              )[rs.status]
                            }
                          </Badge>
                        </div>
                        <div className="rule-chips">
                          {rs.requirements.map((r) => (
                            <span key={r.id}>{r.title}</span>
                          ))}
                        </div>
                        <div className="rule-actions">
                          <button
                            className="secondary"
                            onClick={() => setRuleEditor(rs.requirements)}
                          >
                            <Pencil size={15} />
                            审阅与编辑
                          </button>
                          {rs.status === "draft" && (
                            <button
                              className="primary"
                              disabled={busy}
                              onClick={() =>
                                act(async () => {
                                  await post(
                                    "/rule-sets/" + rs.id + "/activate",
                                    { revision: item.revision },
                                  );
                                  await refresh();
                                  setNotice("要求已启用，请重新预检材料");
                                })
                              }
                            >
                              <Check size={16} />
                              确认启用
                            </button>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </section>
              </div>
            )}
            {tab === "chat" && (
              <div className="chat-grid">
                <section className="panel chat-panel">
                  <div className="panel-header">
                    <div className="assistant-title">
                      <span className="assistant-icon">
                        <Sparkles size={20} />
                      </span>
                      <div>
                        <h2>齐呈助手</h2>
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
                          <small>{m.role === "user" ? "你" : "齐呈助手"}</small>
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
                      aria-label="发送给齐呈助手"
                      placeholder="告诉齐呈，你想确认什么…"
                      value={chat}
                      onChange={(e) => setChat(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          if (chat.trim() && !running && !busy)
                            act(() => sendChat(chat));
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
            )}
            {tab === "history" && (
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
                          {new Date(r.created_at).toLocaleString("zh-CN")} ·
                          修订 {r.revision}
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
                  <span className="muted">删除申请会清除全部材料和历史。</span>
                  <button
                    className="text-action danger"
                    onClick={() =>
                      setConfirm({
                        text: "永久删除此申请、全部材料、对话与历史？此操作不可撤销。",
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
      {(modal === "new" || modal === "edit") && (
        <Dialog
          error={error}
          title={modal === "edit" ? "编辑申请信息" : "创建一份新的申请"}
          close={() => setModal("")}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                const c =
                  modal === "edit" && item
                    ? await api<Case>("/cases/" + item.id, {
                        method: "PATCH",
                        body: JSON.stringify({
                          ...draftCase,
                          revision: item.revision,
                          archived: item.archived,
                        }),
                      })
                    : await post<Case>("/cases", draftCase);
                setModal("");
                setDraftCase({
                  title: "",
                  institution: "",
                  kind: "exchange",
                  deadline: "",
                });
                await loadCases();
                openCase(c.id);
                setItem(c);
              });
            }}
          >
            <p className="dialog-intro">
              {modal === "edit"
                ? "修改后会提示重新核对，确保检查与当前申请信息一致。"
                : "先记下申请目标，材料可以慢慢补齐。"}
            </p>
            <label>
              申请名称
              <input
                required
                placeholder="例如：秋季校际交流申请"
                value={draftCase.title}
                onChange={(e) =>
                  setDraftCase({ ...draftCase, title: e.target.value })
                }
              />
            </label>
            <label>
              申请机构
              <input
                placeholder="学校、组织或项目名称"
                value={draftCase.institution}
                onChange={(e) =>
                  setDraftCase({ ...draftCase, institution: e.target.value })
                }
              />
            </label>
            <div className="form-row">
              <label>
                申请类型
                <select
                  value={draftCase.kind}
                  onChange={(e) =>
                    setDraftCase({ ...draftCase, kind: e.target.value })
                  }
                >
                  {Object.entries(kinds).map(([k, v]) => (
                    <option value={k} key={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                截止日期（可选）
                <input
                  type="date"
                  value={draftCase.deadline}
                  onChange={(e) =>
                    setDraftCase({ ...draftCase, deadline: e.target.value })
                  }
                />
              </label>
            </div>
            <div className="dialog-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setModal("")}
              >
                取消
              </button>
              <button className="primary" disabled={busy}>
                {modal === "edit" ? "保存修改" : "创建申请"}
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {modal === "source" && item && (
        <Dialog
          error={error}
          title={source.purpose === "source" ? "导入申请通知" : "添加材料文本"}
          close={() => setModal("")}
          wide
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await post("/cases/" + item.id + "/sources/text", source);
                setModal("");
                await refresh();
              });
            }}
          >
            <label>
              标题
              <input
                required
                value={source.title}
                onChange={(e) =>
                  setSource({ ...source, title: e.target.value })
                }
              />
            </label>
            <label>
              正文
              <textarea
                className="large-textarea"
                required
                placeholder="粘贴完整的通知或材料内容，保留原始要求和日期…"
                value={source.text}
                onChange={(e) => setSource({ ...source, text: e.target.value })}
              />
            </label>
            <p className="hint">
              齐呈会保留原文，并将每一项检查关联到具体依据。
            </p>
            <div className="dialog-actions">
              <button className="primary" disabled={busy}>
                保存原文
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {modal === "facts" && item && (
        <Dialog error={error} title="确认申请背景" close={() => setModal("")}>
          <p className="dialog-intro">
            只填写已确定的信息。修改后，相关检查需要重新核对。
          </p>
          {facts.map(([k, v], i) => (
            <div className="fact-editor" key={i}>
              <input
                aria-label={"字段" + (i + 1)}
                placeholder="例如：申请类别"
                value={k}
                onChange={(e) =>
                  setFacts(
                    facts.map((f, j) => (j === i ? [e.target.value, f[1]] : f)),
                  )
                }
              />
              <input
                aria-label={"值" + (i + 1)}
                placeholder="例如：本科交流"
                value={v}
                onChange={(e) =>
                  setFacts(
                    facts.map((f, j) => (j === i ? [f[0], e.target.value] : f)),
                  )
                }
              />
              <button
                className="icon-button"
                aria-label="移除此字段"
                onClick={() => setFacts(facts.filter((_, j) => j !== i))}
              >
                <X size={16} />
              </button>
            </div>
          ))}
          <button
            className="text-action"
            onClick={() => setFacts([...facts, ["", ""]])}
          >
            <Plus size={15} />
            添加背景字段
          </button>
          <div className="dialog-actions">
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await post("/cases/" + item.id + "/facts/confirm", {
                    revision: item.revision,
                    facts: Object.fromEntries(facts.filter(([k]) => k.trim())),
                  });
                  setModal("");
                  await refresh();
                })
              }
            >
              确认并保存
            </button>
          </div>
        </Dialog>
      )}
      {modal === "rules" && item && (
        <Dialog
          error={error}
          title="审阅申请要求"
          close={() => setModal("")}
          wide
        >
          <p className="dialog-intro">
            编辑会保存为新的草稿版本。请确认来源、适用条件和检查方式，再启用。
          </p>
          <button
            className="text-action"
            onClick={() => {
              if (!advanced) setRulesRaw(JSON.stringify(rules, null, 2));
              else {
                try {
                  setRules(JSON.parse(rulesRaw));
                } catch {
                  setError("要求格式有误");
                  return;
                }
              }
              setAdvanced(!advanced);
            }}
          >
            {advanced ? "返回可视化编辑" : "高级：编辑完整结构"}
          </button>
          {advanced ? (
            <textarea
              className="code-editor"
              value={rulesRaw}
              onChange={(e) => setRulesRaw(e.target.value)}
              aria-label="要求 JSON"
            />
          ) : (
            rules.map((r, i) => (
              <div className="rule-editor" key={r.id}>
                <label>
                  要求 {i + 1}
                  <input
                    value={r.title}
                    onChange={(e) =>
                      setRules(
                        rules.map((x, j) =>
                          j === i ? { ...x, title: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </label>
                <div className="form-row">
                  <label>
                    对应材料
                    <input
                      value={r.document_type}
                      onChange={(e) =>
                        setRules(
                          rules.map((x, j) =>
                            j === i
                              ? { ...x, document_type: e.target.value }
                              : x,
                          ),
                        )
                      }
                    />
                  </label>
                  <label>
                    检查方式
                    <select
                      value={r.kind}
                      onChange={(e) =>
                        setRules(
                          rules.map((x, j) =>
                            j === i ? { ...x, kind: e.target.value } : x,
                          ),
                        )
                      }
                    >
                      {Object.entries({
                        material_presence: "材料存在",
                        semantic_requirement: "内容核对",
                        manual_review: "人工核对",
                        file_format: "文件格式",
                        file_size: "文件大小",
                        page_count: "页数",
                        required_field: "必填字段",
                        field_consistency: "字段一致性",
                        date_constraint: "日期限制",
                      }).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <blockquote>
                  {r.source_evidence.map((e) => e.quote).join("\n")}
                </blockquote>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={r.required}
                    onChange={(e) =>
                      setRules(
                        rules.map((x, j) =>
                          j === i ? { ...x, required: e.target.checked } : x,
                        ),
                      )
                    }
                  />
                  必需要求
                </label>
                <small>
                  条件：
                  {Object.keys(r.condition).length
                    ? JSON.stringify(r.condition)
                    : "无附加条件"}
                </small>
              </div>
            ))
          )}
          <div className="dialog-actions">
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await post("/cases/" + item.id + "/rule-sets", {
                    revision: item.revision,
                    requirements: advanced ? JSON.parse(rulesRaw) : rules,
                  });
                  setModal("");
                  await refresh();
                  setNotice("已保存新草稿，请确认启用");
                })
              }
            >
              保存为新草稿
            </button>
          </div>
        </Dialog>
      )}
      {modal === "manual" && item && (
        <Dialog error={error} title="记录人工检查" close={() => setModal("")}>
          <p className="dialog-intro">
            请先查看原件，确认签署、盖章或其他需要本人核对的要求。记录仅对当前材料版本有效。
          </p>
          <label>
            确认说明
            <textarea
              required
              placeholder="说明你核对了什么…"
              value={manualNote}
              onChange={(e) => setManualNote(e.target.value)}
            />
          </label>
          <div className="dialog-actions">
            <button
              className="primary"
              disabled={busy || !manualNote.trim()}
              onClick={() =>
                act(async () => {
                  await post("/cases/" + item.id + "/attestations", {
                    revision: item.revision,
                    requirement_id: manual,
                    note: manualNote,
                  });
                  setModal("");
                  await refresh();
                })
              }
            >
              我已核对，记录确认
            </button>
          </div>
        </Dialog>
      )}
      {modal === "settings" && (
        <Dialog error={error} title="设置与连接" close={() => setModal("")}>
          <div className="settings-section">
            <h3>模型连接</h3>
            <p>
              当前模型：<strong>{capabilities?.model}</strong>
            </p>
            <p>{capabilities?.inference}</p>
            <button
              className="secondary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  const r = await post<{ ok: boolean; message?: string }>(
                    "/model/check",
                  );
                  setNotice(
                    r.ok ? "模型连接正常" : r.message || "模型连接未成功",
                  );
                })
              }
            >
              <RefreshCw size={16} />
              测试连接
            </button>
          </div>
          <div className="settings-section">
            <h3>文档读取</h3>
            <p>
              支持 PDF、DOCX、TXT、MD
              和图片保存。扫描件与图片需要提供可读副本或校订文本；当前未开启自动
              OCR。
            </p>
          </div>
          <div className="settings-section">
            <h3>本地配置</h3>
            <p>
              模型密钥和数据库凭据通过本地环境配置提供，不进入浏览器。运行数据不进入
              Git 仓库。
            </p>
            <a
              className="text-action"
              href="https://github.com/cyuanb/PacketPilot"
              target="_blank"
              rel="noreferrer"
            >
              项目与使用文档 <ExternalLink size={14} />
            </a>
          </div>
        </Dialog>
      )}
      {preview && (
        <Dialog
          error={error}
          title={preview.title}
          close={() => {
            setPreview(null);
            setModal("");
          }}
          wide
        >
          <div className="preview-meta">
            <Badge
              status={preview.parse_status === "ready" ? "pass" : "unknown"}
            >
              {preview.parse_status === "ready" ? "可读取" : "需要核对"}
            </Badge>
            <span>
              版本 {preview.version} ·{" "}
              {preview.parse_method === "user_corrected"
                ? "人工校订文本"
                : "原文提取"}
            </span>
            <a
              className="text-action"
              href={"/api/v1/documents/" + preview.id + "/content"}
              target="_blank"
              rel="noreferrer"
            >
              打开原件 <ExternalLink size={14} />
            </a>
          </div>
          {preview.parse_note && (
            <div className="subtle-note">
              <Info size={16} />
              {preview.parse_note}
            </div>
          )}
          {preview.pages.map((p) => (
            <section
              className={
                "preview-page " +
                (highlight?.page === p.number ? "highlighted" : "")
              }
              key={p.number}
            >
              <h4>{p.label}</h4>
              <pre>{p.text}</pre>
              {highlight?.page === p.number && (
                <blockquote>
                  <strong>引用片段</strong>
                  <p>{highlight.quote}</p>
                </blockquote>
              )}
            </section>
          ))}
          {!preview.pages.length && (
            <Empty
              icon={<FileText size={25} />}
              title="尚无可读取文本"
              text="打开原件核对内容，或提供校订文本。"
            />
          )}
          <div className="panel-footer">
            <button
              className="secondary"
              onClick={() => {
                setCorrection(preview.pages.map((p) => p.text).join("\n\n"));
                setModal("correction");
              }}
            >
              <Pencil size={15} />
              提供校订文本
            </button>
          </div>
          {modal === "correction" && item && (
            <div className="correction-form">
              <label>
                校订文本
                <textarea
                  className="large-textarea"
                  value={correction}
                  onChange={(e) => setCorrection(e.target.value)}
                />
              </label>
              <button
                className="primary"
                disabled={busy || !correction.trim()}
                onClick={() =>
                  act(async () => {
                    await post("/documents/" + preview.id + "/correction", {
                      revision: item.revision,
                      text: correction,
                    });
                    setPreview(null);
                    setModal("");
                    await refresh();
                  })
                }
              >
                保存为新版本
              </button>
            </div>
          )}
        </Dialog>
      )}
      {confirm && (
        <Dialog error={error} title="请确认操作" close={() => setConfirm(null)}>
          <p>{confirm.text}</p>
          <div className="dialog-actions">
            <button className="secondary" onClick={() => setConfirm(null)}>
              取消
            </button>
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await confirm.action();
                  setConfirm(null);
                })
              }
            >
              确认
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
