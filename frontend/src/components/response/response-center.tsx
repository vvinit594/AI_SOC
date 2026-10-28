"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { StatusBadge } from "@/components/incidents/status-badge";
import { ReportDownloadButton } from "@/components/reports/report-download-button";
import { AuditHistory } from "@/components/response/audit-history";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  actionTypeLabel,
  containmentLabel,
  mapResponseAction,
  replaceIncidentAction,
} from "@/lib/actions";
import {
  ApiError,
  approveAction,
  getIncidentApi,
  listIncidentsApi,
  rejectAction,
} from "@/lib/api";
import { analystErrorMessage, shouldBlockInFlight } from "@/lib/analyst-errors";
import { formatUtc } from "@/lib/format";
import type { ActionStatus, PersistedIncident, ResponseAction } from "@/lib/types";

function approvalClass(status: ActionStatus): string {
  if (status === "approved") {
    return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  }
  if (status === "rejected") {
    return "border-destructive/30 bg-destructive/10 text-destructive";
  }
  return "border-amber-500/30 bg-amber-500/10 text-amber-200";
}

export function ResponseCenter() {
  const [incidents, setIncidents] = useState<PersistedIncident[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [auditKey, setAuditKey] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listIncidentsApi(controller.signal)
      .then((rows) => {
        setIncidents(rows);
        setLoadError(null);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        setLoadError(analystErrorMessage(caught));
        setIncidents([]);
      });
    return () => controller.abort();
  }, []);

  async function refreshIncident(incidentId: string) {
    const latest = await getIncidentApi(incidentId);
    setIncidents((current) =>
      (current ?? []).map((item) => (item.id === incidentId ? latest : item)),
    );
  }

  async function decide(action: ResponseAction, decision: Exclude<ActionStatus, "proposed">) {
    if (shouldBlockInFlight(pendingActionId !== null)) {
      return;
    }
    setPendingActionId(action.id);
    setActionError(null);
    setNotice(null);
    try {
      const payload =
        decision === "approved" ? await approveAction(action.id) : await rejectAction(action.id);
      const updated = mapResponseAction(payload);
      setIncidents((current) =>
        replaceIncidentAction(current ?? [], updated, payload.incident_status),
      );
      setAuditKey((value) => value + 1);
      setNotice(
        `${actionTypeLabel(updated.actionType)} recorded as ${updated.approvalStatus} by ${updated.actor ?? "unknown"}.`,
      );
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        return;
      }
      setActionError(analystErrorMessage(caught));
      if (caught instanceof ApiError && caught.status === 409) {
        try {
          await refreshIncident(action.incidentId);
          setAuditKey((value) => value + 1);
        } catch {
          /* keep the decision error */
        }
      }
    } finally {
      setPendingActionId(null);
    }
  }

  if (incidents === null && !loadError) {
    return (
      <div className="grid gap-4" aria-busy="true" aria-label="Loading response actions">
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }

  if (loadError) {
    return (
      <p className="text-sm text-destructive" role="alert">
        {loadError}
      </p>
    );
  }

  const withActions = (incidents ?? []).filter((incident) => incident.actions.length > 0);

  if (withActions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No persisted response recommendations. Investigate an incident so the response planner
        can store simulated actions.
      </p>
    );
  }

  return (
    <div className="grid gap-6">
      {notice ? (
        <p className="text-sm text-emerald-300" aria-live="polite">
          {notice}
        </p>
      ) : null}
      {actionError ? (
        <p className="text-sm text-destructive" role="alert">
          {actionError}
        </p>
      ) : null}
      {withActions.map((incident) => (
        <Card key={incident.id}>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>
                  <Link className="hover:text-primary hover:underline" href={`/incidents/${incident.id}`}>
                    {incident.title}
                  </Link>
                </CardTitle>
                <CardDescription>
                  {incident.actions.length} simulated recommendation
                  {incident.actions.length === 1 ? "" : "s"}. Deciding one action does not
                  decide the others.
                </CardDescription>
              </div>
              <StatusBadge status={incident.status} />
            </div>
          </CardHeader>
          <CardContent className="grid gap-4">
            {incident.actions.map((action) => {
              const pending = pendingActionId === action.id;
              const awaitingDecision = action.approvalStatus === "proposed";
              return (
                <article key={action.id} className="grid gap-3 rounded-lg border border-border/70 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-medium capitalize">
                        {actionTypeLabel(action.actionType)}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        Target {action.target ?? "—"} · risk {action.riskLevel}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">Simulated</Badge>
                      <Badge variant="outline" className={approvalClass(action.approvalStatus)}>
                        {action.approvalStatus.replaceAll("_", " ")}
                      </Badge>
                      <Badge variant="secondary">
                        {action.executionStatus.replaceAll("_", " ")}
                      </Badge>
                    </div>
                  </div>
                  <p className="text-sm">{action.reason}</p>
                  <p className="text-sm font-medium">{containmentLabel(action)}</p>
                  {action.decidedAt ? (
                    <p className="text-xs text-muted-foreground">
                      Decision recorded {formatUtc(action.decidedAt)} by {action.actor ?? "—"}.
                    </p>
                  ) : null}
                  {awaitingDecision ? (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        onClick={() => void decide(action, "approved")}
                        disabled={pendingActionId !== null}
                        aria-busy={pending}
                      >
                        {pending ? "Saving…" : "Approve (simulate)"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void decide(action, "rejected")}
                        disabled={pendingActionId !== null}
                        aria-busy={pending}
                      >
                        {pending ? "Saving…" : "Reject"}
                      </Button>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      This recommendation is no longer awaiting a decision.
                    </p>
                  )}
                </article>
              );
            })}
            <div className="grid gap-3 border-t border-border/60 pt-3">
              <div>
                <p className="mb-2 text-sm font-medium">Audit history</p>
                <AuditHistory incidentId={incident.id} refreshKey={auditKey} />
              </div>
              <ReportDownloadButton incidentId={incident.id} />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
