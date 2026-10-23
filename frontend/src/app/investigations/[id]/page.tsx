import Link from "next/link";
import { notFound } from "next/navigation";

import { EvidencePanel } from "@/components/investigations/evidence-panel";
import { LiveAgentWorkflow } from "@/components/investigations/live-agent-workflow";
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
        description="Each LangGraph node reports queued, running, completed, or failed over SSE. Connecting after a run has started replays persisted progress."
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
        Findings and evidence on this page still use the Phase 2 snapshot when the
        backend has no investigation with this ID. Live node status uses SSE when
        the API is reachable.
      </MockBanner>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="grid gap-6">
          <LiveAgentWorkflow
            investigationId={investigation.id}
            initialAgents={investigation.agents}
          />
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
