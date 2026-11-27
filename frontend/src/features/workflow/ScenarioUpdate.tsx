import { useEffect, useState } from "react";
import { api, post, type Case } from "../../api";
import type { Scenario } from "./types";

export function ScenarioUpdate({
  item,
  refresh,
}: {
  item: Case;
  refresh: () => Promise<void>;
}) {
  const [update, setUpdate] = useState<{
    current: Scenario;
    latest: Scenario;
    available: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    if (item.scenario)
      api<{ current: Scenario; latest: Scenario; available: boolean }>(
        `/cases/${item.id}/scenario-update`,
      )
        .then((v) => {
          if (live) setUpdate(v);
        })
        .catch((e) => {
          if (live) setError(e.message);
        });
    return () => {
      live = false;
    };
  }, [item.id, item.revision, item.scenario]);
  if (!update?.available) return error ? <p role="alert">{error}</p> : null;
  return (
    <details className="scenario-update">
      <summary>
        场景引导有新版本：v{update.current.version} → v{update.latest.version}
      </summary>
      <p>{update.latest.description}</p>
      <p>材料槽位：{update.latest.slots?.map((s) => s.label).join("、")}</p>
      <p>输出建议：{update.latest.output?.naming}</p>
      <p className="hint">
        只更新引导、槽位建议和输出规范；现有材料、通知与启用要求不自动改变。
      </p>
      {error && <p role="alert">{error}</p>}
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await post(`/cases/${item.id}/scenario-update`, {
              revision: item.revision,
            });
            await refresh();
          } catch (e) {
            setError(e instanceof Error ? e.message : "更新失败");
          } finally {
            setBusy(false);
          }
        }}
      >
        确认采用新版引导
      </button>
    </details>
  );
}
