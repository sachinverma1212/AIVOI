"""
The Complaint Intake Graph.

START -> extract -> completeness -> risk -> duplicate -> summary -> root_cause -> capa -> END

This mirrors the "Log Customer Complaint" workflow in the demo: a document is
dropped in, fields are extracted and the form auto-populates, then the bonus
AI features (completeness, risk, duplicate check, summary, root cause, CAPA)
run automatically so the reviewer sees everything in one pass.
"""
from langgraph.graph import StateGraph, START, END

from app.agents.state import IntakeState
from app.agents.nodes import (
    extract_node,
    completeness_node,
    risk_node,
    duplicate_node,
    summary_node,
    root_cause_node,
    capa_node,
)


def build_intake_graph():
    graph = StateGraph(IntakeState)

    graph.add_node("extract_step", extract_node)
    graph.add_node("completeness_step", completeness_node)
    graph.add_node("risk_step", risk_node)
    graph.add_node("duplicate_step", duplicate_node)
    graph.add_node("summary_step", summary_node)
    graph.add_node("root_cause_step", root_cause_node)
    graph.add_node("capa_step", capa_node)

    graph.add_edge(START, "extract_step")
    graph.add_edge("extract_step", "completeness_step")
    graph.add_edge("completeness_step", "risk_step")
    graph.add_edge("risk_step", "duplicate_step")
    graph.add_edge("duplicate_step", "summary_step")
    graph.add_edge("summary_step", "root_cause_step")
    graph.add_edge("root_cause_step", "capa_step")
    graph.add_edge("capa_step", END)

    return graph.compile()


# Compiled once at import time and reused across requests.
intake_graph = build_intake_graph()
