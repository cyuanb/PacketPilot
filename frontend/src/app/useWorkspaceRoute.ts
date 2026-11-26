import { useCallback, useEffect, useState } from "react";
import { parseRoute, routeHash, type Tab, type WorkspaceRoute } from "./routes";

export function useWorkspaceRoute() {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const sync = () => {
      const next = parseRoute(window.location.hash);
      const canonical = routeHash(next);
      if (window.location.hash !== canonical)
        window.history.replaceState(null, "", canonical);
      setRoute(next);
    };
    sync();
    window.addEventListener("hashchange", sync);
    window.addEventListener("popstate", sync);
    return () => {
      window.removeEventListener("hashchange", sync);
      window.removeEventListener("popstate", sync);
    };
  }, []);
  const navigate = useCallback((next: WorkspaceRoute) => {
    if (window.location.hash !== routeHash(next))
      window.history.pushState(null, "", routeHash(next));
    setRoute(next);
  }, []);
  const goHome = useCallback(
    (archive = false) => navigate({ selected: null, tab: "overview", archive }),
    [navigate],
  );
  const openCase = useCallback(
    (selected: string) =>
      navigate({ selected, tab: "overview", archive: false }),
    [navigate],
  );
  const setTab = useCallback(
    (tab: Tab) => navigate({ ...route, tab }),
    [route, navigate],
  );
  return { ...route, goHome, openCase, setTab };
}
export type WorkspaceNavigation = ReturnType<typeof useWorkspaceRoute>;
