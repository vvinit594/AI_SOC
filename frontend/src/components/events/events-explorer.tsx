"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";

import { LogUploadPanel } from "@/components/events/log-upload-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listEventsPage } from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import { isAbortError } from "@/lib/analyst-proxy";
import { formatUtc, shortId } from "@/lib/format";
import { EVENTS_PAGE_SIZE } from "@/lib/ingest";
import type { DemoScenario, SecurityEvent } from "@/lib/types";

const EVENT_TYPES = [
  "all",
  "login_failure",
  "login_success",
  "outbound_connection",
  "admin_task",
] as const;

export function EventsExplorer() {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [eventType, setEventType] = useState<string>("all");
  const [scenario, setScenario] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    listEventsPage({
      eventType,
      scenario,
      limit: EVENTS_PAGE_SIZE,
      offset: page * EVENTS_PAGE_SIZE,
      signal: controller.signal,
    })
      .then((result) => {
        setEvents(result.items);
        setTotal(result.total);
        setLoadError(null);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught) || controller.signal.aborted) {
          return;
        }
        setLoadError(analystErrorMessage(caught));
        setLoading(false);
      });
    return () => controller.abort();
  }, [eventType, page, reloadToken, scenario]);

  const pageCount = Math.max(1, Math.ceil(total / EVENTS_PAGE_SIZE));

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return events;
    }
    return events.filter((event) => {
      const haystack = [
        event.id,
        event.eventType,
        event.sourceIp,
        event.destinationIp,
        event.username,
        event.hostname,
        event.rawMessage,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [events, query]);

  function changeEventType(value: string | null) {
    setLoading(true);
    setEventType(value ?? "all");
    setPage(0);
  }

  function changeScenario(value: string | null) {
    setLoading(true);
    setScenario(value ?? "all");
    setPage(0);
  }

  return (
    <div className="grid gap-6">
      <LogUploadPanel
        onIngested={() => {
          setLoading(true);
          setPage(0);
          setReloadToken((token) => token + 1);
        }}
      />

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative min-w-0 flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search IP, user, host, or event type"
            aria-label="Search events"
            className="pl-8"
          />
        </div>
        <Select value={eventType} onValueChange={changeEventType}>
          <SelectTrigger className="w-full lg:w-52" aria-label="Filter by event type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {EVENT_TYPES.map((type) => (
              <SelectItem key={type} value={type}>
                {type === "all" ? "All event types" : type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={scenario} onValueChange={changeScenario}>
          <SelectTrigger className="w-full lg:w-44" aria-label="Filter by scenario">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All scenarios</SelectItem>
            {(["A", "B", "C"] as DemoScenario[]).map((id) => (
              <SelectItem key={id} value={id}>
                Scenario {id}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {loadError ? (
        <div className="flex flex-wrap items-center gap-2" role="alert">
          <p className="text-sm text-destructive">{loadError}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              setReloadToken((token) => token + 1);
            }}
          >
            Retry
          </Button>
        </div>
      ) : null}

      <p className="text-sm text-muted-foreground">
        {loading
          ? "Loading events…"
          : query.trim()
            ? `Showing ${filtered.length} of ${events.length} on this page (${total} total)`
            : `Showing ${events.length} of ${total} events`}
      </p>

      {loading ? (
        <div className="grid gap-2" aria-busy="true" aria-label="Loading events">
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
          <Skeleton className="h-10" />
        </div>
      ) : filtered.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          {total === 0
            ? "No events are stored yet. Upload JSON or CSV, or load a built-in scenario."
            : "No events match the current search on this page."}
        </p>
      ) : (
        <Table>
          <caption className="sr-only">Parsed security events</caption>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Source / destination</TableHead>
              <TableHead>User / host</TableHead>
              <TableHead>Scenario</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((event) => (
              <TableRow key={event.id}>
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {formatUtc(event.timestamp)}
                  <p className="font-mono text-xs">{shortId(event.id, 12)}</p>
                </TableCell>
                <TableCell>
                  <Badge variant="secondary">{event.eventType}</Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {event.sourceIp ?? "—"}
                  {event.destinationIp ? ` → ${event.destinationIp}` : ""}
                </TableCell>
                <TableCell className="text-sm">
                  {event.username ?? "—"}
                  <p className="text-xs text-muted-foreground">{event.hostname ?? "—"}</p>
                </TableCell>
                <TableCell>{event.scenario || "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Page {page + 1} of {pageCount}
        </p>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page === 0 || loading}
            onClick={() => {
              setLoading(true);
              setPage((current) => Math.max(0, current - 1));
            }}
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading || (page + 1) * EVENTS_PAGE_SIZE >= total}
            onClick={() => {
              setLoading(true);
              setPage((current) => current + 1);
            }}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
