"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { IncidentLiveResponse } from "@/components/incidents/incident-live-response";
import { SeverityBadge } from "@/components/incidents/severity-badge";
import { StatusBadge } from "@/components/incidents/status-badge";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getIncidentApi } from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import { isAbortError } from "@/lib/analyst-proxy";
import { getEventsForIncident, getIncident } from "@/lib/data";
import { formatUtc, shortId } from "@/lib/format";
import type { Incident, PersistedIncident } from "@/lib/types";
import { cn } from "@/lib/utils";

export function IncidentDetailClient({ incidentId }: { incidentId: string }) {
  const mock = getIncident(incidentId);
  const [incident, setIncident] = useState<PersistedIncident | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getIncidentApi(incidentId, controller.signal)
      .then((row) => {
        setIncident(row);
        setError(null);
        setNotFound(false);
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught)) {
          return;
        }
        if (caught instanceof ApiError && caught.status === 404) {
          setNotFound(true);
          setIncident(null);
          return;
        }
        setError(analystErrorMessage(caught));
      });
    return () => controller.abort();
  }, [incidentId]);

  if (notFound && mock === undefined) {
    return (
      <div>
        <PageHeader
          title="Incident not found"
          description="No persisted incident exists for this identifier."
        />
        <p className="text-sm text-muted-foreground">
          Open the incident from the Response Center after it has been stored by detection.
        </p>
      </div>
    );
  }

  if (error && incident === null && mock === undefined) {
    return (
      <div>
        <PageHeader title="Incident" description="Unable to load persisted incident details." />
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      </div>
    );
  }

  if (incident === null && mock === undefined) {
    return (
      <div aria-busy="true" aria-label="Loading incident">
        <Skeleton className="mb-4 h-8 w-80" />
        <Skeleton className="h-4 w-96 max-w-full" />
        <Skeleton className="mt-6 h-48" />
      </div>
    );
  }

  const title = incident?.title ?? mock?.title ?? "Incident";
  const summary = incident?.summary ?? mock?.summary ?? "";
  const severity = incident?.severity ?? mock?.severity ?? "low";
  const status = incident?.status ?? mock?.status ?? "open";
  const createdAt = incident?.createdAt ?? mock?.createdAt;
  const scenario = incident?.scenario ?? mock?.scenario;
  const eventIds = incident?.eventIds ?? mock?.eventIds ?? [];
  const liveId = incident?.id ?? incidentId;

  return (
    <div>
      <PageHeader
        title={title}
        description={summary}
        actions={
          mock ? (
            <Link
              href={`/investigations/${mock.investigationId}`}
              className={cn(buttonVariants())}
            >
              Investigate Incident
            </Link>
          ) : (
            <Link href="/response" className={cn(buttonVariants({ variant: "outline" }))}>
              Response center
            </Link>
          )
        }
      />
      <MockBanner>
        {incident
          ? "Title, severity, status, summary, and evidence IDs come from the backend. Root-cause, ATT&CK, and event timelines below are shown only when a Phase 2 mock snapshot exists for this ID; they are not invented from incomplete API fields."
          : "This identifier is not in the persisted backend. The narrative below is the Phase 2 mock snapshot so demo routes still open. Open a live incident from the Response Center for stored response actions and reports."}
      </MockBanner>
      {error && incident === null ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={severity} />
        <StatusBadge status={status} />
        {createdAt ? (
          <span className="text-sm text-muted-foreground">
            Created {formatUtc(createdAt)}
            {scenario ? ` · Scenario ${scenario}` : ""}
          </span>
        ) : null}
      </div>
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Evidence event IDs ({eventIds.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {eventIds.length === 0 ? (
            <p className="text-sm text-muted-foreground">No linked evidence events.</p>
          ) : (
            <p className="font-mono text-xs text-muted-foreground">
              {eventIds.map((id) => shortId(id, 8)).join(", ")}
            </p>
          )}
        </CardContent>
      </Card>
      {mock ? <MockNarrative incident={mock} /> : null}
      {incident ? (
        <div className="mt-6">
          <IncidentLiveResponse incidentId={liveId} />
        </div>
      ) : null}
    </div>
  );
}

function MockNarrative({ incident }: { incident: Incident }) {
  const events = getEventsForIncident(incident);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Why this severity (mock snapshot)</CardTitle>
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
          <CardTitle>Root-cause hypothesis (mock snapshot)</CardTitle>
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
                No technique is mapped in the mock snapshot.
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
          <CardTitle>Related events from mock snapshot ({events.length})</CardTitle>
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
  );
}
