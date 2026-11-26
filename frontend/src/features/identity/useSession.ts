import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { useAsyncAction } from "../../app/useAsyncAction";

export function useSession() {
  const [user, setUser] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const action = useAsyncAction();
  useEffect(() => {
    const controller = new AbortController();
    api<{ username: string }>("/me", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setUser(value.username);
      })
      .catch(() => {})
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);
  return { user, setUser, loading, ...action };
}
export type SessionState = ReturnType<typeof useSession>;
