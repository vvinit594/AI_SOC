import { CheckCircle2, CircleDashed, LoaderCircle, ShieldAlert, PauseCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { AGENT_LABELS } from "@/lib/format";
import type { AgentRun, AgentRunStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_ICON: Record<AgentRunStatus, typeof CheckCircle2> = {
  queued: CircleDashed,
  running: LoaderCircle,
  completed: CheckCircle2,
  failed: ShieldAlert,
  waiting_for_approval: PauseCircle,
};

const STATUS_CLASS: Record<AgentRunStatus, string> = {
  queued: "text-muted-foreground",
  running: "text-sky-300",
  completed: "text-emerald-300",
  failed: "text-red-300",
  waiting_for_approval: "text-amber-200",
};

export function AgentStatusList({ agents }: { agents: AgentRun[] }) {
  const done = agents.filter(
    (agent) =>
      agent.status === "completed" ||
      agent.status === "failed" ||
      agent.status === "waiting_for_approval",
  ).length;
  const progress = Math.round((done / agents.length) * 100);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent workflow</CardTitle>
        <Progress value={progress} aria-label="Investigation progress">
          <span className="text-xs text-muted-foreground">
            {done} of {agents.length} nodes finished
          </span>
        </Progress>
      </CardHeader>
      <CardContent className="grid gap-3">
        {agents.map((run) => {
          const Icon = STATUS_ICON[run.status];
          return (
            <article
              key={run.agent}
              className="rounded-lg border border-border/80 bg-background/40 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Icon
                    className={cn(
                      "size-4",
                      STATUS_CLASS[run.status],
                      run.status === "running" && "animate-spin",
                    )}
                    aria-hidden="true"
                  />
                  <h3 className="font-medium">{AGENT_LABELS[run.agent]}</h3>
                </div>
                <Badge variant="outline" className="capitalize">
                  {run.status.replaceAll("_", " ")}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{run.finding}</p>
              {run.error ? (
                <p className="mt-2 text-xs text-amber-200">Error: {run.error}</p>
              ) : null}
            </article>
          );
        })}
      </CardContent>
    </Card>
  );
}
