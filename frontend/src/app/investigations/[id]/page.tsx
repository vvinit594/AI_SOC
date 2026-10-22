import Link from "next/link";
import { notFound } from "next/navigation";

import { AgentStatusList } from "@/components/investigations/agent-status";
import { EvidencePanel } from "@/components/investigations/evidence-panel";
import { InvestigationTimeline } from "@/components/investigations/timeline";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getEventsForIncident,
  getIncident,
  getInvestigation,
  listIncidents,
} from "@/lib/data";
import { AGENT_LABELS } from "@/lib/format";
import { cn } from "@/lib/utils";

export async function generateStaticParams() {
  return listIncidents().map((incident) => ({ id: incident.investigationId }));
}

export async function generateMetadata({
  params,
}: PageProps<"/investigations/[id]">) {
  const { id } = await params;
  const investigation = getInvestigation(id);
  return { title: investigation ? "Investigation" : "Investigation not found" };
}

export default async function InvestigationPage({
  params,
}: PageProps<"/investigations/[id]">) {
  const { id } = await params;
  const investigation = getInvestigation(id);
  if (!investigation) {
    notFound();
  }

  const incident = getIncident(investigation.incidentId);
  if (!incident) {
    notFound();
  }

  const events = getEventsForIncident(incident);
  const analysis = investigation.agents.find((agent) => agent.agent === "analysis");

  return (
    <div>
      <PageHeader
        title={`Investigation · ${incident.title}`}
        description="LangGraph nodes will stream real status over SSE in Phase 7. This view shows the four frozen agent roles and their structured outputs."
        actions={
          <>
            <Link
              href={`/incidents/${incident.id}`}
              className={cn(buttonVariants({ variant: "outline" }))}
            >
              Incident detail
            </Link>
            <Link href="/response" className={cn(buttonVariants())}>
              Response center
            </Link>
          </>
        }
      />
      <MockBanner>
        Agent states below are mock snapshots (queued, running, completed, failed,
        waiting for approval). They are not animated independently of a backend workflow.
      </MockBanner>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="grid gap-6">
          <AgentStatusList agents={investigation.agents} />
          <InvestigationTimeline entries={investigation.timeline} />
        </div>
        <div className="grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle>
                {analysis ? AGENT_LABELS.analysis : "Analysis"} findings
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2 text-sm">
              <p>{incident.rootCause.hypothesis}</p>
              <p className="text-muted-foreground">{incident.rootCause.uncertainty}</p>
            </CardContent>
          </Card>
          <EvidencePanel
            incident={incident}
            events={events}
            investigation={investigation}
          />
        </div>
      </div>
    </div>
  );
}
