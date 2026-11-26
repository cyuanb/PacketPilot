import {
  ArrowUpRight,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  FileText,
  FolderOpen,
  ListChecks,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { date } from "../../api";
import type { WorkspaceState } from "../../app/useWorkspace";
import { Badge } from "../../components/Badge";
import { Empty } from "../../components/Empty";
import { kinds } from "./constants";
type Props = Pick<
  WorkspaceState,
  | "archive"
  | "setModal"
  | "busy"
  | "act"
  | "newExample"
  | "cases"
  | "query"
  | "setQuery"
  | "openCase"
>;
export function Dashboard({
  archive,
  setModal,
  busy,
  act,
  newExample,
  cases,
  query,
  setQuery,
  openCase,
}: Props) {
  return (
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
              <Sparkles size={15} /> 齐备，陪你准备每一步
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
            <span>{cases.filter((c) => c.archived === archive).length}</span>
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
                    : c.checklist.findings.filter((f) => f.verdict === "pass")
                        .length}{" "}
                  / {c.checklist.requirements.length} 项已检查
                </span>
              </div>
              <div className="progress-track">
                <i
                  style={{
                    width:
                      (!c.checklist.stale && c.checklist.requirements.length
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
                  {c.deadline ? date(c.deadline) + " 截止" : "截止日期待确认"}
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
          c.archived === archive && (c.title + c.institution).includes(query),
      ).length && (
        <Empty
          icon={<FolderOpen size={30} />}
          title={query ? "没有找到匹配的申请" : "从你的第一份申请开始"}
          text="新建一个申请，或体验合成示例，看看齐备如何帮助你。"
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
        <span>齐备帮助你检查准备情况，最终材料仍由你确认。</span>
        <span>PacketPilot · 0.1.1</span>
      </div>
    </div>
  );
}
