# AI-SOC — MVP Specification (v1)

**Status:** Phase 8B (persistent audit-log history) complete. Phase 8C downloadable reports and 8D frontend integration are not started. Scope remains frozen.
**Product:** AI-SOC — Autonomous Threat Investigation & Response Platform  
**One-line definition:** A deployable Agentic AI platform that ingests security events, detects suspicious activity with transparent rules, coordinates specialized LangGraph agents to investigate, enriches indicators with real threat intelligence, explains the probable attack with evidence, and recommends a safe, human-approved response through a live SOC dashboard.

---

## 1. Core demo loop (the thing that must work end to end)

1. Analyst loads a built-in scenario **or** uploads a JSON/CSV log file.
2. Detection engine parses events and raises incidents with structured evidence.
3. Analyst clicks **Investigate Incident**.
4. Live workflow view shows each agent's real state (queued → running → completed / failed).
5. Incident detail shows evidence, severity + reasons, timeline, threat-intel results, MITRE ATT&CK mapping, root-cause hypothesis and uncertainty.
6. Analyst approves or rejects the recommended (simulated) response; decision is audited.
7. Analyst downloads the incident report.
8. Page refresh / new browser session — everything persists.

---

## 2. In scope for v1 (must-have)

| # | Feature | Done when |
|---|---------|-----------|
| 1 | Log ingestion (JSON/CSV upload + built-in scenarios) | Valid files are parsed and persisted; malformed records return a clear error summary, no corrupt data |
| 2 | Deterministic detection engine (3 rules, configurable thresholds) | Each match returns `rule_id, severity, event_ids, reason, matched_threshold, timestamp` |
| 3 | Incident correlation & timeline | Related events grouped by time / source IP / user / host; re-uploading the same file does not duplicate incidents |
| 4 | Multi-agent LangGraph investigation (4 nodes) | Workflow runs for real, every node's structured output is persisted in `agent_runs` |
| 5 | Threat-intelligence lookup (real API, bounded tool) | Result stored with source, timestamp, status; API failure → `unavailable`, never fabricated |
| 6 | Transparent severity + MITRE ATT&CK mapping | Every severity and technique has a listed reason tied to event IDs |
| 7 | Root-cause analysis | Evidence-backed explanation that states what is uncertain |
| 8 | Response recommendations + approval/rejection | Actions are **simulated only**, labelled as such; decisions recorded with actor + timestamp + audit event. **Done for persistence/API; frontend wiring is Phase 8D.** |
| 9 | Incident report (downloadable HTML or PDF) | Generated from persisted structured data; includes all sections in §6 |
| 10 | SOC dashboard | All counters/charts read from PostgreSQL, never hardcoded |
| 11 | Deployment with persistent storage | Public URL completes the full demo loop without the developer's machine running |

**Phase 2 / explicitly deferred:** AI SOC Assistant (Q&A over incidents), live log streaming (Wazuh), additional SIEM/EDR integrations.

## 3. Out of scope for v1 (will not build)

Unrestricted automatic blocking or account disabling · live enterprise endpoint monitoring · custom-trained LLM · Kubernetes / per-agent microservices · Elasticsearch, Redis, FAISS/RAG · real malware execution or penetration testing · multi-tenant production deployment · accuracy claims without evaluation.

---

## 4. Frozen technical decisions

| Area | Decision |
|------|----------|
| Frontend | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Recharts** (supersedes the Vite mention in the overview document) |
| Backend | Python 3.11+ · FastAPI · Pydantic · REST + **SSE** for live progress |
| Agents | **LangGraph** stateful graph with 4 nodes: `investigation` → `threat_intelligence` → `analysis` → `response_planner`. Three agent *roles* (Investigation, Threat Intelligence, Analysis & Response). Structured LLM outputs via Pydantic. |
| Agent tools (bounded) | `search_incident_events(incident_id)` · `lookup_ip_reputation(ip)` · `get_attack_technique(technique_id)` — validated inputs, no shell, no raw SQL, no arbitrary HTTP |
| Database | PostgreSQL · SQLAlchemy · Alembic. v1 tables: `security_events`, `incidents`, `incident_events`, `agent_runs`, `response_actions` (+ `audit_logs` once approvals exist). UUID PKs, UTC timestamps |
| Detection | Python rules first; scikit-learn Isolation Forest **optional**, only if time permits |
| Threat intel | **AbuseIPDB** (primary, IP reputation) or VirusTotal — provider-agnostic interface, selected by env var; results cached per indicator |
| MITRE ATT&CK | Local curated subset of technique data (no live dependency during demo) |
| LLM | `LLM_PROVIDER=none` (default, deterministic evidence-backed analysis) or `openai` via `LLM_API_KEY` / `LLM_MODEL`. Invalid model output falls back; results are never invented. |
| Architecture | Frontend and backend are **separate apps**; all secrets live on the backend |
| Deployment | Docker Compose locally · Vercel (Next.js) · Python-capable host (FastAPI) · managed PostgreSQL |
| Repo | Monorepo `ai-soc/` with `frontend/`, `backend/`, `docs/`; `.env` files never committed |

### Normalized event schema (minimum)
`id (uuid)` · `timestamp (UTC)` · `event_type` · `source_ip?` · `destination_ip?` · `username?` · `hostname?` · `action?` · `source` (e.g. `linux_auth`, `firewall`) · `raw_message`

### Severity scale (transparent, evidence-based)
`low` · `medium` · `high` · `critical` — each assignment lists the rule(s) and event IDs that justify it. LLM confidence is stored as a **qualitative** label, never presented as a calibrated probability.

### Frozen API surface
`GET /health` · `POST /api/logs/upload` · `POST /api/scenarios/{name}/load` · `GET /api/events` · `POST /api/incidents/detect` · `GET /api/incidents` · `GET /api/incidents/{id}` · `POST /api/incidents/{id}/investigate` · `GET /api/investigations/{id}` · `GET /api/investigations/{id}/stream` (SSE) · `POST /api/actions/{id}/approve` · `POST /api/actions/{id}/reject` · `GET /api/incidents/{id}/report`

Phase 8A implements approve/reject. `GET /api/incidents/{id}` returns persisted `response_actions`. Decisions are simulated (`simulated=true`, `execution_status=not_executed`); no containment is invoked. Repeating the same decision is idempotent; the opposite decision is HTTP 409. Incident status stays `awaiting_approval` when individual actions are decided so one decision cannot imply that every recommendation was decided.

Phase 8B persists append-only `audit_logs` rows in the same transaction as a successful approve/reject. Idempotent repeats and 409/404 responses do not write a new success audit event. `GET /api/incidents/{id}/audit-logs` returns that history (newest first, bounded pagination) under the same `ANALYST_API_TOKEN` policy as approve/reject. Application services never update or delete audit rows. Direct database access can still alter records; this is not tamper-proof WORM storage. Retention is a future operational decision. `GET /api/incidents/{id}/report` is not implemented yet.

### Frontend pages
`/` SOC Overview · `/events` Event Explorer · `/incidents` + `/incidents/[id]` Incident Detail · `/investigations/[id]` Investigation Workspace · `/response` Response Center · `/reports` Reports & History

---

## 5. Demo scenarios (synthetic data, RFC 5737 documentation IPs only: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`)

| Scenario | Sample events | Rules expected to fire | Expected outcome |
|----------|---------------|------------------------|------------------|
| **A — Brute-force login** (primary demo) | One source IP, ~15–30 `login_failure` events against one account inside a short window, then one `login_success` | R1 repeated auth failures · R2 failure→success | `high`/`critical` incident; timeline failures → success; ATT&CK **T1110 Brute Force** (+ T1078 Valid Accounts if success is supported by evidence); recommended actions: force password reset, review session, flag IP for review (all simulated) |
| **B — Suspicious outbound connection** | One internal host repeatedly connecting to one unusual external IP, possibly matching a seeded test indicator | R3 unusual outbound activity | `medium`/`high` incident; real reputation lookup on the IP; if lookup fails → shown as **unknown/unavailable**, not malicious; ATT&CK **T1071 Application Layer Protocol** / **T1041 Exfiltration over C2** only where evidence supports; proposed investigation/containment plan |
| **C — Benign activity / false positive** | Normal business-hours logins by several users, a scheduled admin task, a few isolated failures below threshold | None (or at most `low`) | No confirmed attack claimed; analysis explains why evidence is insufficient; proportionate `low`/`informational` severity |

Dataset size target: **100–500 synthetic events** across the three scenarios, kept stable for presentation day.

### Detection rules (v1)
- **R1 — Repeated authentication failures:** ≥ N failures from one `source_ip` (or against one `username`) within W minutes. Defaults N=5, W=5.
- **R2 — Failure followed by success:** a `login_success` for the same `source_ip`+`username` within W minutes after an R1 match.
- **R3 — Unusual outbound activity:** ≥ M connections from one host to one external IP within W minutes, or any connection to a seeded suspicious indicator. Default M=10.

---

## 6. Incident report contents
Incident summary & severity · event evidence (with IDs) · investigation timeline · threat-intel results with source/status · supported ATT&CK mappings · root-cause hypothesis & uncertainty · recommended actions · approval/rejection history.

---

## 7. Agent contract (applies to every node)
**Input** — shared LangGraph state (incident ID, event IDs/evidence, prior findings). **Tools** — only the bounded tools listed in §4. **Output** — Pydantic schema with `finding`, `evidence_event_ids`, `confidence (qualitative)`, `reasoning_summary`, `recommended_next_step`. **Validation** — referenced event IDs must exist on the incident; technique IDs must exist in the local ATT&CK subset. **Failure handling** — timeouts/API errors are recorded on the `agent_run`, the workflow continues where possible with explicit `unavailable` results, and the run can be retried safely. **Security** — log contents and tool responses are untrusted data; embedded instructions never override policy.

---

## 8. Acceptance criteria — Definition of Done (8/16; Phase 6 items checked)

**Core functionality**
- [x] Loads built-in scenarios and accepts JSON/CSV uploads with size/type limits.
- [x] Parses valid events; malformed records are reported clearly without corrupting data.
- [x] Incidents are created only by real detection rules and preserve underlying evidence.
- [x] Each investigation step's actual status and structured output is visible.

**Agentic AI**
- [x] A multi-step LangGraph workflow runs with structured agent outputs.
- [x] At least one agent calls a real external tool (threat-intel lookup).
- [x] Every finding links to event IDs or other traceable evidence.
- [x] LLM / API failures are handled explicitly — no invented successful results.

**Response & reporting**
- [x] A reasoned response recommendation is produced.
- [x] Approve/reject is recorded with actor + timestamp; simulated vs real is unambiguous.
- [ ] A downloadable report with findings and timeline is generated.
- [x] Incidents, agent runs, and audit history survive page refresh and restart.

**Deployment & demo**
- [ ] Full demo loop works from a clean browser on the public URL.
- [ ] No local-only files or hidden setup steps required.
- [ ] API keys and DB credentials exist only on the server.
- [ ] All three scenarios (A, B, C) demonstrate correctly, including the benign case.

---

## 9. Phase plan reference
Phase 0 scope (this doc) → 1 environment → 2 Next.js shell → 3 FastAPI → 4 PostgreSQL & schemas → 5 ingestion & detection → 6 LangGraph agents → 7 live SSE progress → 8 response center & reports → 9 testing & hardening → 10 Docker → 11 deploy → 12 demo prep.  
One phase at a time; each phase is reviewed, tested, and committed by the project owner before the next begins.

## 10. Open decisions to confirm before Phase 1
1. **LLM provider/model** — decided in Phase 6: `LLM_PROVIDER=none` by default; optional `openai` (`gpt-4o-mini`) with structured JSON. No extra LangChain provider package until another vendor is added.
2. **Threat-intel provider** — decided in Phase 6: `THREAT_INTEL_PROVIDER=none` by default; optional `abuseipdb`. Failures and documentation IPs are `unavailable`, never fabricated as malicious.
3. **Backend host** for FastAPI (needs long-running requests + SSE): Render, Railway, Fly.io, etc.
4. **Authentication for approval endpoints** — decided in Phase 8A: shared `ANALYST_API_TOKEN` bearer token. A valid token records actor `analyst` (generic, not a person). Development/test with an empty token allow decisions as `unverified`. Production with an empty token returns HTTP 403. Missing/invalid bearer when a token is configured returns HTTP 401. Per-user login is deferred.
5. **Report format**: HTML (simplest, no extra deps) vs PDF.
