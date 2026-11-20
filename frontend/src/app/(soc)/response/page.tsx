import { PageHeader } from "@/components/layout/page-header";
import { ResponseCenter } from "@/components/response/response-center";
import { MockBanner } from "@/components/shared/mock-banner";

export const metadata = {
  title: "Response",
};

export default function ResponsePage() {
  return (
    <div>
      <PageHeader
        title="Response center"
        description="Human-in-the-loop approval for simulated remediation. Nothing is blocked, isolated, or disabled in v1."
      />
      <MockBanner>
        Approve, reject, audit history, and report download use your signed-in workspace
        session. The browser never receives <code className="font-mono text-xs">ANALYST_API_TOKEN</code>.
        Approval records a decision; it does not execute containment.
      </MockBanner>
      <ResponseCenter />
    </div>
  );
}
