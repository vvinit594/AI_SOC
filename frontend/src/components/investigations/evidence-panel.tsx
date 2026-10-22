import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatUtc, shortId } from "@/lib/format";
import type { Incident, Investigation, SecurityEvent } from "@/lib/types";

export function EvidencePanel({
  incident,
  events,
  investigation,
}: {
  incident: Incident;
  events: SecurityEvent[];
  investigation: Investigation;
}) {
  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Evidence</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          {events.map((event) => (
            <article key={event.id} className="rounded-lg border border-border/70 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-mono text-xs text-muted-foreground">
                  {shortId(event.id, 12)}
                </p>
                <time className="text-xs text-muted-foreground" dateTime={event.timestamp}>
                  {formatUtc(event.timestamp)}
                </time>
              </div>
              <p className="mt-1 text-sm font-medium">{event.eventType}</p>
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {event.sourceIp ?? "—"}
                {event.destinationIp ? ` → ${event.destinationIp}` : ""} ·{" "}
                {event.username ?? "no user"} · {event.hostname ?? "no host"}
              </p>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                {event.rawMessage}
              </p>
            </article>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Threat intelligence</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          {investigation.threatIntel.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No external indicators were looked up for this incident.
            </p>
          ) : (
            investigation.threatIntel.map((result) => (
              <article key={result.indicator} className="rounded-lg border border-border/70 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm">{result.indicator}</span>
                  <Badge variant="outline" className="capitalize">
                    {result.status}
                  </Badge>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{result.summary}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Source {result.source} · {result.provider} · {formatUtc(result.lookedUpAt)}
                </p>
              </article>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>MITRE ATT&CK</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          {incident.mitreTechniques.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No ATT&CK technique is supported by the current evidence.
            </p>
          ) : (
            incident.mitreTechniques.map((technique) => (
              <article key={technique.techniqueId}>
                <p className="font-medium">
                  {technique.techniqueId} · {technique.name}
                </p>
                <p className="text-sm text-muted-foreground">{technique.reason}</p>
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  Evidence: {technique.evidenceEventIds.map((id) => shortId(id, 8)).join(", ")}
                </p>
              </article>
            ))
          )}
          <Separator />
          <p className="text-sm">
            Linked incident:{" "}
            <Link className="text-primary hover:underline" href={`/incidents/${incident.id}`}>
              {incident.title}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
