import re
from collections.abc import Mapping, Sequence

VERIFICATION_BYPASS = re.compile(
    r"(?:跳过|绕过|免除|省略).{0,12}(?:验证码|验证|核验|认证)"
    r"|(?:不用|不经过|无需).{0,8}(?:验证身份|身份验证|身份核验|验证码)"
)
OTHER_PERSON = re.compile(r"同事|其他员工|另一个员工|他人|别人的")
ACCOUNT_DATA = re.compile(r"密码|口令|登录邮箱|注册邮箱|绑定邮箱")
ACCOUNT_ACTION = re.compile(r"发给|告诉|提供|查看|改成|修改|更换|重置|进入|登录")


# FAQ-001 applicability
FAQ_001_MANUAL_REVIEW = (
    # Recovery email unavailable or unfamiliar sign-in
    (
        re.compile(
            r"(?:已经|早已|已)(?:被)?(?:注销|停用|关闭|作废)的[^，。；\n]{0,10}邮箱"
            r"|(?:注册|登记|绑定|原来的|原先的).{0,8}邮箱.{0,12}"
            r"(?:已|已经|早已)(?:被)?(?:注销|关闭|作废)"
        ),
        "The original recovery email is unavailable",
    ),
    (
        re.compile(
            r"(?:不认识|没见过)的(?:设备|地点)?(?:从这里)?(?:登录|登入)"
            r"|(?:陌生|可疑)的?(?:登录|登入)(?:活动|记录|提醒)?"
        ),
        "Unrecognized sign-in activity requires human review",
    ),
    (
        re.compile(
            r"(?:已经|已|试过|按指引).{0,24}(?:重置|重设).{0,24}"
            r"(?:仍|还是|依旧|却|失败)"
            r"|(?:重置|重设)(?:密码)?(?:已经|已)?成功.{0,24}"
            r"(?:无法登录|停用|锁定|冻[结結])"
        ),
        "Password reset did not resolve the reported issue",
    ),
    (
        re.compile(
            r"(?:注册|绑定).{0,4}邮[箱件].{0,16}"
            r"(?:停用|无法使用|不能用|无法访问|收不到)"
            r"|(?:收不到|无法收到).{0,12}(?:找回|重置|验证)邮件"
            r"|链接.{0,14}(?:失效|过期|无效)"
        ),
        "A prerequisite for self-service password reset is unavailable",
    ),
    (
        re.compile(
            r"(?:不是要|不想|不需要|不用).{0,10}"
            r"(?:重置|重设|找回)(?:密码|账号|账户)"
            r"|(?:只想|仅想|只需要).{0,16}(?:登录记录|按钮名称)"
        ),
        "The ticket does not request a password reset",
    ),
    (
        re.compile(
            r"(?:绑定|注册|登录)邮箱.{0,12}(?:换成|改成|更换|修改)"
            r"|(?:更换|修改|改绑).{0,8}(?:绑定|注册|登录)邮箱"
            r"|(?:陌生|异常|不认识的).{0,6}(?:设备|地点).{0,12}(?:登录|登入)"
            r"|(?:疑似|怀疑).{0,10}(?:盗号|被盗)"
        ),
        "Account security or recovery details require human review",
    ),
)


def faq_001_review_reason(content: str) -> str | None:
    # 有明确的凭据恢复意图或措辞时，才检查此 FAQ 的适用条件。
    if not re.search(r"密码|口令", content):
        return None

    for pattern, reason in FAQ_001_MANUAL_REVIEW:
        if pattern.search(content):
            return reason

    return None


def required_human_review(
    content: str,
    history: Sequence[Mapping],
) -> str | None:
    """Return the reason when the ticket must stay with human support."""
    for event in reversed(history):
        if event.get("to_status") != "processing":
            continue
        actor = event.get("actor") or ""
        if event.get("from_status") == "escalated" and actor.startswith("human:"):
            return "Ticket is already under human ownership"
        break

    for clause in re.split(r"[，。！？；,\n]", content):
        if VERIFICATION_BYPASS.search(clause):
            return "Request asks to bypass identity verification"

        if (
            OTHER_PERSON.search(clause)
            and ACCOUNT_DATA.search(clause)
            and ACCOUNT_ACTION.search(clause)
        ):
            return "Request concerns another person's account credentials"

    return faq_001_review_reason(content)


CREDENTIAL_CONTEXT = re.compile(r"密码|口令|登录|登入")
RECOVERY_ACTION = re.compile(
    r"忘记|忘了|记不起|想不起|记不清|重置|重设|"
    r"重新设|设.{0,5}新的|找回|换一个"
)


def has_credential_recovery_intent(content: str) -> bool:
    return bool(
        CREDENTIAL_CONTEXT.search(content)
        and RECOVERY_ACTION.search(content)
    )
