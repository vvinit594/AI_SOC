import { EventsExplorer } from "@/components/events/events-explorer";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";
import { listEvents } from "@/lib/data";

export const metadata = {
  title: "Events",
};

export default function EventsPage() {
  const events = listEvents();

  return (
    <div>
      <PageHeader
        title="Event Explorer"
        description="Browse normalized security events. Search by IP, username, hostname, or event type."
      />
      <MockBanner>
        These events are the synthetic dataset for scenarios A, B, and C. Upload, parse, and
        persist land in Phase 5.
      </MockBanner>
      <EventsExplorer events={events} />
    </div>
  );
}
