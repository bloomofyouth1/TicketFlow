from dataclasses import dataclass


@dataclass
class ClassificationResult:
    category: str
    matched_keywords: list[str]
    method: str = "rule"


CATEGORY_KEYWORDS = {
    "technical_issue": [
        "http 500",
        "500错误",
        "服务器异常",
        "系统崩溃",
        "数据库连接失败",
        "接口报错",
    ],
    "billing": [
        "扣费",
        "发票",
        "退款",
        "支付",
        "续费",
        "套餐",
    ],
    "account": [
        "登录",
        "密码",
        "账号",
        "账户",
        "验证码",
        "冻结",
    ],
}


def classify_ticket(content: str) -> ClassificationResult:
    text = content.strip().casefold()

    for category, keywords in CATEGORY_KEYWORDS.items():
        matched = [
            keyword
            for keyword in keywords
            if keyword.casefold() in text
        ]

        if matched:
            return ClassificationResult(
                category=category,
                matched_keywords=matched,
            )

    return ClassificationResult(
        category="other",
        matched_keywords=[],
    )
