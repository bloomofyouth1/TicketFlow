import pytest

from app.agents.resolution_agent import finalize_node


CASES = {'V06': '想重置密码，可当时用的是已经注销的公司邮箱，换了新邮箱也收不到通知。', 'V07': '忘记密码只是顺便一提，我主要想核实一笔不认识的登录。'}


def decide(content):
    return finalize_node({
        "content": content,
        "history": [],
        "evidence_ids": ["FAQ-001"],
        "final_answer": "已找到官方自助重置指引。",
        "trace": [],
    })["result"]


@pytest.mark.parametrize("case_id", ["V06", "V07"])
def test_inapplicable_faq_escalates_even_with_evidence(case_id):
    result = decide(CASES[case_id])
    assert result.action == "escalate"
    assert result.suggested_reply is None


@pytest.mark.parametrize("content", [
    "我忘记密码了，注册邮箱可以正常收信，怎么重置密码？",
    "我忘记密码了，刚收到验证码，下一步怎么操作？",
    "我收到了找回密码的邮件，链接还有效，接下来怎么做？",
])
def test_available_self_service_still_allows_suggestion(content):
    result = decide(content)
    assert result.action == "suggest_reply"
    assert result.faq_id == "FAQ-001"
