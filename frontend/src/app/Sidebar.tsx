import {
  Archive,
  ChevronDown,
  FileCheck2,
  FileText,
  LayoutGrid,
  LogOut,
  Plus,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { api, post } from "../api";
import type { WorkspaceState } from "./useWorkspace";
type Props = Pick<
  WorkspaceState,
  | "setSelected"
  | "selected"
  | "archive"
  | "cases"
  | "setModal"
  | "openCase"
  | "act"
  | "setCapabilities"
  | "user"
  | "setUser"
  | "goHome"
>;
export function Sidebar({
  setSelected,
  selected,
  archive,
  cases,
  setModal,
  openCase,
  act,
  setCapabilities,
  user,
  setUser,
  goHome,
}: Props) {
  return (
    <aside className="sidebar">
      <button
        className="brand"
        onClick={() => {
          goHome(false);
        }}
      >
        <span className="brand-icon">
          <FileCheck2 size={25} />
        </span>
        <strong>
          齐备<small>PacketPilot</small>
        </strong>
      </button>
      <div className="workspace-label">
        个人工作空间 <ChevronDown size={14} />
      </div>
      <nav>
        <button
          className={!selected && !archive ? "active" : ""}
          onClick={() => {
            goHome(false);
          }}
        >
          <LayoutGrid size={19} />
          我的申请<span>{cases.filter((c) => !c.archived).length}</span>
        </button>
        <button
          className={!selected && archive ? "active" : ""}
          onClick={() => {
            goHome(true);
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
  );
}
