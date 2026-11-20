import { InvestigationDetailClient } from "@/components/investigations/investigation-detail-client";
import { listIncidents } from "@/lib/data";

export async function generateStaticParams() {
  return listIncidents().map((incident) => ({ id: incident.investigationId }));
}

export async function generateMetadata({
  params,
}: PageProps<"/investigations/[id]">) {
  const { id } = await params;
  return { title: `Investigation ${id.slice(0, 8)}` };
}

export default async function InvestigationPage({
  params,
}: PageProps<"/investigations/[id]">) {
  const { id } = await params;
  return <InvestigationDetailClient investigationId={id} />;
}
