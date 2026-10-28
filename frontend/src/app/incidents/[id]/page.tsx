import { IncidentDetailClient } from "@/components/incidents/incident-detail-client";
import { getIncident, listIncidents } from "@/lib/data";

export async function generateStaticParams() {
  return listIncidents().map((incident) => ({ id: incident.id }));
}

export async function generateMetadata({ params }: PageProps<"/incidents/[id]">) {
  const { id } = await params;
  const incident = getIncident(id);
  return { title: incident?.title ?? "Incident" };
}

export default async function IncidentDetailPage({
  params,
}: PageProps<"/incidents/[id]">) {
  const { id } = await params;
  return <IncidentDetailClient incidentId={id} />;
}
