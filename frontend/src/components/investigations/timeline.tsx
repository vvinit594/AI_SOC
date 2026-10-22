import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatUtc, shortId } from "@/lib/format";
import type { TimelineEntry } from "@/lib/types";

export function InvestigationTimeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Attack timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="relative space-y-4 border-l border-border pl-4">
          {entries.map((entry) => (
            <li key={`${entry.timestamp}-${entry.title}`} className="relative">
              <span
                aria-hidden="true"
                className="absolute top-1.5 -left-[21px] size-2.5 rounded-full bg-primary ring-4 ring-background"
              />
              <time className="text-xs text-muted-foreground" dateTime={entry.timestamp}>
                {formatUtc(entry.timestamp)}
              </time>
              <p className="font-medium">{entry.title}</p>
              <p className="text-sm text-muted-foreground">{entry.detail}</p>
              {entry.eventId ? (
                <p className="font-mono text-xs text-muted-foreground">
                  Event {shortId(entry.eventId, 12)}
                </p>
              ) : null}
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
