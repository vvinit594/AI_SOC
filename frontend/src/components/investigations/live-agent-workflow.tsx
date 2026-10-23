"use client";

import { useEffect, useRef, useState } from "react";

import { AgentStatusList } from "@/components/investigations/agent-status";
import { ApiError, getInvestigationApi } from "@/lib/api";
import {
  applyProgressEvent,
  investigationStreamUrl,
  isTerminalStreamEvent,
  mergeApiNodes,
  type InvestigationProgressPayload,
  type StreamConnectionState,
  type StreamEventName,
} from "@/lib/investigation-stream";
import type { AgentRun } from "@/lib/types";

const STREAM_EVENTS: StreamEventName[] = [
  "connected",
  "node_started",
  "node_completed",
  "node_failed",
  "investigation_completed",
  "investigation_failed",
];

export function LiveAgentWorkflow({
  investigationId,
  initialAgents,
}: {
  investigationId: string;
  initialAgents: AgentRun[];
}) {
  const [agents, setAgents] = useState(initialAgents);
  const [streamState, setStreamState] = useState<StreamConnectionState>("connecting");
  const [detail, setDetail] = useState("Connecting to live progress…");
  const terminal = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    let source: EventSource | null = null;
    let errors = 0;
    terminal.current = false;

    const refreshFindings = () =>
      getInvestigationApi(investigationId, controller.signal)
        .then((payload) => {
          setAgents((current) => mergeApiNodes(current, payload.nodes));
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
        });

    const attach = () => {
      source = new EventSource(investigationStreamUrl(investigationId));
      for (const name of STREAM_EVENTS) {
        source.addEventListener(name, (message: Event) => {
          const evt = message as MessageEvent<string>;
          errors = 0;
          let parsed: Omit<InvestigationProgressPayload, "event">;
          try {
            parsed = JSON.parse(evt.data) as Omit<InvestigationProgressPayload, "event">;
          } catch {
            return;
          }
          const payload: InvestigationProgressPayload = { ...parsed, event: name };
          if (name === "connected") {
            setStreamState("live");
            setDetail("Live progress connected");
            return;
          }
          setAgents((current) => applyProgressEvent(current, payload));
          if (name === "node_completed" || name === "node_failed") {
            void refreshFindings();
          }
          if (isTerminalStreamEvent(name)) {
            terminal.current = true;
            setStreamState(name === "investigation_completed" ? "completed" : "failed");
            setDetail(
              name === "investigation_completed"
                ? "Investigation finished"
                : "Investigation failed",
            );
            source?.close();
            void refreshFindings();
          }
        });
      }
      source.onerror = () => {
        if (terminal.current) {
          source?.close();
          return;
        }
        errors += 1;
        if (errors >= 5) {
          source?.close();
          setStreamState("error");
          setDetail("Live progress disconnected. Refresh to reconnect.");
        }
      };
    };

    getInvestigationApi(investigationId, controller.signal)
      .then((payload) => {
        if (controller.signal.aborted) {
          return;
        }
        setAgents((current) => mergeApiNodes(current, payload.nodes));
        attach();
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        if (error instanceof ApiError && error.status === 404) {
          setStreamState("unavailable");
          setDetail("Live stream unavailable — showing the saved snapshot");
          return;
        }
        setStreamState("error");
        setDetail("Unable to open live progress");
      });

    return () => {
      controller.abort();
      source?.close();
    };
  }, [investigationId]);

  return (
    <div className="grid gap-2">
      <p className="text-xs text-muted-foreground" aria-live="polite">
        {detail}
        <span className="sr-only"> Stream state: {streamState}</span>
      </p>
      <AgentStatusList agents={agents} />
    </div>
  );
}