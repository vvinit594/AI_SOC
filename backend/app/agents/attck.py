"""Local MITRE ATT&CK subset. No live network dependency."""

from __future__ import annotations

from typing import TypedDict


class AttackTechnique(TypedDict):
    technique_id: str
    name: str
    tactic: str
    summary: str


TECHNIQUES: dict[str, AttackTechnique] = {
    "T1110": {
        "technique_id": "T1110",
        "name": "Brute Force",
        "tactic": "Credential Access",
        "summary": "Adversaries may brute-force credentials, including password guessing.",
    },
    "T1078": {
        "technique_id": "T1078",
        "name": "Valid Accounts",
        "tactic": "Defense Evasion",
        "summary": "Adversaries may use legitimate credentials to bypass access controls.",
    },
    "T1071": {
        "technique_id": "T1071",
        "name": "Application Layer Protocol",
        "tactic": "Command and Control",
        "summary": "Adversaries may use application-layer protocols to blend in with traffic.",
    },
    "T1041": {
        "technique_id": "T1041",
        "name": "Exfiltration Over C2 Channel",
        "tactic": "Exfiltration",
        "summary": "Adversaries may steal data over an existing command-and-control channel.",
    },
}


def get_attack_technique(technique_id: str) -> AttackTechnique | None:
    normalized = technique_id.strip().upper()
    return TECHNIQUES.get(normalized)
