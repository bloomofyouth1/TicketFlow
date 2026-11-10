import json
import logging
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import START, END, StateGraph

from app.agents.ticket_graph import run_ticket_graph
from app.llm.ticket_analyzer import analyze_ticket
from app.services.ticket_processor import ProcessingResult


logger = logging.getLogger("ticketflow.agent")


class HybridState(TypedDict, total=False):
    content: str
    baseline: ProcessingResult
    analysis: object
    result: ProcessingResult
    llm_error: str | None
    input_tokens: int
    output_tokens: int
    latency_seconds: float
    model: str


@dataclass
class HybridOutcome:
    result: ProcessingResult
    input_tokens: int
    output_tokens: int
    latency_seconds: float
    fallback: bool


def baseline_node(state: HybridState) -> dict:
    return {
        "baseline": run_ticket_graph(state["content"])
    }


def analyze_node(state: HybridState) -> dict:
    try:
        output = analyze_ticket(state["content"])

        return {
            "analysis": output.analysis,
            "input_tokens": output.input_tokens,
            "output_tokens": output.output_tokens,
            "latency_seconds": output.latency_seconds,
            "model": output.model,
            "llm_error": None,
        }

    except Exception as exc:
        # 不记录 API Key、原始工单文本或异常详情
        return {
            "llm_error": type(exc).__name__,
        }


def guard_node(state: HybridState) -> dict:
    baseline = state["baseline"]
    analysis = state.get("analysis")

    # LLM 不可用：返回原有规则结果
    if analysis is None:
        return {"result": baseline}

    # 高风险类别由确定性规则保证转人工
    if baseline.category in {"technical_issue", "billing"}:
        return {
            "result": ProcessingResult(
                category=baseline.category,
                action="escalate",
                faq_id=baseline.faq_id,
                suggested_reply=None,
                reason="High-risk category requires human review",
                method="llm_guarded",
            )
        }

    # 模型与规则分类不一致：保守转人工
    if analysis.category != baseline.category:
        return {
            "result": ProcessingResult(
                category=baseline.category,
                action="escalate",
                faq_id=baseline.faq_id,
                suggested_reply=None,
                reason="Model and rule category disagreement",
                method="llm_guarded",
            )
        }

    # LLM 判断需要人工，不允许规则覆盖
    if analysis.needs_human:
        return {
            "result": ProcessingResult(
                category=baseline.category,
                action="escalate",
                faq_id=baseline.faq_id,
                suggested_reply=None,
                reason="LLM requested human review",
                method="llm_guarded",
            )
        }

    # 只有原规则允许时，才能生成候选回复
    return {
        "result": ProcessingResult(
            category=baseline.category,
            action=baseline.action,
            faq_id=baseline.faq_id,
            suggested_reply=baseline.suggested_reply,
            reason=baseline.reason,
            method="llm_guarded",
        )
    }


builder = StateGraph(HybridState)

builder.add_node("baseline", baseline_node)
builder.add_node("analyze", analyze_node)
builder.add_node("guard", guard_node)

builder.add_edge(START, "baseline")
builder.add_edge("baseline", "analyze")
builder.add_edge("analyze", "guard")
builder.add_edge("guard", END)

hybrid_graph = builder.compile()


def run_hybrid_ticket_graph(content: str) -> ProcessingResult:
    state = hybrid_graph.invoke(
        {"content": content},
        config={"recursion_limit": 10},
    )

    result = state["result"]

    logger.info(
        json.dumps(
            {
                "event": "agent_execution",
                "method": result.method,
                "action": result.action,
                "model": state.get("model"),
                "input_tokens": state.get("input_tokens", 0),
                "output_tokens": state.get("output_tokens", 0),
                "latency_seconds": state.get("latency_seconds", 0),
                "fallback": state.get("analysis") is None,
                "error_type": state.get("llm_error"),
            },
            ensure_ascii=False,
        )
    )

    return result
