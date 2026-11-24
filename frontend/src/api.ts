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
};
export type Doc = {
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
    attestations: { requirement_id: string; note: string }[];
  };
};
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("X-PacketPilot", "1");
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch("/api/v1" + path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.message === "string"
        ? error.message
        : "请求未完成 (" + response.status + ")",
    );
  }
  return response.json();
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
export const date = (value: string) =>
  value
    ? new Date(value).toLocaleDateString("zh-CN", {
        month: "long",
        day: "numeric",
      })
    : "未设置";
export const statusLabels: Record<string, string> = {
  not_ready: "等待准备",
  blocked: "待补齐",
  needs_review: "待确认",
  ready: "可最终复核",
  stale: "需要复检",
  pass: "已检查",
  fail: "不符合",
  missing: "待补齐",
  conflict: "信息冲突",
  unknown: "待确认",
};
