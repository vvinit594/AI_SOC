"use client";

import Link from "next/link";
import { Download } from "lucide-react";

import { SeverityBadge } from "@/components/incidents/severity-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getActionsForIncident,
  getEventsForIncident,
  getIncident,
  getInvestigationForIncident,
} from "@/lib/data";
import { formatUtc } from "@/lib/format";
import { buildIncidentReportHtml, downloadHtml } from "@/lib/report";
import type { IncidentReport } from "@/lib/types";

export function ReportsList({ reports }: { reports: IncidentReport[] }) {
  function handleDownload(report: IncidentReport) {
    const incident = getIncident(report.incidentId);
    if (!incident) {
      return;
    }
    const html = buildIncidentReportHtml({
      incident,
      events: getEventsForIncident(incident),
      investigation: getInvestigationForIncident(incident.id),
      actions: getActionsForIncident(incident.id),
    });
    downloadHtml(`${report.id}.html`, html);
  }

  return (
    <div className="grid gap-4">
      {reports.map((report) => {
        const incident = getIncident(report.incidentId);
        return (
          <Card key={report.id}>
            <CardHeader className="flex flex-row items-start justify-between gap-3">
              <div>
                <CardTitle>{report.title}</CardTitle>
                <CardDescription>
                  {formatUtc(report.generatedAt)} · {report.format.toUpperCase()} preview
                </CardDescription>
              </div>
              {incident ? <SeverityBadge severity={incident.severity} /> : null}
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {incident ? (
                <Link
                  href={`/incidents/${incident.id}`}
                  className="text-sm text-primary hover:underline"
                >
                  Open incident
                </Link>
              ) : null}
              <Button size="sm" variant="outline" onClick={() => handleDownload(report)}>
                <Download data-icon="inline-start" />
                Download HTML
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
