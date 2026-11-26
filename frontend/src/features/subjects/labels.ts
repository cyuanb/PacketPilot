import type { SubjectKind, SubjectRole } from "./types";

export const kindLabels = { person: "个人", organization: "组织" };
export const roleLabels: Record<SubjectRole, string> = {
  applicant: "申请主体",
  recommender: "推荐人",
  representative: "经办人",
  organization: "关联组织",
  contact: "联系人",
  other: "其他相关主体",
};
export const attributeLabels: Record<SubjectKind, Record<string, string>> = {
  person: { email: "邮箱", phone: "联系电话", affiliation: "所属学校或单位" },
  organization: {
    registration_number: "组织登记号（可选）",
    contact_email: "联系邮箱",
    contact_phone: "联系电话",
  },
};
export function allowsRole(kind: SubjectKind, role: SubjectRole) {
  if (role === "organization") return kind === "organization";
  if (["recommender", "representative", "contact"].includes(role))
    return kind === "person";
  return true;
}
export function subjectCaption(subject: {
  id: string;
  name: string;
  kind: SubjectKind;
  label: string;
}) {
  return `${subject.name} · ${kindLabels[subject.kind]}${subject.label ? " · " + subject.label : ""} · ${subject.id.slice(0, 8)}`;
}
