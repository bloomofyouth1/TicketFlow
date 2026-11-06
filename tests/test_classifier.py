from app.services.ticket_classifier import classify_ticket


def test_technical_issue():
    result = classify_ticket("系统提示 HTTP 500")
    assert result.category == "technical_issue"
    assert result.method == "rule"


def test_billing():
    result = classify_ticket("客户要求退款")
    assert result.category == "billing"


def test_account():
    result = classify_ticket("忘记密码，无法登录")
    assert result.category == "account"


def test_other():
    result = classify_ticket("请问支持哪些功能")
    assert result.category == "other"
    assert result.matched_keywords == []


def test_category_priority():
    result = classify_ticket(
        "无法登录，提示 HTTP 500"
    )
    assert result.category == "technical_issue"


def test_case_insensitive():
    result = classify_ticket(
        "系统提示 http 500"
    )
    assert result.category == "technical_issue"
