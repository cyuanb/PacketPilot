export const date = (value: string) => {
  if (!value) return "未设置";
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const parsed = new Date(dateOnly ? value + "T00:00:00Z" : value);
  if (
    Number.isNaN(parsed.getTime()) ||
    (dateOnly && parsed.toISOString().slice(0, 10) !== value)
  )
    return "待确认";
  return parsed.toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    ...(dateOnly ? { timeZone: "UTC" } : {}),
  });
};
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
