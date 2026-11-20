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
        This table reads <code className="font-mono text-xs">GET /api/events</code>. Use Load
        built-in scenario to persist demo logs, then detection to create incidents.
      </MockBanner>
      <EventsExplorer />
    </div>
  );
}
