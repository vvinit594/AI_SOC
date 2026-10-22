import { PageHeader } from "@/components/layout/page-header";
import { ResponseCenter } from "@/components/response/response-center";
import { MockBanner } from "@/components/shared/mock-banner";
import { listActions } from "@/lib/data";

export const metadata = {
  title: "Response",
};

export default function ResponsePage() {
  const actions = listActions();

  return (
    <div>
      <PageHeader
        title="Response center"
        description="Human-in-the-loop approval for simulated remediation. Nothing is blocked, isolated, or disabled in v1."
      />
      <MockBanner>
        Approve and reject only update local React state. Phase 8 will persist decisions
        and write an audit event. Every action is labelled simulated.
      </MockBanner>
      <ResponseCenter actions={actions} />
    </div>
  );
}
