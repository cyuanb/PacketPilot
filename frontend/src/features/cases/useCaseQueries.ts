import { useCallback, useEffect, useSyncExternalStore } from "react";
import { api } from "../../api/client";
import type { Case } from "../../api/types";
import type { QueryClient } from "../../app/queryClient";

function useQuery<T>(client: QueryClient, key: string) {
  const subscribe = useCallback(
    (notify: () => void) => client.subscribe(key, notify),
    [client, key],
  );
  const getSnapshot = useCallback(() => client.snapshot<T>(key), [client, key]);
  return useSyncExternalStore(subscribe, getSnapshot);
}

export function useCaseQueries(client: QueryClient, selected: string | null) {
  const list = useQuery<Case[]>(client, "/cases");
  const detailKey = selected ? "/cases/" + selected : "idle";
  const detail = useQuery<Case>(client, detailKey);
  const loadCases = useCallback(
    (force = false) =>
      client.fetch<Case[]>(
        "/cases",
        (signal) => api("/cases", { signal }),
        force,
      ),
    [client],
  );
  const loadDetail = useCallback(
    async (force = false) => {
      if (selected)
        return client.fetch<Case>(
          detailKey,
          (signal) => api(detailKey, { signal }),
          force,
        );
    },
    [client, detailKey, selected],
  );
  useEffect(() => {
    loadCases().catch(() => {});
    loadDetail().catch(() => {});
  }, [loadCases, loadDetail]);
  const refresh = useCallback(async () => {
    await Promise.all([loadDetail(true), loadCases(true)]);
  }, [loadCases, loadDetail]);
  const setItem = useCallback(
    (item: Case) => client.set("/cases/" + item.id, item),
    [client],
  );
  return {
    cases: list.data || [],
    item: selected ? detail.data || null : null,
    queryError: detail.error?.message || list.error?.message || "",
    loadCases,
    loadDetail,
    refresh,
    setItem,
  };
}
