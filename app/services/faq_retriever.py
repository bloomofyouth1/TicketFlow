import json
from dataclasses import dataclass
from pathlib import Path

from app.services.ticket_classifier import classify_ticket


BASE_DIR = Path(__file__).resolve().parents[2]
FAQ_PATH = BASE_DIR / "data" / "faq.json"


@dataclass
class FAQResult:
    id: str
    title: str
    category: str
    answer: str
    score: int


def load_faq():
    with FAQ_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def retrieve_faq(content: str, top_k: int = 3) -> list[FAQResult]:
    if top_k < 1:
        raise ValueError("top_k must be positive")

    if not content.strip():
        return []

    category = classify_ticket(content).category
    text = content.casefold()

    results = []

    for item in load_faq():
        if item["category"] != category:
            continue

        matched = [
            keyword
            for keyword in item["keywords"]
            if keyword.casefold() in text
        ]

        if not matched:
            continue

        results.append(
            FAQResult(
                id=item["id"],
                title=item["title"],
                category=item["category"],
                answer=item["answer"],
                score=len(matched),
            )
        )

    results.sort(key=lambda x: (-x.score, x.id))

    return results[:top_k]
