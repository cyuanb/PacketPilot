export const tabs = [
  "overview",
  "documents",
  "rules",
  "chat",
  "history",
  "issues",
  "packets",
  "parsing",
  "matching",
  "work",
  "processing",
  "collaboration",
] as const;
export type Tab = (typeof tabs)[number];
export type WorkspaceRoute = {
  selected: string | null;
  tab: Tab;
  archive: boolean;
  subjects?: boolean;
  community?: boolean;
  library?: "all" | "inbox";
  assetId?: string;
};
const home: WorkspaceRoute = {
  selected: null,
  tab: "overview",
  archive: false,
};
const casePath = /^#(?:case\/|\/cases\/)([0-9a-f-]{36})(?:\/([^/]+))?\/?$/i;

export function parseRoute(hash: string): WorkspaceRoute {
  if (hash === "#/community") return { ...home, community: true };
  if (hash === "#/library") return { ...home, library: "all" };
  if (hash === "#/inbox") return { ...home, library: "inbox" };
  const asset = hash.match(/^#\/library\/([0-9a-f-]{36})\/?$/i);
  if (asset) return { ...home, library: "all", assetId: asset[1] };
  if (hash === "#/subjects") return { ...home, subjects: true };
  if (hash === "#/archive") return { ...home, archive: true };
  const match = hash.match(casePath);
  if (!match) return { ...home };
  return {
    selected: match[1],
    tab: tabs.includes(match[2] as Tab) ? (match[2] as Tab) : "overview",
    archive: false,
  };
}

export function routeHash(route: WorkspaceRoute) {
  if (route.community && !route.selected) return "#/community";
  if (route.library && !route.selected)
    return route.assetId
      ? "#/library/" + route.assetId
      : route.library === "inbox"
        ? "#/inbox"
        : "#/library";
  if (route.subjects && !route.selected) return "#/subjects";
  return route.selected
    ? `#/cases/${route.selected}/${route.tab}`
    : route.archive
      ? "#/archive"
      : "#/cases";
}
