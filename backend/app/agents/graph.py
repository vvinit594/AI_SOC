from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    analysis_node,
    investigation_node,
    response_planner_node,
    threat_intelligence_node,
)


class InvestigationState(TypedDict, total=False):
    incident_id: str
    investigation_id: str
    events: list[dict[str, Any]]
    event_ids: list[str]
    indicators: list[str]
    threat_intel: list[dict[str, Any]]
    analysis: dict[str, Any]
    recommendations: list[dict[str, Any]]
    node_errors: dict[str, str]


def build_investigation_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("investigation", investigation_node)
    graph.add_node("threat_intelligence", threat_intelligence_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("response_planner", response_planner_node)
    graph.add_edge(START, "investigation")
    graph.add_edge("investigation", "threat_intelligence")
    graph.add_edge("threat_intelligence", "analysis")
    graph.add_edge("analysis", "response_planner")
    graph.add_edge("response_planner", END)
    return graph.compile()


INVESTIGATION_GRAPH = build_investigation_graph()


def run_investigation_graph(
    initial: InvestigationState, config: dict[str, Any]
) -> InvestigationState:
    result = INVESTIGATION_GRAPH.invoke(initial, config=config)
    return result  # type: ignore[return-value]
