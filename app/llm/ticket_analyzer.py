import json
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from typing import Literal

load_dotenv()


class TicketAnalysis(BaseModel):
    category: Literal[
        "account",
        "technical_issue",
        "billing",
        "other",
    ]
    summary: str
    priority: Literal["low", "medium", "high"]
    needs_human: bool


@dataclass
class LLMAnalysisResult:
    analysis: TicketAnalysis
    input_tokens: int
    output_tokens: int
    latency_seconds: float
    model: str


def analyze_ticket(content: str) -> LLMAnalysisResult:
    if not content.strip():
        raise ValueError("Ticket content cannot be empty")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is missing")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv(
            "DEEPSEEK_BASE_URL",
            "https://api.deepseek.com",
        ),
        timeout=30.0,
        max_retries=0,
    )

    model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

    system_prompt = """
你是企业SaaS客服工单分析助手。
只能分析工单，不得执行任何账号、付款或系统操作。

请返回一个JSON对象，字段如下：
{
  "category": "account",
  "summary": "简短的问题摘要",
  "priority": "low",
  "needs_human": false
}

category只能是account、technical_issue、billing或other。
priority只能是low、medium或high。

涉及服务器故障、退款争议或账号安全风险时，
needs_human应为true。

只返回JSON，不要输出额外说明。
""".strip()

    start = time.perf_counter()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
        max_tokens=300,
        extra_body={"thinking": {"type": "disabled"}},
    )

    elapsed = time.perf_counter() - start
    raw = response.choices[0].message.content

    if not raw or not raw.strip():
        raise ValueError("LLM returned empty JSON")

    analysis = TicketAnalysis.model_validate(
        json.loads(raw)
    )

    usage = response.usage

    return LLMAnalysisResult(
        analysis=analysis,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        latency_seconds=elapsed,
        model=response.model,
    )
