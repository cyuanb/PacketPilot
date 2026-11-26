import { useCallback, useEffect, useSyncExternalStore } from "react";
import { api } from "../api/client";
import type { QueryClient } from "./queryClient";

export function useResource<T>(client: QueryClient, path: string) {
  const subscribe = useCallback(
    (notify: () => void) => client.subscribe(path, notify),
    [client, path],
  );
  const snapshot = useCallback(() => client.snapshot<T>(path), [client, path]);
  const state = useSyncExternalStore(subscribe, snapshot);
  const reload = useCallback(
    (force = true) =>
      client.fetch<T>(path, (signal) => api(path, { signal }), force),
    [client, path],
  );
  useEffect(() => {
    reload(false).catch(() => {});
  }, [reload]);
  return { ...state, reload };
}
