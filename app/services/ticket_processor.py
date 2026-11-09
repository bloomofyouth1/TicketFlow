from dataclasses import dataclass
from typing import Optional

from app.services.ticket_classifier import classify_ticket
from app.services.faq_retriever import retrieve_faq


@dataclass
class ProcessingResult:
    category: str
    action: str
    faq_id: Optional[str]
    suggested_reply: Optional[str]
    reason: str
    method: str = "rule"


def process_ticket_content(content: str) -> ProcessingResult:
    classification = classify_ticket(content)
    category = classification.category

    faq_results = retrieve_faq(content, top_k=1)

    if category in {"technical_issue", "billing"}:
        return ProcessingResult(
            category=category,
            action="escalate",
            faq_id=faq_results[0].id if faq_results else None,
            suggested_reply=None,
            reason="High-risk category requires human review",
        )

    if not faq_results:
        return ProcessingResult(
            category=category,
            action="escalate",
            faq_id=None,
            suggested_reply=None,
            reason="No matching FAQ evidence",
        )

    faq = faq_results[0]

    # 第一版只允许明确的密码重置 FAQ 自动生成候选回复
    if category == "account" and faq.id == "FAQ-001":
        return ProcessingResult(
            category=category,
            action="suggest_reply",
            faq_id=faq.id,
            suggested_reply=faq.answer,
            reason="Matched approved password-reset FAQ",
        )

    return ProcessingResult(
        category=category,
        action="escalate",
        faq_id=faq.id,
        suggested_reply=None,
        reason="Human review required",
    )
