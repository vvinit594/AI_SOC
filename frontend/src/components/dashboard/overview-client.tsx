"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, AlertTriangle, ShieldCheck, Siren } from "lucide-react";

import { IncidentChart } from "@/components/dashboard/incident-chart";
import { LoadDemoDialog } from "@/components/dashboard/load-demo-dialog";
import { MetricCard } from "@/components/dashboard/metric-card";
import { IncidentTable } from "@/components/incidents/incident-table";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listIncidentSummaries } from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import { isAbortError } from "@/lib/analyst-proxy";
import { metricsFromIncidents } from "@/lib/data";
import type { PersistedIncident } from "@/lib/types";
import { cn } from "@/lib/utils";

export function OverviewClient() {
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

  const metrics = metricsFromIncidents(incidents ?? []);

  return (
    <div>
      <PageHeader
        title="SOC Overview"
        description="Live incident posture from FastAPI and PostgreSQL."
        actions={
          <>
            <LoadDemoDialog />
            <Link href="/incidents" className={cn(buttonVariants())}>
              View incidents
            </Link>
          </>
        }
      />
      <MockBanner>
        Overview counters, charts, and the incident table read{" "}
        <code className="font-mono text-xs">GET /api/incidents</code>. Mock snapshots are not
        used on this page.
      </MockBanner>
      {error ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Total incidents"
          value={incidents === null ? "—" : metrics.totalIncidents}
          hint="All persisted detections in this workspace"
          icon={Siren}
        />
        <MetricCard
          label="Open"
          value={incidents === null ? "—" : metrics.openIncidents}
          hint="Open, investigating, or awaiting approval"
          icon={Activity}
        />
        <MetricCard
          label="Critical / high"
          value={incidents === null ? "—" : metrics.criticalAndHigh}
          hint="Severity assigned from detection evidence"
          icon={AlertTriangle}
        />
        <MetricCard
          label="Awaiting approval"
          value={incidents === null ? "—" : metrics.awaitingApproval}
          hint="Simulated response actions need a decision"
          icon={ShieldCheck}
        />
      </section>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Severity distribution</CardTitle>
            <CardDescription>Counts by evidence-based severity, not LLM confidence.</CardDescription>
          </CardHeader>
          <CardContent>
            {incidents === null ? (
              <Skeleton className="h-[240px]" />
            ) : (
              <IncidentChart incidents={incidents} />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent incidents</CardTitle>
            <CardDescription>Newest detections first. Investigate starts a live agent run.</CardDescription>
          </CardHeader>
          <CardContent>
            {incidents === null ? (
              <Skeleton className="h-40" />
            ) : (
              <IncidentTable incidents={incidents} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
