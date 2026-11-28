import { useState } from "react";
import { post, type Case, type Doc } from "../../api";
import { Badge } from "../../components/Badge";

export function MaterialReviewControl({
  item,
  document,
  changed,
}: {
  item: Case;
  document: Doc;
  changed: (document: Doc) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const state = document.confirmation?.state || "pending";
  const current = item.documents?.some(
    (d) =>
      d.id === document.id &&
      d.parse_revision_id === document.parse_revision_id,
  );
  const confirmed = state === "confirmed";
  return (
    <div className="material-review-control">
      <Badge status={confirmed && current ? "pass" : "unknown"}>
        {!current
          ? "历史版本"
          : (
              {
                confirmed: "已人工确认",
                stale: "变更后待确认",
                excluded: "已排除",
                pending: "待人工确认",
              } as Record<string, string>
            )[state]}
      </Badge>
      <button
        className={confirmed ? "text-action" : "secondary"}
        disabled={
          busy ||
          !current ||
          document.parse_status === "queued" ||
          state === "excluded"
        }
        title="记录本人已核对当前原件与归属信息；不会替代读取、规则检查或签名等逐项确认"
        onClick={async () => {
          setBusy(true);
          setError("");
          try {
            const next = await post<Doc>(
              `/documents/${document.id}/confirmation`,
              {
                revision: item.revision,
                parse_revision_id: document.parse_revision_id,
                confirmed: !confirmed,
              },
            );
            await changed(next);
          } catch (e) {
            setError(e instanceof Error ? e.message : "确认失败");
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "正在保存…" : confirmed ? "撤销确认" : "确认本版材料"}
      </button>
      {error && (
        <span role="alert" className="error-text">
          {error}
        </span>
      )}
    </div>
  );
}
