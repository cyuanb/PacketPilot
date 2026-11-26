import { useCallback, useEffect, useRef, useState } from "react";

export function useAsyncAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const isCurrent = useCallback(() => mounted.current, []);
  const act = useCallback(async (fn: () => Promise<void>) => {
    if (!mounted.current) return;
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (error) {
      if (mounted.current)
        setError(error instanceof Error ? error.message : "操作未完成，请重试");
    } finally {
      if (mounted.current) setBusy(false);
    }
  }, []);
  return { busy, error, setError, act, isCurrent };
}
