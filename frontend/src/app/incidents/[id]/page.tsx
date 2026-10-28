import Link from "next/link";
import { notFound } from "next/navigation";

import { IncidentLiveResponse } from "@/components/incidents/incident-live-response";
import { SeverityBadge } from "@/components/incidents/severity-badge";
import { StatusBadge } from "@/components/incidents/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { getEventsForIncident, getIncident, listIncidents } from "@/lib/data";
import { formatUtc, shortId } from "@/lib/format";
import { cn } from "@/lib/utils";

export async function generateStaticParams() {
  return listIncidents().map((incident) => ({ id: incident.id }));
}

export async function generateMetadata({ params }: PageProps<"/incidents/[id]">) {
  const { id } = await params;
  const incident = getIncident(id);
  return { title: incident?.title ?? "Incident" };
}

export default async function IncidentDetailPage({
  params,
}: PageProps<"/incidents/[id]">) {
  const { id } = await params;
  const incident = getIncident(id);
  if (!incident) {
    notFound();
  }

  const events = getEventsForIncident(incident);

  return (
    <div>
      <PageHeader
        title={incident.title}
        description={incident.summary}
        actions={
          <Link
            href={`/investigations/${incident.investigationId}`}
            className={cn(buttonVariants())}
          >
            Investigate Incident
          </Link>
        }
      />
      <MockBanner>
        Severity, events, and root-cause on this page still use mock data. Response
        recommendations, audit history, and HTML report download read the backend.
      </MockBanner>
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={incident.severity} />
        <StatusBadge status={incident.status} />
        <span className="text-sm text-muted-foreground">
          Created {formatUtc(incident.createdAt)} · Scenario {incident.scenario}
        </span>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Why this severity</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {incident.severityReasons.map((reason) => (
              <article key={`${reason.ruleId}-${reason.reason}`}>
                <p className="text-sm font-medium">Rule {reason.ruleId}</p>
                <p className="text-sm text-muted-foreground">{reason.reason}</p>
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  {reason.eventIds.map((eventId) => shortId(eventId, 8)).join(", ")}
                </p>
              </article>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Root-cause hypothesis</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <p className="text-sm">{incident.rootCause.hypothesis}</p>
            <p className="text-sm text-muted-foreground">
              Uncertainty: {incident.rootCause.uncertainty}
            </p>
            <p className="text-xs text-muted-foreground">
              Qualitative confidence: {incident.rootCause.confidence} — not a calibrated
              probability.
            </p>
            <Separator />
            <div>
              <p className="mb-2 text-sm font-medium">MITRE ATT&CK</p>
              {incident.mitreTechniques.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No technique is mapped. The evidence does not support a confirmed attack.
                </p>
              ) : (
                <ul className="grid gap-2 text-sm">
                  {incident.mitreTechniques.map((technique) => (
                    <li key={technique.techniqueId}>
                      <span className="font-medium">
                        {technique.techniqueId} {technique.name}
                      </span>
                      <span className="text-muted-foreground"> — {technique.reason}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Related events ({events.length})</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2">
            {events.map((event) => (
              <p key={event.id} className="text-sm">
                <span className="font-mono text-xs text-muted-foreground">
                  {formatUtc(event.timestamp)}
                </span>{" "}
                {event.eventType} · {event.sourceIp ?? "—"} · {event.username ?? "—"}
              </p>
            ))}
          </CardContent>
        </Card>
      </div>
      <div className="mt-6">
        <IncidentLiveResponse incidentId={incident.id} />
      </div>
    </div>
  );
}
