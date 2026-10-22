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
import { getMetrics, getPrimaryInvestigationId, listIncidents } from "@/lib/data";
import { cn } from "@/lib/utils";

export default function OverviewPage() {
  const metrics = getMetrics();
  const incidents = listIncidents();
  const investigationHref = `/investigations/${getPrimaryInvestigationId()}`;

  return (
    <div>
      <PageHeader
        title="SOC Overview"
        description="Incident posture across the three built-in demo scenarios. Counters will read from PostgreSQL once Phase 4–5 land."
        actions={
          <>
            <LoadDemoDialog />
            <Link href={investigationHref} className={cn(buttonVariants())}>
              Investigate Incident
            </Link>
          </>
        }
      />
      <MockBanner>
        Phase 2 visual shell. Metrics, charts, and tables are served from{" "}
        <code className="font-mono text-xs">src/lib/mock-data.ts</code>, not the API.
      </MockBanner>
      <section className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Total incidents"
          value={metrics.totalIncidents}
          hint="All persisted detections in this workspace"
          icon={Siren}
        />
        <MetricCard
          label="Open"
          value={metrics.openIncidents}
          hint="Open, investigating, or awaiting approval"
          icon={Activity}
        />
        <MetricCard
          label="Critical / high"
          value={metrics.criticalAndHigh}
          hint="Severity assigned from detection evidence"
          icon={AlertTriangle}
        />
        <MetricCard
          label="Awaiting approval"
          value={metrics.awaitingApproval}
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
            <IncidentChart incidents={incidents} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recent incidents</CardTitle>
            <CardDescription>Newest detections first. Investigate opens the live workspace shell.</CardDescription>
          </CardHeader>
          <CardContent>
            <IncidentTable incidents={incidents} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
