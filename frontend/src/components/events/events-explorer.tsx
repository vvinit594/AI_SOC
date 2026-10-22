"use client";

import { useMemo, useState } from "react";
import { Search, Upload } from "lucide-react";

import { LoadDemoDialog } from "@/components/dashboard/load-demo-dialog";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatUtc, shortId } from "@/lib/format";
import type { DemoScenario, SecurityEvent } from "@/lib/types";

const EVENT_TYPES = [
  "all",
  "login_failure",
  "login_success",
  "outbound_connection",
  "admin_task",
] as const;

export function EventsExplorer({ events }: { events: SecurityEvent[] }) {
  const [query, setQuery] = useState("");
  const [eventType, setEventType] = useState<string>("all");
  const [scenario, setScenario] = useState<string>("all");

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return events.filter((event) => {
      if (eventType !== "all" && event.eventType !== eventType) {
        return false;
      }
      if (scenario !== "all" && event.scenario !== scenario) {
        return false;
      }
      if (!needle) {
        return true;
      }
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
  }, [events, eventType, query, scenario]);

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="size-4" aria-hidden="true" />
            Log ingest
          </CardTitle>
          <CardDescription>
            JSON/CSV upload and parsing land in Phase 5. Use a built-in scenario
            for now — files are not sent anywhere in this phase.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <div className="flex min-h-24 flex-1 items-center justify-center rounded-lg border border-dashed border-border px-4 text-center text-sm text-muted-foreground">
            Upload dropzone reserved for Phase 5
          </div>
          <LoadDemoDialog triggerLabel="Load built-in scenario" />
        </CardContent>
      </Card>

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
        <Select value={eventType} onValueChange={(value) => setEventType(value ?? "all")}>
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
        <Select value={scenario} onValueChange={(value) => setScenario(value ?? "all")}>
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

      <p className="text-sm text-muted-foreground">
        Showing {filtered.length} of {events.length} events
      </p>

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
              <TableCell> {event.scenario}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
