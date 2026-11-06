import pytest

from app.services.faq_retriever import retrieve_faq


def test_password_faq():
    results = retrieve_faq("忘记密码，怎么重置密码")

    assert len(results) >= 1
    assert results[0].id == "FAQ-001"


def test_technical_faq():
    results = retrieve_faq("系统提示 HTTP 500")

    assert len(results) >= 1
    assert results[0].id == "FAQ-003"


def test_billing_faq():
    results = retrieve_faq("请问如何申请发票")

    assert len(results) >= 1
    assert results[0].id == "FAQ-005"


def test_no_match():
    results = retrieve_faq("今天天气怎么样")

    assert results == []


def test_top_k_limit():
    results = retrieve_faq(
        "系统提示 HTTP 500，服务器异常",
        top_k=1,
    )

    assert len(results) <= 1


def test_invalid_top_k():
    with pytest.raises(ValueError):
        retrieve_faq("忘记密码", top_k=0)


def test_empty_query():
    assert retrieve_faq("   ") == []
