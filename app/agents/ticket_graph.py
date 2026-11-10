from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.ticket_classifier import classify_ticket
from app.services.faq_retriever import retrieve_faq
from app.services.ticket_processor import ProcessingResult


class TicketState(TypedDict, total=False):
    content: str
    category: str
    matched_keywords: list[str]
    faq_id: str | None
    faq_answer: str | None
    action: str
    suggested_reply: str | None
    reason: str
    method: str
    execution_path: list[str]


def classify_node(state: TicketState) -> dict:
    result = classify_ticket(state["content"])

    return {
        "category": result.category,
        "matched_keywords": result.matched_keywords,
        "execution_path": state.get("execution_path", []) + ["classify"],
    }


def retrieve_node(state: TicketState) -> dict:
    results = retrieve_faq(state["content"], top_k=1)

    if results:
        faq = results[0]
        faq_id = faq.id
        faq_answer = faq.answer
    else:
        faq_id = None
        faq_answer = None

    return {
        "faq_id": faq_id,
        "faq_answer": faq_answer,
        "execution_path": state["execution_path"] + ["retrieve"],
    }


def decide_node(state: TicketState) -> dict:
    category = state["category"]
    faq_id = state.get("faq_id")

    if category in {"technical_issue", "billing"}:
        action = "escalate"
        reason = "High-risk category requires human review"

    elif faq_id is None:
        action = "escalate"
        reason = "No matching FAQ evidence"

    elif category == "account" and faq_id == "FAQ-001":
        action = "suggest_reply"
        reason = "Matched approved password-reset FAQ"

    else:
        action = "escalate"
        reason = "Human review required"

    return {
        "action": action,
        "reason": reason,
        "method": "rule",
        "suggested_reply": (
            state.get("faq_answer")
            if action == "suggest_reply"
            else None
        ),
        "execution_path": state["execution_path"] + ["decide"],
    }


def route_decision(state: TicketState) -> str:
    return state["action"]


def suggest_node(state: TicketState) -> dict:
    return {
        "execution_path": state["execution_path"] + ["suggest_reply"],
    }


def escalate_node(state: TicketState) -> dict:
    return {
        "execution_path": state["execution_path"] + ["escalate"],
    }


def build_ticket_graph():
    builder = StateGraph(TicketState)

    builder.add_node("classify", classify_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("decide", decide_node)
    builder.add_node("suggest_reply", suggest_node)
    builder.add_node("escalate", escalate_node)

    builder.add_edge(START, "classify")
    builder.add_edge("classify", "retrieve")
    builder.add_edge("retrieve", "decide")

    builder.add_conditional_edges(
        "decide",
        route_decision,
        {
            "suggest_reply": "suggest_reply",
            "escalate": "escalate",
        },
    )

    builder.add_edge("suggest_reply", END)
    builder.add_edge("escalate", END)

    return builder.compile()


ticket_graph = build_ticket_graph()


def run_ticket_graph(content: str) -> ProcessingResult:
    state = ticket_graph.invoke(
        {
            "content": content,
            "execution_path": [],
        },
        config={"recursion_limit": 10},
    )

    return ProcessingResult(
        category=state["category"],
        action=state["action"],
        faq_id=state.get("faq_id"),
        suggested_reply=state.get("suggested_reply"),
        reason=state["reason"],
        method=state["method"],
    )
