"""
The Chat Assistant Graph — powers the "Ask me anything about this complaint"
box in the AI Complaint Intake Assistant panel.

START -> classify_intent -> (route) -> answer_from_context | answer_general -> END

- answer_from_context: the question is about the complaint currently on screen
  (e.g. "what's the batch number?"), so we answer strictly from the extracted
  form data / source document to avoid hallucinating facts.
- answer_general: the question is about QMS/process knowledge in general
  (e.g. "what does CAPA stand for?"), so we let the reasoning model answer
  from its own knowledge.
"""
from typing import TypedDict, Optional, List, Dict, Any

from langgraph.graph import StateGraph, START, END

from app.agents.llm import chat_completion, chat_completion_json
from app.config import get_settings

settings = get_settings()


class ChatState(TypedDict, total=False):
    history: List[Dict[str, str]]   # [{"role": "user"/"assistant", "content": ...}]
    context: Dict[str, Any]         # current form field values + source_text
    intent: str                     # "context" | "general"
    reply: str


def classify_intent_node(state: ChatState) -> ChatState:
    last_user_msg = state["history"][-1]["content"] if state.get("history") else ""
    messages = [
        {
            "role": "system",
            "content": (
                'Classify the user question as "context" if it asks about the specific '
                'complaint currently being logged (its fields, the uploaded document, its '
                'severity/priority, etc.), or "general" if it asks about QMS concepts, '
                'pharma regulations, or how to use the tool. '
                'Respond with ONLY JSON: {"intent": "context" | "general"}'
            ),
        },
        {"role": "user", "content": last_user_msg},
    ]
    result = chat_completion_json(messages, model=settings.GROQ_EXTRACTION_MODEL)
    state["intent"] = result.get("intent", "context")
    return state


def route_intent(state: ChatState) -> str:
    return "answer_general" if state.get("intent") == "general" else "answer_from_context"


def answer_from_context_node(state: ChatState) -> ChatState:
    context = state.get("context", {}) or {}
    system = (
        "You are the AI Complaint Intake Assistant embedded in a pharmaceutical QMS "
        "Customer Complaint module. Answer the user's question using ONLY the complaint "
        "data below. If the data doesn't contain the answer, say so plainly and suggest "
        "what to ask the reporter for. Be concise and factual.\n\n"
        f"Current complaint data:\n{context}"
    )
    messages = [{"role": "system", "content": system}] + state.get("history", [])
    state["reply"] = chat_completion(messages, model=settings.GROQ_REASONING_MODEL, max_tokens=400)
    return state


def answer_general_node(state: ChatState) -> ChatState:
    system = (
        "You are the AI Complaint Intake Assistant in a pharmaceutical Quality Management "
        "System (QMS) tool used by API/FDF manufacturers. Answer general questions about "
        "QMS processes, complaint handling, CAPA, root cause analysis, or how to use this "
        "tool. Be concise and accurate."
    )
    messages = [{"role": "system", "content": system}] + state.get("history", [])
    state["reply"] = chat_completion(messages, model=settings.GROQ_REASONING_MODEL, max_tokens=400)
    return state


def build_chat_graph():
    graph = StateGraph(ChatState)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("answer_from_context", answer_from_context_node)
    graph.add_node("answer_general", answer_general_node)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_intent,
        {"answer_from_context": "answer_from_context", "answer_general": "answer_general"},
    )
    graph.add_edge("answer_from_context", END)
    graph.add_edge("answer_general", END)

    return graph.compile()


chat_graph = build_chat_graph()
