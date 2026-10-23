from __future__ import annotations

import ipaddress
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.core.errors import exception_label
from app.core.time import utc_now
from app.schemas.investigations import ThreatIntelRecord

logger = logging.getLogger(__name__)

_DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)


def is_documentation_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(address in network for network in _DOCUMENTATION_NETWORKS)


class ThreatIntelClient(Protocol):
    def lookup_ip(self, ip: str) -> ThreatIntelRecord: ...


def _unavailable(ip: str, *, provider: str, summary: str) -> ThreatIntelRecord:
    return ThreatIntelRecord(
        indicator=ip,
        status="unavailable",
        provider=provider,
        source=provider,
        fetched_at=utc_now(),
        summary=summary,
    )


class NoneThreatIntel:
    def lookup_ip(self, ip: str) -> ThreatIntelRecord:
        return _unavailable(
            ip,
            provider="none",
            summary="Threat-intelligence provider is disabled; no reputation lookup was performed.",
        )


def _parse_score(value: object) -> tuple[int | None, str]:
    if value is None or isinstance(value, bool):
        return None, "unknown"
    if isinstance(value, int | float):
        score = int(value)
        return score, "suspicious" if score >= 25 else "unknown"
    if isinstance(value, str):
        try:
            score = int(value.strip())
        except ValueError:
            return None, "unknown"
        return score, "suspicious" if score >= 25 else "unknown"
    return None, "unknown"


class AbuseIPDBClient:
    def __init__(self, api_key: str | None, timeout_seconds: int) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds

    def lookup_ip(self, ip: str) -> ThreatIntelRecord:
        if not self._api_key:
            return _unavailable(
                ip,
                provider="abuseipdb",
                summary="AbuseIPDB API key is not configured.",
            )
        try:
            response = httpx.get(
                "https://api.abuseipdb.com/api/v2/check",
                params={"ipAddress": ip, "maxAgeInDays": 90},
                headers={"Key": self._api_key, "Accept": "application/json"},
                timeout=self._timeout,
            )
            response.raise_for_status()
            body: Any = response.json()
            if not isinstance(body, dict):
                raise TypeError("malformed AbuseIPDB envelope")
            payload = body.get("data")
            if not isinstance(payload, dict):
                raise TypeError("malformed AbuseIPDB data")
            score, classification = _parse_score(payload.get("abuseConfidenceScore"))
            return ThreatIntelRecord(
                indicator=ip,
                status="ok",
                provider="abuseipdb",
                source="abuseipdb",
                fetched_at=utc_now(),
                summary="AbuseIPDB returned a reputation score for this indicator.",
                score=score,
                classification=classification,
            )
        except Exception as exc:
            logger.warning("AbuseIPDB lookup failed: %s", exception_label(exc))
            return _unavailable(
                ip,
                provider="abuseipdb",
                summary="AbuseIPDB lookup failed or timed out; reputation is unavailable.",
            )


class CachingThreatIntel:
    def __init__(self, inner: ThreatIntelClient, ttl_seconds: int) -> None:
        self._inner = inner
        self._ttl = timedelta(seconds=ttl_seconds)
        self._cache: dict[str, tuple[datetime, ThreatIntelRecord]] = {}

    def lookup_ip(self, ip: str) -> ThreatIntelRecord:
        now = datetime.now(UTC)
        cached = self._cache.get(ip)
        if cached is not None:
            stored_at, record = cached
            if now - stored_at < self._ttl:
                return record.model_copy(update={"cache_hit": True})
        record = self._inner.lookup_ip(ip)
        if record.status == "ok":
            self._cache[ip] = (now, record)
        return record


def build_threat_intel_client(
    settings: Settings, inner: ThreatIntelClient | None = None
) -> ThreatIntelClient:
    if inner is not None:
        return CachingThreatIntel(inner, settings.threat_intel_cache_ttl_seconds)
    if settings.threat_intel_provider == "abuseipdb":
        client: ThreatIntelClient = AbuseIPDBClient(
            settings.threat_intel_api_key,
            settings.threat_intel_timeout_seconds,
        )
    else:
        client = NoneThreatIntel()
    return CachingThreatIntel(client, settings.threat_intel_cache_ttl_seconds)
