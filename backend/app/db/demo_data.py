"""Stable demo dataset for the three frozen scenarios (RFC 5737 documentation IPs)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

BRUTE_FAILURE_IDS = [
    uuid.UUID("e0a10001-0001-4a11-8c01-000000000001"),
    uuid.UUID("e0a10001-0002-4a11-8c01-000000000002"),
    uuid.UUID("e0a10001-0003-4a11-8c01-000000000003"),
    uuid.UUID("e0a10001-0004-4a11-8c01-000000000004"),
    uuid.UUID("e0a10001-0005-4a11-8c01-000000000005"),
    uuid.UUID("e0a10001-0006-4a11-8c01-000000000006"),
    uuid.UUID("e0a10001-0007-4a11-8c01-000000000007"),
    uuid.UUID("e0a10001-0008-4a11-8c01-000000000008"),
    uuid.UUID("e0a10001-0009-4a11-8c01-000000000009"),
    uuid.UUID("e0a10001-0010-4a11-8c01-000000000010"),
    uuid.UUID("e0a10001-0011-4a11-8c01-000000000011"),
    uuid.UUID("e0a10001-0012-4a11-8c01-000000000012"),
]
BRUTE_SUCCESS_ID = uuid.UUID("e0a10001-0013-4a11-8c01-000000000013")
OUTBOUND_IDS = [
    uuid.UUID("e0b20001-0001-4b22-8d01-000000000021"),
    uuid.UUID("e0b20001-0002-4b22-8d01-000000000022"),
    uuid.UUID("e0b20001-0003-4b22-8d01-000000000023"),
    uuid.UUID("e0b20001-0004-4b22-8d01-000000000024"),
    uuid.UUID("e0b20001-0005-4b22-8d01-000000000025"),
    uuid.UUID("e0b20001-0006-4b22-8d01-000000000026"),
    uuid.UUID("e0b20001-0007-4b22-8d01-000000000027"),
    uuid.UUID("e0b20001-0008-4b22-8d01-000000000028"),
    uuid.UUID("e0b20001-0009-4b22-8d01-000000000029"),
    uuid.UUID("e0b20001-0010-4b22-8d01-000000000030"),
]
BENIGN_IDS = [
    uuid.UUID("e0c30001-0001-4c33-8e01-000000000041"),
    uuid.UUID("e0c30001-0002-4c33-8e01-000000000042"),
    uuid.UUID("e0c30001-0003-4c33-8e01-000000000043"),
    uuid.UUID("e0c30001-0004-4c33-8e01-000000000044"),
    uuid.UUID("e0c30001-0005-4c33-8e01-000000000045"),
]

INCIDENT_BRUTE_ID = uuid.UUID("a1e0c3f2-4b91-4d2a-9c18-11b0a0b7e001")
INCIDENT_OUTBOUND_ID = uuid.UUID("b2f1d4e3-5c02-4e3b-8d29-22c1b1c8e002")
INCIDENT_BENIGN_ID = uuid.UUID("c3a2e5f4-6d13-4f4c-7e3a-33d2c2d9e003")


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def demo_events() -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for index, event_id in enumerate(BRUTE_FAILURE_IDS):
        minute = 15 + index // 4
        second = (index * 7) % 60
        events.append(
            {
                "id": event_id,
                "timestamp": _ts(f"2026-10-21T10:{minute:02d}:{second:02d}Z"),
                "event_type": "login_failure",
                "source_ip": "192.0.2.10",
                "destination_ip": None,
                "username": "demo_user",
                "hostname": "demo-server-01",
                "action": "authentication_failed",
                "source": "linux_auth",
                "raw_message": (
                    f"Failed password for demo_user from 192.0.2.10 port {51200 + index} ssh2"
                ),
                "scenario": "A",
            }
        )
    events.append(
        {
            "id": BRUTE_SUCCESS_ID,
            "timestamp": _ts("2026-10-21T10:19:48Z"),
            "event_type": "login_success",
            "source_ip": "192.0.2.10",
            "destination_ip": None,
            "username": "demo_user",
            "hostname": "demo-server-01",
            "action": "authentication_succeeded",
            "source": "linux_auth",
            "raw_message": "Accepted password for demo_user from 192.0.2.10 port 51312 ssh2",
            "scenario": "A",
        }
    )
    for index, event_id in enumerate(OUTBOUND_IDS):
        events.append(
            {
                "id": event_id,
                "timestamp": _ts(f"2026-10-21T11:{2 + index:02d}:14Z"),
                "event_type": "outbound_connection",
                "source_ip": "192.0.2.50",
                "destination_ip": "198.51.100.88",
                "username": None,
                "hostname": "demo-server-02",
                "action": "connection_opened",
                "source": "firewall",
                "raw_message": (
                    f"Outbound TCP 192.0.2.50:44300 -> 198.51.100.88:443 (repeat {index + 1}/10)"
                ),
                "scenario": "B",
            }
        )
    events.extend(
        [
            {
                "id": BENIGN_IDS[0],
                "timestamp": _ts("2026-10-21T08:01:12Z"),
                "event_type": "login_success",
                "source_ip": "192.0.2.40",
                "destination_ip": None,
                "username": "j.patel",
                "hostname": "demo-workstation-04",
                "action": "authentication_succeeded",
                "source": "linux_auth",
                "raw_message": "Accepted publickey for j.patel from 192.0.2.40 port 49811 ssh2",
                "scenario": "C",
            },
            {
                "id": BENIGN_IDS[1],
                "timestamp": _ts("2026-10-21T08:03:44Z"),
                "event_type": "login_success",
                "source_ip": "192.0.2.41",
                "destination_ip": None,
                "username": "a.chen",
                "hostname": "demo-workstation-07",
                "action": "authentication_succeeded",
                "source": "linux_auth",
                "raw_message": "Accepted publickey for a.chen from 192.0.2.41 port 50102 ssh2",
                "scenario": "C",
            },
            {
                "id": BENIGN_IDS[2],
                "timestamp": _ts("2026-10-21T08:07:02Z"),
                "event_type": "login_failure",
                "source_ip": "192.0.2.42",
                "destination_ip": None,
                "username": "m.rossi",
                "hostname": "demo-workstation-09",
                "action": "authentication_failed",
                "source": "linux_auth",
                "raw_message": "Failed password for m.rossi from 192.0.2.42 port 50331 ssh2",
                "scenario": "C",
            },
            {
                "id": BENIGN_IDS[3],
                "timestamp": _ts("2026-10-21T08:07:18Z"),
                "event_type": "login_success",
                "source_ip": "192.0.2.42",
                "destination_ip": None,
                "username": "m.rossi",
                "hostname": "demo-workstation-09",
                "action": "authentication_succeeded",
                "source": "linux_auth",
                "raw_message": "Accepted password for m.rossi from 192.0.2.42 port 50332 ssh2",
                "scenario": "C",
            },
            {
                "id": BENIGN_IDS[4],
                "timestamp": _ts("2026-10-21T08:30:00Z"),
                "event_type": "admin_task",
                "source_ip": "192.0.2.20",
                "destination_ip": None,
                "username": "svc-backup",
                "hostname": "demo-server-01",
                "action": "scheduled_backup_started",
                "source": "cron",
                "raw_message": (
                    "Authorized scheduled backup job BACKUP-DAILY-0830 started by svc-backup"
                ),
                "scenario": "C",
            },
        ]
    )
    return events


def demo_incidents() -> list[dict[str, object]]:
    return [
        {
            "id": INCIDENT_BRUTE_ID,
            "title": "Brute-force login followed by success on demo_user",
            "severity": "critical",
            "status": "awaiting_approval",
            "summary": (
                "12 failed SSH logins for demo_user from 192.0.2.10 within five minutes, "
                "immediately followed by a successful login from the same source."
            ),
            "scenario": "A",
            "created_at": _ts("2026-10-21T10:20:02Z"),
            "event_ids": [*BRUTE_FAILURE_IDS, BRUTE_SUCCESS_ID],
        },
        {
            "id": INCIDENT_OUTBOUND_ID,
            "title": "Repeated outbound connections to 198.51.100.88",
            "severity": "high",
            "status": "investigating",
            "summary": (
                "demo-server-02 opened 10 outbound TCP connections to 198.51.100.88:443 "
                "in a short window."
            ),
            "scenario": "B",
            "created_at": _ts("2026-10-21T11:12:40Z"),
            "event_ids": list(OUTBOUND_IDS),
        },
        {
            "id": INCIDENT_BENIGN_ID,
            "title": "Routine morning logins and scheduled backup",
            "severity": "low",
            "status": "resolved",
            "summary": (
                "Business-hours logins by known staff and one isolated failed password, "
                "followed by an authorized backup job."
            ),
            "scenario": "C",
            "created_at": _ts("2026-10-21T08:31:10Z"),
            "event_ids": list(BENIGN_IDS),
        },
    ]
