import type { Scenario, DocumentLink } from "../features/workflow/types";
import type { CaseSubject } from "../features/subjects/types";

export type Evidence = { document_id: string; page: number; quote: string };
export type Requirement = {
  id: string;
  title: string;
  kind: string;
  document_type: string;
  required: boolean;
  condition: Record<string, unknown>;
  parameters: Record<string, unknown>;
  source_evidence: Evidence[];
  explanation: string;
};
export type Finding = {
  requirement_id: string;
  applicability: string;
  verdict: string;
  method: string;
  reason: string;
  next_action: string;
  evidence: Evidence[];
  evaluation_state?: "evaluated" | "not_evaluated" | "invalid";
  field_coverage?: {
    document_id: string;
    field: string;
    status: string;
    values: string[];
    evidence: Evidence[];
  }[];
  material_matches?: {
    document_id: string;
    status: string;
    reason: string;
    evidence: Evidence[];
  }[];
};
export type Doc = {
  asset_revision_id?: string | null;
  id: string;
  logical_id: string;
  version: number;
  title: string;
  filename: string;
  purpose: string;
  category: string;
  mime: string;
  size: number;
  parse_status: string;
  parse_note: string;
  parse_method: string;
  pages: { number: number; label: string; text: string }[];
  page_count: number;
};
export type Run = {
  id: string;
  kind: string;
  status: string;
  revision: number;
  error: string;
  created_at: string;
  updated_at: string;
  skill_hash: string;
  model: string;
  result: {
    answer?: string;
    findings?: Finding[];
    proposed_facts?: Record<string, string>;
    question?: string;
    usage?: Record<string, number>[];
  };
};
export type Case = {
  scenario?: Scenario | null;
  document_links?: DocumentLink[];
  workspace_id: string;
  subjects?: CaseSubject[];
  id: string;
  title: string;
  institution: string;
  kind: string;
  deadline: string;
  archived: boolean;
  revision: number;
  facts: Record<string, string | number | boolean>;
  created_at: string;
  updated_at: string;
  documents?: Doc[];
  rule_sets?: {
    id: string;
    version: number;
    status: string;
    requirements: Requirement[];
  }[];
  messages?: {
    id: string;
    role: string;
    content: string;
    created_at: string;
  }[];
  runs?: Run[];
  checklist: {
    status: string;
    stale: boolean;
    findings: Finding[];
    requirements: Requirement[];
    run_id?: string;
    checked_at?: string;
    checked_revision?: number;
    engine_version: string | null;
    legacy: boolean;
    stale_reason: string;
    run_status: string | null;
    can_export: boolean;
    advisory_count: number;
    coverage: {
      expected_count: number;
      evaluated_count: number;
      complete: boolean;
      missing_ids: string[];
      duplicate_ids: string[];
      unexpected_ids: string[];
      invalid_ids: string[];
      invalid_rule_ids: string[];
    };
    attestations: { requirement_id: string; note: string }[];
  };
};
