import { formatUtc } from "@/lib/format";
import type { Incident, Investigation, ResponseAction, SecurityEvent } from "@/lib/types";

export function buildIncidentReportHtml(input: {
  incident: Incident;
  events: SecurityEvent[];
  investigation: Investigation | undefined;
  actions: ResponseAction[];
}): string {
  const { incident, events, investigation, actions } = input;

  const eventRows = events
    .map(
      (event) =>
        `<tr><td>${event.id}</td><td>${formatUtc(event.timestamp)}</td><td>${event.eventType}</td><td>${event.sourceIp ?? "—"}</td><td>${event.username ?? "—"}</td></tr>`,
    )
    .join("");

  const mitre = incident.mitreTechniques.length
    ? incident.mitreTechniques
        .map(
          (technique) =>
            `<li><strong>${technique.techniqueId}</strong> ${technique.name} — ${technique.reason} (events: ${technique.evidenceEventIds.join(", ")})</li>`,
        )
        .join("")
    : "<li>No ATT&CK technique is supported by the current evidence.</li>";

  const intel =
    investigation?.threatIntel
      .map(
        (result) =>
          `<li>${result.indicator} — ${result.status} via ${result.provider} at ${formatUtc(result.lookedUpAt)}. ${result.summary}</li>`,
      )
      .join("") ?? "<li>No threat-intelligence results.</li>";

  const actionRows = actions
    .map(
      (action) =>
        `<tr><td>${action.actionType}</td><td>${action.target}</td><td>${action.status}</td><td>${action.simulated ? "simulated" : "live"}</td></tr>`,
    )
    .join("");

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>AI-SOC report — ${incident.title}</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; color: #0f172a; }
      h1 { font-size: 1.4rem; }
      table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
      th, td { border: 1px solid #cbd5e1; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.85rem; }
      .muted { color: #475569; }
    </style>
  </head>
  <body>
    <p class="muted">AI-SOC incident report · generated from mock data in Phase 2 · ${formatUtc(new Date().toISOString())}</p>
    <h1>${incident.title}</h1>
    <p><strong>Severity:</strong> ${incident.severity} · <strong>Status:</strong> ${incident.status}</p>
    <p>${incident.summary}</p>
    <h2>Evidence</h2>
    <table>
      <thead><tr><th>Event ID</th><th>Timestamp</th><th>Type</th><th>Source IP</th><th>User</th></tr></thead>
      <tbody>${eventRows}</tbody>
    </table>
    <h2>Root-cause hypothesis</h2>
    <p>${incident.rootCause.hypothesis}</p>
    <p class="muted">Uncertainty: ${incident.rootCause.uncertainty}</p>
    <h2>MITRE ATT&CK</h2>
    <ul>${mitre}</ul>
    <h2>Threat intelligence</h2>
    <ul>${intel}</ul>
    <h2>Recommended actions</h2>
    <table>
      <thead><tr><th>Action</th><th>Target</th><th>Decision</th><th>Execution</th></tr></thead>
      <tbody>${actionRows || "<tr><td colspan='4'>No actions proposed.</td></tr>"}</tbody>
    </table>
  </body>
</html>`;
}

export function downloadHtml(filename: string, html: string) {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
