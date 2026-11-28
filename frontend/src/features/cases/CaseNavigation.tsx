import {
  Archive,
  BookOpen,
  CalendarDays,
  FolderOpen,
  ListChecks,
} from "lucide-react";
import type { Tab } from "../../app/routes";

const groups = [
  {
    id: "review",
    label: "检查与补件",
    icon: ListChecks,
    tabs: [
      ["overview", "检查概览"],
      ["issues", "问题与补件"],
      ["history", "检查历史"],
    ],
  },
  {
    id: "materials",
    label: "材料管理",
    icon: FolderOpen,
    tabs: [
      ["documents", "材料库"],
      ["parsing", "解析与校订"],
      ["matching", "材料归属"],
      ["processing", "材料加工"],
    ],
  },
  {
    id: "requirements",
    label: "申请要求",
    icon: BookOpen,
    tabs: [["rules", "申请要求"]],
  },
  {
    id: "coordination",
    label: "计划与协作",
    icon: CalendarDays,
    tabs: [
      ["work", "计划与期限"],
      ["collaboration", "收集与复核"],
      ["chat", "对话助手"],
    ],
  },
  {
    id: "delivery",
    label: "打包交付",
    icon: Archive,
    tabs: [["packets", "材料包与交付"]],
  },
] as const;

export function CaseNavigation({
  tab,
  setTab,
  materialCount,
}: {
  tab: Tab;
  setTab: (tab: Tab) => void;
  materialCount: number;
}) {
  const active =
    groups.find((group) => group.tabs.some(([key]) => key === tab)) ||
    groups[0];
  return (
    <div className="case-navigation">
      <nav className="case-navigation-groups" aria-label="申请功能分组">
        {groups.map((group) => (
          <button
            key={group.id}
            className={active.id === group.id ? "selected" : ""}
            aria-current={active.id === group.id ? "true" : undefined}
            onClick={() => {
              if (active.id !== group.id) setTab(group.tabs[0][0]);
            }}
          >
            <group.icon size={17} aria-hidden="true" />
            <span>{group.label}</span>
            {group.id === "materials" && <small>{materialCount}</small>}
          </button>
        ))}
      </nav>
      {active.tabs.length > 1 && (
        <nav
          className="case-navigation-items"
          aria-label={`${active.label}功能`}
        >
          {active.tabs.map(([key, label]) => (
            <button
              key={key}
              aria-current={tab === key ? "page" : undefined}
              className={tab === key ? "selected" : ""}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </nav>
      )}
    </div>
  );
}
