import { CheckCircle2, CircleAlert, Clock3 } from "lucide-react";
import { type ReactNode } from "react";
import { statusLabels } from "../api";
const verdictIcon = (status: string) =>
  status === "pass" || status === "ready" ? (
    <CheckCircle2 size={17} />
  ) : status === "not_ready" || status === "unknown" ? (
    <Clock3 size={17} />
  ) : (
    <CircleAlert size={17} />
  );
export function Badge({
  status,
  children,
}: {
  status: string;
  children?: ReactNode;
}) {
  return (
    <span className={"badge " + status}>
      {verdictIcon(status)}
      {children || statusLabels[status] || status}
    </span>
  );
}
