import type { Case } from "../../api/types";

export function checkReadiness(item: Case) {
  const sources = (item.documents || []).filter(
    (d) => d.purpose === "source" && d.parse_status === "ready",
  );
  const rules = item.checklist.requirements;
  const rulesCurrent =
    rules.length > 0 &&
    rules.every((r) =>
      r.source_evidence.every((e) =>
        sources.some(
          (d) =>
            d.id === e.document_id &&
            (!e.parse_revision_id ||
              e.parse_revision_id === d.parse_revision_id),
        ),
      ),
    );
  const hasSubject = !!item.subjects?.some(
    (s) =>
      s.role === "applicant" &&
      !s.archived &&
      (!item.scenario || s.kind === item.scenario.primary_subject_kind),
  );
  const reason = !rulesCurrent
    ? "请先确认当前通知并启用要求"
    : item.scenario && !hasSubject
      ? "请先关联有效的申请主体"
      : "";
  return { rulesCurrent, hasSubject, canCheck: !reason, reason };
}
