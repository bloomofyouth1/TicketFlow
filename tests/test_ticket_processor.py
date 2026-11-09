from app.services.ticket_processor import process_ticket_content


def test_password_reset_suggests_reply():
    result = process_ticket_content("忘记密码，怎么重置密码")

    assert result.category == "account"
    assert result.action == "suggest_reply"
    assert result.faq_id == "FAQ-001"
    assert result.suggested_reply is not None


def test_technical_issue_escalates():
    result = process_ticket_content("系统提示 HTTP 500")

    assert result.action == "escalate"
    assert result.suggested_reply is None


def test_billing_escalates():
    result = process_ticket_content("我想申请退款")

    assert result.action == "escalate"


def test_unknown_issue_escalates():
    result = process_ticket_content("你们支持哪些报表功能？")

    assert result.action == "escalate"
    assert result.faq_id is None


def test_account_without_approved_faq_escalates():
    result = process_ticket_content("账号被冻结了")

    assert result.action == "escalate"
