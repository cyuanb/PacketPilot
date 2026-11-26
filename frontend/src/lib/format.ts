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
