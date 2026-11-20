"use client";

import { useEffect, useState } from "react";

import { IncidentTable } from "@/components/incidents/incident-table";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listIncidentSummaries } from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import { isAbortError } from "@/lib/analyst-proxy";
import type { PersistedIncident } from "@/lib/types";

export function IncidentsListClient() {
  const [incidents, setIncidents] = useState<PersistedIncident[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listIncidentSummaries(controller.signal)
      .then((rows) => {
        setIncidents(rows);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught)) {
          return;
        }
        setError(analystErrorMessage(caught));
        setIncidents([]);
      });
    return () => controller.abort();
  }, []);

  return (
    <div>
      <PageHeader
        title="Incidents"
        description="Incidents created by detection rules, with the evidence that justified each severity."
      />
      <MockBanner>
        This list is <code className="font-mono text-xs">GET /api/incidents</code> from PostgreSQL.
        Load a demo scenario if the table is empty.
      </MockBanner>
      {error ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <Card>
        <CardContent className="pt-4">
          {incidents === null ? (
            <Skeleton className="h-40" />
          ) : (
            <IncidentTable incidents={incidents} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
