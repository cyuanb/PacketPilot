export type SubjectKind = "person" | "organization";
export type SubjectRole =
  | "applicant"
  | "recommender"
  | "representative"
  | "organization"
  | "contact"
  | "other";
export type Subject = {
  id: string;
  workspace_id: string;
  kind: SubjectKind;
  name: string;
  label: string;
  attributes: Record<string, string>;
  archived: boolean;
  revision: number;
  created_at: string;
  updated_at: string;
};
export type SubjectList = {
  items: Subject[];
  total: number;
  limit: number;
  offset: number;
};
export type SubjectDetail = Subject & {
  cases: { id: string; title: string; role: SubjectRole }[];
};
export type CaseSubject = {
  subject_id: string;
  role: SubjectRole;
  kind: SubjectKind;
  name: string;
  label: string;
  revision: number;
  archived: boolean;
};
export type WorkspaceInfo = {
  id: string;
  name: string;
  revision: number;
  role: "owner";
};
