"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ReportDownloadButton } from "@/components/reports/report-download-button";
import { AuditHistory } from "@/components/response/audit-history";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { actionTypeLabel, containmentLabel } from "@/lib/actions";
import { getIncidentApi } from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import type { PersistedIncident } from "@/lib/types";

export function IncidentLiveResponse({ incidentId }: { incidentId: string }) {
  const [incident, setIncident] = useState<PersistedIncident | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getIncidentApi(incidentId, controller.signal)
      .then((row) => {
        setIncident(row);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        setError(analystErrorMessage(caught));
      });
    return () => controller.abort();
  }, [incidentId]);

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Persisted response recommendations</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}
          {incident === null && !error ? (
            <div aria-busy="true" aria-label="Loading response recommendations">
              <Skeleton className="h-16" />
            </div>
          ) : null}
          {incident && incident.actions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No containment actions have been persisted for this incident.
            </p>
          ) : null}
          {incident?.actions.map((action) => (
            <article key={action.id} className="grid gap-1 text-sm">
              <p>
                <span className="capitalize">{actionTypeLabel(action.actionType)}</span>
                {" → "}
                {action.target ?? "—"}{" "}
                <Badge variant="outline" className="ml-1 align-middle">
                  {action.approvalStatus}
                </Badge>
              </p>
              <p className="text-muted-foreground">{containmentLabel(action)}</p>
            </article>
          ))}
          <Link href="/response" className="text-sm text-primary hover:underline">
            Open response center
          </Link>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Audit history</CardTitle>
        </CardHeader>
        <CardContent>
          <AuditHistory incidentId={incidentId} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Incident report</CardTitle>
        </CardHeader>
        <CardContent>
          <ReportDownloadButton incidentId={incidentId} />
        </CardContent>
      </Card>
    </div>
  );
}
