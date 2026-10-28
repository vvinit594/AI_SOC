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
        Approve and reject call the persisted backend APIs. Development works when{" "}
        <code className="font-mono text-xs">ANALYST_API_TOKEN</code> is empty on the backend.
        The browser never receives that secret. Approval records a decision; it does not
        execute containment.
      </MockBanner>
      <ResponseCenter />
    </div>
  );
}
