import { IncidentTable } from "@/components/incidents/incident-table";
import { PageHeader } from "@/components/layout/page-header";
import { MockBanner } from "@/components/shared/mock-banner";
import { Card, CardContent } from "@/components/ui/card";
import { listIncidents } from "@/lib/data";

export const metadata = {
  title: "Incidents",
};

export default function IncidentsPage() {
  const incidents = listIncidents();

  return (
    <div>
      <PageHeader
        title="Incidents"
        description="Incidents created by detection rules, with the evidence that justified each severity."
      />
      <MockBanner>
        Detection correlation is mocked. Phase 5 will create these rows from R1, R2, and R3
        against PostgreSQL.
      </MockBanner>
      <Card>
        <CardContent className="pt-4">
          <IncidentTable incidents={incidents} />
        </CardContent>
      </Card>
    </div>
  );
}
