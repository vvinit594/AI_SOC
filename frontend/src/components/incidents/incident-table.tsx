"use client";

import Link from "next/link";

import { StartInvestigationButton } from "@/components/incidents/start-investigation-button";
import { SeverityBadge } from "@/components/incidents/severity-badge";
import { StatusBadge } from "@/components/incidents/status-badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatUtc, shortId } from "@/lib/format";
import type { IncidentStatus, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

export type IncidentTableRow = {
  id: string;
  title: string;
  severity: Severity;
  status: IncidentStatus;
  createdAt: string;
  scenario: string | null;
};

export function IncidentTable({
  incidents,
  caption = "Detected incidents",
}: {
  incidents: IncidentTableRow[];
  caption?: string;
}) {
  return (
    <Table>
      <caption className="sr-only">{caption}</caption>
      <TableHeader>
        <TableRow>
          <TableHead>Incident</TableHead>
          <TableHead>Severity</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {incidents.length === 0 ? (
          <TableRow>
            <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
              No persisted incidents yet. Load a demo scenario or run detection.
            </TableCell>
          </TableRow>
        ) : (
          incidents.map((incident) => (
            <TableRow key={incident.id}>
              <TableCell>
                <Link
                  href={`/incidents/${incident.id}`}
                  className="block max-w-md font-medium text-foreground hover:text-primary hover:underline"
                >
                  {incident.title}
                </Link>
                <p className="font-mono text-xs text-muted-foreground">
                  {shortId(incident.id, 12)}
                  {incident.scenario ? ` · Scenario ${incident.scenario}` : ""}
                </p>
              </TableCell>
              <TableCell>
                <SeverityBadge severity={incident.severity} />
              </TableCell>
              <TableCell>
                <StatusBadge status={incident.status} />
              </TableCell>
              <TableCell className="text-muted-foreground">
                {formatUtc(incident.createdAt)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Link
                    href={`/incidents/${incident.id}`}
                    className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
                  >
                    Details
                  </Link>
                  <StartInvestigationButton incidentId={incident.id} />
                </div>
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
