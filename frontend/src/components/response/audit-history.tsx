"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { listIncidentAuditLogs } from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import { formatDetailValue, formatUtc, shortId } from "@/lib/format";
import type { AuditLogEntry } from "@/lib/types";

function detailText(details: Record<string, unknown>): string {
  const keys = Object.keys(details).sort();
  if (keys.length === 0) {
    return "—";
  }
  return keys.map((key) => `${key}=${formatDetailValue(details[key])}`).join(", ");
}

export function AuditHistory({
  incidentId,
  refreshKey = 0,
}: {
  incidentId: string;
  refreshKey?: number;
}) {
  const [items, setItems] = useState<AuditLogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listIncidentAuditLogs(incidentId, controller.signal)
      .then((rows) => {
        setItems(rows);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        setItems([]);
        setError(analystErrorMessage(caught));
      });
    return () => controller.abort();
  }, [incidentId, refreshKey]);

  if (items === null && !error) {
    return (
      <div className="grid gap-2" aria-busy="true" aria-label="Loading audit history">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-16" />
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-sm text-destructive" role="alert">
        {error}
      </p>
    );
  }

  if (!items || items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No audit events recorded for this incident.
      </p>
    );
  }

  return (
    <ul className="grid gap-2">
      {items.map((item) => (
        <li key={item.id} className="rounded-md border border-border/70 px-3 py-2 text-sm">
          <p className="font-medium">
            {item.eventType.replaceAll("_", " ")} · {item.actor}
          </p>
          <p className="text-xs text-muted-foreground">
            {formatUtc(item.occurredAt)} · {item.resourceType} {shortId(item.resourceId, 8)}
          </p>
          <p className="mt-1 font-mono text-xs text-muted-foreground">{detailText(item.details)}</p>
        </li>
      ))}
    </ul>
  );
}
