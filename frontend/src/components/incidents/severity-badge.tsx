import { Badge } from "@/components/ui/badge";
import { severityLabel } from "@/lib/format";
import type { Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

const SEVERITY_CLASS: Record<Severity, string> = {
  critical:
    "border-red-500/30 bg-red-500/15 text-red-300 dark:border-red-400/25 dark:text-red-300",
  high: "border-orange-500/30 bg-orange-500/15 text-orange-300",
  medium: "border-amber-500/30 bg-amber-500/15 text-amber-200",
  low: "border-cyan-500/30 bg-cyan-500/15 text-cyan-300",
};

export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={cn("capitalize", SEVERITY_CLASS[severity], className)}
    >
      {severityLabel(severity)}
    </Badge>
  );
}
