"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { LiveAgentWorkflow } from "@/components/investigations/live-agent-workflow";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  getIncidentApi,
  getInvestigationApi,
  type InvestigationApiResponse,
} from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import { isAbortError } from "@/lib/analyst-proxy";
import { getIncident, getInvestigation } from "@/lib/data";
import { emptyAgentRun } from "@/lib/investigation-stream";
import type { AgentName, PersistedIncident } from "@/lib/types";
import { cn } from "@/lib/utils";

const AGENT_ORDER: AgentName[] = [
  "investigation",
  "threat_intelligence",
  "analysis",
  "response_planner",
];

export function InvestigationDetailClient({
  investigationId,
}: {
  investigationId: string;
}) {
  const mock = getInvestigation(investigationId);
  const mockIncident = mock ? getIncident(mock.incidentId) : undefined;
  const [payload, setPayload] = useState<InvestigationApiResponse | null>(null);
  const [incident, setIncident] = useState<PersistedIncident | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getInvestigationApi(investigationId, controller.signal)
      .then(async (row) => {
        setPayload(row);
        setNotFound(false);
        const liveIncident = await getIncidentApi(row.incident_id, controller.signal);
        setIncident(liveIncident);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught)) {
          return;
        }
        if (caught instanceof ApiError && caught.status === 404) {
          setNotFound(true);
          return;
        }
        setError(analystErrorMessage(caught));
      });
    return () => controller.abort();
  }, [investigationId]);

  if (notFound && mock === undefined) {
    return (
      <div>
        <PageHeader
          title="Investigation not found"
          description="No persisted investigation exists for this identifier."
        />
        <p className="text-sm text-muted-foreground">
          Start an investigation from a live incident. Mock investigation routes still open
          when a Phase 2 snapshot exists.
        </p>
      </div>
    );
  }

  if (error && payload === null && mock === undefined) {
    return (
      <div>
        <PageHeader title="Investigation" description="Unable to load the live investigation." />
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      </div>
    );
  }

  if (payload === null && mock === undefined) {
    return (
      <div aria-busy="true" aria-label="Loading investigation">
        <Skeleton className="mb-4 h-8 w-80" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
    );
  }

  const title = incident?.title ?? mockIncident?.title ?? "Investigation";
  const incidentId = incident?.id ?? mockIncident?.id;
  const analysisFinding = payload?.nodes.find((node) => node.agent_name === "analysis")
    ?.structured_output;
  const analysisText =
    typeof analysisFinding?.finding === "string" ? analysisFinding.finding : null;
  const analysisReason =
    typeof analysisFinding?.reasoning_summary === "string"
      ? analysisFinding.reasoning_summary
      : null;

  return (
    <div>
      <PageHeader
        title={`Investigation · ${title}`}
        description="Each LangGraph node reports queued, running, completed, or failed over SSE."
        actions={
          <>
            {incidentId ? (
              <Link
                href={`/incidents/${incidentId}`}
                className={cn(buttonVariants({ variant: "outline" }))}
              >
                Incident detail
              </Link>
            ) : null}
            <Link href="/response" className={cn(buttonVariants())}>
              Response center
            </Link>
          </>
        }
      />
      <MockBanner>
        {payload
          ? "Node status and findings come from the backend. Missing LLM or threat-intel fields stay unavailable rather than invented."
          : "This identifier is not in the persisted backend. The Phase 2 snapshot is shown so demo routes still open."}
      </MockBanner>
      {error && payload === null ? (
        <p className="mb-4 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="grid gap-6">
          <LiveAgentWorkflow
            investigationId={investigationId}
            initialAgents={mock?.agents ?? AGENT_ORDER.map((agent) => emptyAgentRun(agent))}
          />
        </div>
        <div className="grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Analysis findings</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2 text-sm">
              {analysisText ? (
                <>
                  <p>{analysisText}</p>
                  {analysisReason ? (
                    <p className="text-muted-foreground">{analysisReason}</p>
                  ) : null}
                </>
              ) : mockIncident ? (
                <>
                  <p>{mockIncident.rootCause.hypothesis}</p>
                  <p className="text-muted-foreground">{mockIncident.rootCause.uncertainty}</p>
                </>
              ) : (
                <p className="text-muted-foreground">
                  No analysis finding is stored yet. Wait for the analysis node to complete.
                </p>
              )}
            </CardContent>
          </Card>
          {incident ? (
            <Card>
              <CardHeader>
                <CardTitle>Persisted incident</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <p>{incident.summary}</p>
                <p className="font-mono text-xs text-muted-foreground">
                  {incident.eventIds.length} evidence event ID(s)
                </p>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
