import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.nodes import NODE_NAMES
from app.db.models import AgentRun
from app.services import progress
from app.services.investigations import RunRecorder
from app.tests.test_investigations import _open_incident


def _parse_sse(text: str) -> list[dict]:
    events: list[dict] = []
    for block in text.split("\n\n"):
        stripped = block.strip()
        if not stripped or stripped.startswith(":"):
            continue
        item: dict = {}
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("id:"):
                item["id"] = line.split(":", 1)[1].strip()
            elif line.startswith("event:"):
                item["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if data_lines:
            item["data"] = json.loads("\n".join(data_lines))
        if item:
            events.append(item)
    return events


def _read_until_terminal(client: TestClient, investigation_id: str, timeout: float = 8.0) -> str:
    deadline = time.monotonic() + timeout
    chunks: list[str] = []
    with client.stream("GET", f"/api/investigations/{investigation_id}/stream") as response:
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/event-stream")
        for piece in response.iter_text():
            chunks.append(piece)
            body = "".join(chunks)
            if "investigation_completed" in body or "investigation_failed" in body:
                break
            if time.monotonic() > deadline:
                break
    return "".join(chunks)


def test_sse_unknown_investigation_404(client: TestClient) -> None:
    response = client.get(f"/api/investigations/{uuid.uuid4()}/stream")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_sse_replays_completed_investigation(client: TestClient) -> None:
    incident_id = _open_incident(client)
    created = client.post(f"/api/incidents/{incident_id}/investigate")
    assert created.status_code == 200, created.text
    investigation_id = created.json()["investigation"]["id"]
    body = _read_until_terminal(client, investigation_id)
    events = _parse_sse(body)
    names = [item["event"] for item in events]
    assert names[0] == "connected"
    assert names[-1] == "investigation_completed"
    assert names.count("node_started") == 4
    assert names.count("node_completed") == 4
    assert {item["data"]["agent_name"] for item in events if item["event"] == "node_started"} == {
        "investigation",
        "threat_intelligence",
        "analysis",
        "response_planner",
    }
    for item in events:
        payload = item.get("data", {})
        assert "structured_output" not in payload
        assert "raw_message" not in json.dumps(payload)
        assert "LLM_API_KEY" not in json.dumps(payload)


def test_sse_last_event_id_skips_replayed_events(client: TestClient) -> None:
    incident_id = _open_incident(client)
    created = client.post(f"/api/incidents/{incident_id}/investigate")
    investigation_id = created.json()["investigation"]["id"]
    with client.stream(
        "GET",
        f"/api/investigations/{investigation_id}/stream",
        headers={"Last-Event-ID": "analysis:completed"},
    ) as response:
        body = "".join(response.iter_text())
    events = _parse_sse(body)
    names = [item["event"] for item in events]
    assert names[0] == "connected"
    assert "investigation" not in [
        item["data"].get("agent_name") for item in events if item["event"] == "node_started"
    ]
    assert any(
        item["data"].get("agent_name") == "response_planner" and item["event"] == "node_completed"
        for item in events
    )
    assert names[-1] == "investigation_completed"


def test_sse_heartbeat_on_idle_queued_investigation(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(progress, "HEARTBEAT_INTERVAL_SECONDS", 0.05)
    monkeypatch.setattr(progress, "POLL_INTERVAL_SECONDS", 0.02)
    incident_id = _open_incident(client)
    investigation_id = uuid.uuid4()
    session = client.app.state.session_factory()
    try:
        for name in NODE_NAMES:
            session.add(
                AgentRun(
                    investigation_id=investigation_id,
                    incident_id=uuid.UUID(incident_id),
                    agent_name=name,
                    status="queued",
                    structured_output={},
                )
            )
        session.commit()
    finally:
        session.close()
    chunks: list[str] = []
    with client.stream("GET", f"/api/investigations/{investigation_id}/stream") as response:
        assert response.status_code == 200
        for piece in response.iter_text():
            chunks.append(piece)
            if ": heartbeat" in "".join(chunks):
                break
    assert ": heartbeat" in "".join(chunks)


def test_sse_failed_investigation_emits_terminal_failure(client: TestClient, monkeypatch) -> None:
    from app.agents import nodes as agent_nodes

    incident_id = _open_incident(client)

    def _boom(*_args: object, **_kwargs: object) -> list:
        raise RuntimeError("password=super-secret raw_message=Accepted password")

    monkeypatch.setattr(agent_nodes, "search_incident_events", _boom)
    failed = client.post(f"/api/incidents/{incident_id}/investigate")
    assert failed.status_code == 500
    session = client.app.state.session_factory()
    try:
        row = session.scalar(select(AgentRun).where(AgentRun.incident_id == uuid.UUID(incident_id)))
        assert row is not None
        investigation_id = str(row.investigation_id)
    finally:
        session.close()
    body = _read_until_terminal(client, investigation_id)
    assert "super-secret" not in body
    assert "Accepted password" not in body
    events = _parse_sse(body)
    assert events[-1]["event"] == "investigation_failed"
    failed_nodes = [item for item in events if item["event"] == "node_failed"]
    assert failed_nodes
    assert all(
        item["data"].get("error") in {None, "Error", "RuntimeError"} for item in failed_nodes
    )


def test_sse_two_clients_see_the_same_replay(client: TestClient) -> None:
    incident_id = _open_incident(client)
    created = client.post(f"/api/incidents/{incident_id}/investigate")
    investigation_id = created.json()["investigation"]["id"]
    first = _parse_sse(_read_until_terminal(client, investigation_id))
    second = _parse_sse(_read_until_terminal(client, investigation_id))
    assert [item["event"] for item in first] == [item["event"] for item in second]
    assert [item["id"] for item in first] == [item["id"] for item in second]


def test_sse_follows_live_persisted_progress(client: TestClient, monkeypatch) -> None:
    if client.app.state.engine.dialect.name == "sqlite":
        pytest.skip("Shared StaticPool sqlite cannot overlap POST and SSE; PostgreSQL covers this")

    original = RunRecorder.start

    def _slow_start(self: RunRecorder, agent_name: str) -> AgentRun:
        run = original(self, agent_name)
        time.sleep(0.05)
        return run

    monkeypatch.setattr(RunRecorder, "start", _slow_start)
    incident_id = _open_incident(client)
    ready = threading.Event()

    def _investigate() -> int:
        ready.set()
        response = client.post(f"/api/incidents/{incident_id}/investigate")
        return response.status_code

    def _stream() -> str:
        ready.wait(timeout=5)
        investigation_id = None
        for _ in range(80):
            session = client.app.state.session_factory()
            try:
                row = session.scalar(
                    select(AgentRun).where(AgentRun.incident_id == uuid.UUID(incident_id))
                )
                if row is not None:
                    investigation_id = str(row.investigation_id)
                    break
            finally:
                session.close()
            time.sleep(0.025)
        assert investigation_id is not None
        return _read_until_terminal(client, investigation_id, timeout=15)

    with ThreadPoolExecutor(max_workers=2) as pool:
        stream_future = pool.submit(_stream)
        status_future = pool.submit(_investigate)
        status = status_future.result(timeout=20)
        body = stream_future.result(timeout=20)
    assert status == 200
    events = _parse_sse(body)
    names = [item["event"] for item in events]
    assert names[0] == "connected"
    assert names[-1] == "investigation_completed"
    started = [item["data"]["agent_name"] for item in events if item["event"] == "node_started"]
    completed = [item["data"]["agent_name"] for item in events if item["event"] == "node_completed"]
    assert started == list(NODE_NAMES)
    assert completed == list(NODE_NAMES)
    # started is emitted before completed for the same agent
    for name in NODE_NAMES:
        assert names.index("node_started") <= names.index("node_completed")
        start_at = next(
            i
            for i, item in enumerate(events)
            if item["event"] == "node_started" and item["data"]["agent_name"] == name
        )
        done_at = next(
            i
            for i, item in enumerate(events)
            if item["event"] == "node_completed" and item["data"]["agent_name"] == name
        )
        assert start_at < done_at
