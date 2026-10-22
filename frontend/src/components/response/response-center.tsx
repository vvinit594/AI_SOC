"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { StatusBadge } from "@/components/incidents/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getIncident } from "@/lib/data";
import { shortId } from "@/lib/format";
import type { ActionStatus, ResponseAction } from "@/lib/types";

type Decision = {
  status: ActionStatus;
  decidedAt: string;
  decidedBy: string;
};

export function ResponseCenter({ actions }: { actions: ResponseAction[] }) {
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});

  const rows = useMemo(
    () =>
      actions.map((action) => ({
        ...action,
        status: decisions[action.id]?.status ?? action.status,
        decidedAt: decisions[action.id]?.decidedAt ?? action.decidedAt,
        decidedBy: decisions[action.id]?.decidedBy ?? action.decidedBy,
      })),
    [actions, decisions],
  );

  function decide(id: string, status: Exclude<ActionStatus, "proposed">) {
    setDecisions((current) => ({
      ...current,
      [id]: {
        status,
        decidedAt: new Date().toISOString(),
        decidedBy: "local-analyst (mock)",
      },
    }));
  }

  return (
    <div className="grid gap-4">
      {rows.map((action) => {
        const incident = getIncident(action.incidentId);
        return (
          <Card key={action.id}>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle className="capitalize">
                    {action.actionType.replaceAll("_", " ")}
                  </CardTitle>
                  <CardDescription>
                    Target {action.target} · risk {action.riskLevel}
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">Simulated</Badge>
                  <Badge variant="secondary" className="capitalize">
                    {action.status.replaceAll("_", " ")}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3">
              <p className="text-sm">{action.reason}</p>
              <p className="font-mono text-xs text-muted-foreground">
                Evidence: {action.evidenceIds.map((id) => shortId(id, 8)).join(", ")}
              </p>
              {incident ? (
                <p className="text-sm text-muted-foreground">
                  Incident{" "}
                  <Link className="text-primary hover:underline" href={`/incidents/${incident.id}`}>
                    {incident.title}
                  </Link>{" "}
                  <StatusBadge status={incident.status} className="ml-1 align-middle" />
                </p>
              ) : null}
              {action.decidedAt ? (
                <p className="text-xs text-muted-foreground">
                  Decision recorded locally as {action.status} by {action.decidedBy}. Not
                  persisted — Phase 8 writes this to PostgreSQL.
                </p>
              ) : null}
              {action.status === "proposed" ? (
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => decide(action.id, "approved")}>
                    Approve (simulate)
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => decide(action.id, "rejected")}
                  >
                    Reject
                  </Button>
                </div>
              ) : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
