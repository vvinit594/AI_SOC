import { PageHeader } from "@/components/layout/page-header";
import { ReportsList } from "@/components/reports/reports-list";
import { MockBanner } from "@/components/shared/mock-banner";
import { listReports } from "@/lib/data";

export const metadata = {
  title: "Reports",
};

export default function ReportsPage() {
  const reports = listReports();

  return (
    <div>
      <PageHeader
        title="Reports & history"
        description="Downloadable incident reports generated from structured data. Phase 8 will render these from persisted agent runs."
      />
      <MockBanner>
        HTML download is assembled in the browser from mock records so you can review the
        report shape. It is not a signed backend artifact yet.
      </MockBanner>
      <ReportsList reports={reports} />
    </div>
  );
}
