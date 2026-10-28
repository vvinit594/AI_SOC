"""Generate a self-contained HTML incident report from persisted data.

No parallel report table: the document is rendered on demand from incidents,
events, agent_runs, response_actions, and audit_logs. Untrusted strings are
HTML-escaped. The report never claims live containment when execution_status
is not_executed or simulated is true. v1 has no live execution status.
"""

from __future__ import annotations

import html
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.attck import get_attack_technique
from app.agents.nodes import NODE_NAMES
from app.core.time import utc_now
from app.db.models import AuditLog, Incident, ResponseAction, SecurityEvent
from app.schemas.investigations import AgentRunRead, InvestigationRead
from app.services import incidents as incident_service
from app.services.investigations import _latest_investigation

_RULE_RE = re.compile(r"\bR[123]\b")
_NODE_ORDER = {name: index for index, name in enumerate(NODE_NAMES)}
_NOT_PERFORMED = "Not performed. Simulated recommendation only; no live containment occurred."
AUDIT_REPORT_LIMIT = 500


class ReportError(ValueError):
    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _esc(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _when(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        return _esc(value.isoformat())
    return _esc(value.astimezone(UTC).isoformat())


def report_filename(incident_id: uuid.UUID) -> str:
    return f"incident-{incident_id}-report.html"


def content_disposition(filename: str) -> str:
    return f'attachment; filename="{filename}"'


def build_incident_report(session: Session, incident_id: uuid.UUID) -> tuple[str, str]:
    incident = incident_service.get_incident(session, incident_id)
    if incident is None:
        raise ReportError("Incident not found", status_code=404)
    generated_at = utc_now()
    html_doc = _render(session, incident, generated_at)
    return html_doc, report_filename(incident.id)


def _render(session: Session, incident: Incident, generated_at: datetime) -> str:
    events = _load_events(session, incident)
    investigation = _latest_investigation(session, incident.id)
    actions = sorted(incident.response_actions, key=lambda item: (item.created_at, item.id))
    audits, audits_truncated = _load_audits(session, incident.id)
    title = _esc(incident.title or "Untitled incident")
    generated = _when(generated_at)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'\">\n"
        f"<title>Incident report — {title}</title>\n"
        f"{_STYLES}\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        '<p class="eyebrow">AI-SOC incident report</p>\n'
        f"<h1>{title}</h1>\n"
        f"<p>Generated at {generated}. Self-contained HTML; readable offline. No scripts.</p>\n"
        "</header>\n"
        f"{_section_summary(incident)}\n"
        f"{_section_rules(incident)}\n"
        f"{_section_events(events)}\n"
        f"{_section_investigation(investigation)}\n"
        f"{_section_actions(actions)}\n"
        f"{_section_audits(audits, audits_truncated)}\n"
        "</body>\n"
        "</html>\n"
    )


_STYLES = """<style>
body { font-family: Georgia, serif; margin: 2rem auto; max-width: 56rem; color: #111; }
h1, h2, h3 { font-family: Arial, sans-serif; }
.eyebrow { letter-spacing: 0.08em; text-transform: uppercase; font-size: 0.8rem; }
section { margin: 1.75rem 0; }
table { border-collapse: collapse; width: 100%; font-size: 0.95rem; }
th, td { border: 1px solid #ccc; padding: 0.4rem 0.55rem; text-align: left; vertical-align: top; }
.muted { color: #444; }
.notice { background: #fff8e1; border: 1px solid #e6c200; padding: 0.6rem 0.8rem; }
code { font-family: Consolas, monospace; font-size: 0.9em; }
</style>"""


def _section_summary(incident: Incident) -> str:
    rows = [
        ("Incident ID", f"<code>{_esc(incident.id)}</code>"),
        ("Title", _esc(incident.title) or "—"),
        ("Severity", _esc(incident.severity) or "—"),
        ("Status", _esc(incident.status) or "—"),
        ("Scenario", _esc(incident.scenario) or "—"),
        ("Created at", _when(incident.created_at)),
        ("Summary", _esc(incident.summary) or "—"),
    ]
    return "<section><h2>Incident summary</h2>" + _dl(rows) + "</section>"


def _section_rules(incident: Incident) -> str:
    found = sorted(set(_RULE_RE.findall(incident.summary or "")))
    if not found:
        body = (
            '<p class="muted">No detection rule identifiers were stored on this '
            "incident summary.</p>"
        )
    else:
        items = "".join(f"<li><code>{_esc(rule)}</code></li>" for rule in found)
        body = (
            "<p>Rule identifiers taken from the persisted incident summary "
            "(not re-run at report time):</p><ul>" + items + "</ul>"
        )
    return "<section><h2>Detected security rules</h2>" + body + "</section>"


def _load_events(session: Session, incident: Incident) -> list[SecurityEvent]:
    event_ids = incident_service.incident_event_ids(incident)
    if not event_ids:
        return []
    return list(
        session.scalars(
            select(SecurityEvent)
            .where(SecurityEvent.id.in_(event_ids))
            .order_by(SecurityEvent.timestamp.asc(), SecurityEvent.id.asc())
        ).all()
    )


def _section_events(events: list[SecurityEvent]) -> str:
    if not events:
        body = '<p class="muted">No linked evidence events.</p>'
    else:
        rows = [_event_row(event) for event in events]
        body = (
            "<table><thead><tr>"
            "<th>Time</th><th>Type</th><th>Source IP</th><th>Destination IP</th>"
            "<th>User</th><th>Host</th><th>Message</th><th>ID</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )
    return "<section><h2>Evidence and security events</h2>" + body + "</section>"


def _event_row(event: SecurityEvent) -> str:
    return (
        "<tr>"
        f"<td>{_when(event.timestamp)}</td>"
        f"<td>{_esc(event.event_type)}</td>"
        f"<td>{_esc(event.source_ip) or '—'}</td>"
        f"<td>{_esc(event.destination_ip) or '—'}</td>"
        f"<td>{_esc(event.username) or '—'}</td>"
        f"<td>{_esc(event.hostname) or '—'}</td>"
        f"<td>{_esc(event.raw_message)}</td>"
        f"<td><code>{_esc(event.id)}</code></td>"
        "</tr>"
    )


def _section_investigation(investigation: InvestigationRead | None) -> str:
    if investigation is None:
        body = '<p class="muted">No investigation has been recorded for this incident.</p>'
        return "<section><h2>Investigation findings</h2>" + body + "</section>"
    parts = [
        "<p>Investigation ID: "
        f"<code>{_esc(investigation.id)}</code> — status {_esc(investigation.status)} "
        f"(assessment source: {_esc(investigation.assessment_source)}).</p>"
    ]
    nodes = sorted(
        investigation.nodes,
        key=lambda node: (_NODE_ORDER.get(node.agent_name, 99), node.agent_name),
    )
    for node in nodes:
        parts.append(_node_block(node))
    return "<section><h2>Investigation findings</h2>" + "".join(parts) + "</section>"


def _node_block(node: AgentRunRead) -> str:
    payload = node.structured_output if isinstance(node.structured_output, dict) else {}
    bits = [
        f'<h3>{_esc(node.agent_name)} <span class="muted">({_esc(node.status)})</span></h3>',
    ]
    if node.error:
        bits.append(f"<p>Recorded error type: <code>{_esc(node.error)}</code></p>")
    finding = payload.get("finding")
    if finding:
        bits.append(f"<p>{_esc(finding)}</p>")
    reasoning = payload.get("reasoning_summary")
    if reasoning:
        bits.append(f'<p class="muted">{_esc(reasoning)}</p>')
    confidence = payload.get("confidence")
    if confidence:
        bits.append(f"<p>Confidence: {_esc(confidence)}</p>")
    next_step = payload.get("recommended_next_step")
    if next_step:
        bits.append(f"<p>Recommended next step: {_esc(next_step)}</p>")
    llm_status = payload.get("llm_status")
    if llm_status:
        bits.append(f"<p>LLM status: {_esc(llm_status)}</p>")
    evidence_ids = payload.get("evidence_event_ids") or []
    if isinstance(evidence_ids, list) and evidence_ids:
        items = "".join(f"<li><code>{_esc(item)}</code></li>" for item in evidence_ids)
        bits.append("<p>Evidence event IDs:</p><ul>" + items + "</ul>")
    techniques = payload.get("techniques") or []
    if isinstance(techniques, list) and techniques:
        items = "".join(_technique_item(item) for item in techniques)
        bits.append("<p>ATT&amp;CK techniques:</p><ul>" + items + "</ul>")
    facts = payload.get("facts") or []
    if isinstance(facts, list):
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            statement = fact.get("statement")
            if statement:
                bits.append(f"<p>{_esc(fact.get('kind'))}: {_esc(statement)}</p>")
    records = payload.get("records") or []
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            bits.append(
                "<p>Threat intel "
                f"{_esc(record.get('indicator'))} — status {_esc(record.get('status'))}, "
                f"source {_esc(record.get('source') or record.get('provider'))}. "
                f"{_esc(record.get('summary'))}</p>"
            )
    actions = payload.get("actions") or []
    if isinstance(actions, list):
        for item in actions:
            if not isinstance(item, dict):
                continue
            bits.append(
                "<p>Planner recommendation (not performed): "
                f"{_esc(item.get('action_type'))} target {_esc(item.get('target') or '—')} — "
                f"{_esc(item.get('reason'))}. Simulated recommendation only.</p>"
            )
    return "".join(bits)


def _technique_item(technique_id: object) -> str:
    ident = str(technique_id)
    known = get_attack_technique(ident) if ident.strip() else None
    if known is None:
        return f"<li><code>{_esc(ident)}</code></li>"
    return (
        f"<li><code>{_esc(known['technique_id'])}</code> "
        f"{_esc(known['name'])} ({_esc(known['tactic'])})</li>"
    )


def _execution_label(action: ResponseAction) -> str:
    status = action.execution_status
    if status == "failed":
        return "Recorded execution attempt failed; no successful containment."
    if status in {"not_executed", "simulated"} or action.simulated:
        return _NOT_PERFORMED
    return (
        f"Recorded execution_status is {_esc(status)}. "
        "This report does not treat that value as live containment."
    )


def _section_actions(actions: list[ResponseAction]) -> str:
    notice = (
        '<p class="notice">All v1 response recommendations are simulated. '
        "An approved action is a recorded human decision, not proof of containment. "
        "Nothing in this report means a response action was carried out on a live system."
        "</p>"
    )
    if not actions:
        body = '<p class="muted">No response actions have been persisted.</p>'
        return "<section><h2>Recommended response actions</h2>" + notice + body + "</section>"
    rows = []
    for action in actions:
        rows.append(
            "<tr>"
            f"<td><code>{_esc(action.id)}</code></td>"
            f"<td>{_esc(action.action_type)}</td>"
            f"<td>{_esc(action.target) or '—'}</td>"
            f"<td>{_esc(action.reason)}</td>"
            f"<td>{_esc(action.approval_status)}</td>"
            f"<td>{_esc(action.execution_status)}</td>"
            f"<td>{'yes' if action.simulated else 'no'}</td>"
            f"<td>{_esc(action.actor) or '—'}</td>"
            f"<td>{_when(action.decided_at)}</td>"
            f"<td>{_esc(_execution_label(action))}</td>"
            "</tr>"
        )
    table = (
        "<table><thead><tr>"
        "<th>ID</th><th>Type</th><th>Target</th><th>Reason</th>"
        "<th>Approval</th><th>Execution status</th><th>Simulated</th>"
        "<th>Actor</th><th>Decided at</th><th>Containment</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )
    return "<section><h2>Recommended response actions</h2>" + notice + table + "</section>"


def _load_audits(session: Session, incident_id: uuid.UUID) -> tuple[list[AuditLog], bool]:
    items = list(
        session.scalars(
            select(AuditLog)
            .where(AuditLog.incident_id == incident_id)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
            .limit(AUDIT_REPORT_LIMIT + 1)
        ).all()
    )
    truncated = len(items) > AUDIT_REPORT_LIMIT
    return items[:AUDIT_REPORT_LIMIT], truncated


def _section_audits(audits: list[AuditLog], truncated: bool) -> str:
    heading = "<section><h2>Approval and rejection history</h2>"
    if not audits:
        body = '<p class="muted">No audit events recorded for this incident.</p>'
        return heading + body + "</section>"
    rows = []
    for item in audits:
        details = item.details if isinstance(item.details, dict) else {}
        detail_bits = ", ".join(
            f"{_esc(key)}={_esc(value)}" for key, value in sorted(details.items())
        )
        rows.append(
            "<tr>"
            f"<td>{_when(item.occurred_at)}</td>"
            f"<td>{_esc(item.event_type)}</td>"
            f"<td>{_esc(item.actor)}</td>"
            f"<td>{_esc(item.resource_type)}</td>"
            f"<td><code>{_esc(item.resource_id)}</code></td>"
            f"<td>{detail_bits or '—'}</td>"
            "</tr>"
        )
    note = ""
    if truncated:
        note = (
            f'<p class="muted">Showing the {AUDIT_REPORT_LIMIT} most recent audit events; '
            "older events are omitted.</p>"
        )
    table = (
        "<table><thead><tr>"
        "<th>Occurred at</th><th>Event</th><th>Actor</th>"
        "<th>Resource</th><th>Resource ID</th><th>Details</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )
    return heading + note + table + "</section>"


def _dl(rows: list[tuple[str, str]]) -> str:
    body = "".join(f"<tr><th>{_esc(label)}</th><td>{value}</td></tr>" for label, value in rows)
    return "<table>" + body + "</table>"
