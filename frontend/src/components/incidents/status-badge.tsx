import { Badge } from "@/components/ui/badge";
import { statusLabel } from "@/lib/format";
import type { IncidentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_CLASS: Record<IncidentStatus, string> = {
  open: "border-sky-500/30 bg-sky-500/10 text-sky-300",
  investigating: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  awaiting_approval: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  resolved: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  dismissed: "border-border bg-muted/40 text-muted-foreground",
};

export function StatusBadge({
  status,
  className,
}: {
  status: IncidentStatus;
  className?: string;
}) {
  return (
    <Badge variant="outline" className={cn(STATUS_CLASS[status], className)}>
      {statusLabel(status)}
    </Badge>
  );
}
