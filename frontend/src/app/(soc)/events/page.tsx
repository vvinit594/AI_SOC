import { EventsExplorer } from "@/components/events/events-explorer";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";

export const metadata = {
  title: "Events",
};

export default function EventsPage() {
  return (
    <div>
      <PageHeader
        title="Event Explorer"
        description="Browse normalized security events persisted by the backend."
      />
      <MockBanner>
        Events come from PostgreSQL via <code className="font-mono text-xs">GET /api/events</code>.
        Upload uses <code className="font-mono text-xs">POST /api/logs/upload</code>. Run
        Detection is a separate <code className="font-mono text-xs">POST /api/incidents/detect</code>{" "}
        call.
      </MockBanner>
      <EventsExplorer />
    </div>
  );
}
