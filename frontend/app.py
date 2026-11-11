import os

import httpx
import streamlit as st


API = os.getenv(
    "TICKETFLOW_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(
    page_title="TicketFlow Console",
    page_icon="🎫",
    layout="wide",
)


def request(method, path, *, quiet_404=False, **kwargs):
    try:
        with httpx.Client(timeout=15) as client:
            response = client.request(
                method, API + path, **kwargs
            )

        if quiet_404 and response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json().get(
                "detail", detail
            )
        except ValueError:
            pass
        st.error(f"API {exc.response.status_code}: {detail}")

    except httpx.RequestError as exc:
        st.error(
            "连接后端失败：" + type(exc).__name__
        )

    return None


def select_ticket(ticket_id):
    st.session_state.ticket_id = ticket_id
    st.session_state.task_id = None


def current_ticket():
    ticket_id = st.session_state.get("ticket_id")
    if not ticket_id:
        return None
    return request(
        "GET", f"/tickets/{ticket_id}",
        quiet_404=True,
    )


def current_processing():
    ticket_id = st.session_state.get("ticket_id")
    if not ticket_id:
        return None
    return request(
        "GET",
        f"/tickets/{ticket_id}/processing-result",
        quiet_404=True,
    )


st.title("🎫 TicketFlow")
st.caption(
    "企业智能工单系统 | "
    "LangGraph · DeepSeek · FastAPI"
)

if request("GET", "/health") is None:
    st.stop()

tickets = request(
    "GET",
    "/tickets",
    params={"limit": 100, "offset": 0},
) or []

with st.sidebar:
    st.header("工单导航")

    if st.button("刷新数据", use_container_width=True):
        st.rerun()

    if tickets:
        ids = [t["id"] for t in tickets]
        current_id = st.session_state.get("ticket_id")

        options = [""] + ids
        initial = (
            options.index(current_id)
            if current_id in options else 0
        )

        chosen = st.selectbox(
            "选择工单",
            options,
            index=initial,
            format_func=lambda x: (
                "请选择" if not x else
                next(
                    (
                        f"{t['status']} | "
                        f"{t['content'][:24]} | {x[:8]}"
                        for t in tickets if t["id"] == x
                    ),
                    x,
                )
            ),
        )

        if chosen and chosen != current_id:
            select_ticket(chosen)
            st.rerun()
    else:
        st.info("暂无工单")

    st.divider()
    st.caption("当前模式由 FastAPI 服务端配置决定")
    st.caption("此版本仅用于受控开发和演示环境")


tab_create, tab_agent, tab_review = st.tabs([
    "📋 工单管理",
    "🤖 Agent 工作台",
    "👤 人工审核",
])


with tab_create:
    st.subheader("创建新工单")

    with st.form("new_ticket", clear_on_submit=True):
        user_id = st.text_input(
            "客户编号",
            value="demo_customer",
        )
        content = st.text_area(
            "问题描述",
            placeholder="例如：忘记密码，怎么重置密码？",
        )

        submitted = st.form_submit_button(
            "创建工单",
            type="primary",
        )

    if submitted:
        if not user_id.strip() or not content.strip():
            st.warning("请填写客户编号和问题描述")
        else:
            result = request(
                "POST",
                "/tickets",
                json={
                    "user_id": user_id.strip(),
                    "content": content.strip(),
                },
            )
            if result:
                select_ticket(result["id"])
                st.rerun()

    st.divider()
    st.subheader("工单列表")

    status_filter = st.selectbox(
        "筛选状态",
        ["all", "pending", "processing",
         "escalated", "resolved"],
    )

    filtered = [
        t for t in tickets
        if status_filter == "all"
        or t["status"] == status_filter
    ]

    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
    )
    st.caption("当前显示最近查询到的最多 100 条工单")


ticket = current_ticket()
processing = current_processing() if ticket else None


with tab_agent:
    st.subheader("Agent 执行控制台")

    if not ticket:
        st.info("请先创建或选择工单")
    else:
        st.write("**工单 ID：**", ticket["id"])
        st.write("**问题：**", ticket["content"])

        status = ticket["status"]
        st.write("**当前状态：**", status)

        if status == "pending":
            if st.button(
                "启动异步 Agent",
                type="primary",
            ):
                task = request(
                    "POST",
                    f"/tickets/{ticket['id']}/process-async",
                )
                if task:
                    st.session_state.task_id = task["id"]
                    st.rerun()

        task_id = st.session_state.get("task_id")

        if task_id:
            task = request(
                "GET", f"/agent-tasks/{task_id}",
                quiet_404=True,
            )
            if task:
                st.subheader("任务状态")
                st.write(task["status"])

                if task["status"] in {"queued", "running"}:
                    st.info("Agent 正在运行，请刷新页面")
                    if st.button("刷新 Agent 状态"):
                        st.rerun()

                if task["status"] == "failed":
                    st.error(
                        "任务执行失败：" +
                        str(task.get("error_type"))
                    )

        if processing:
            st.divider()
            st.subheader("Agent 决策")

            c1, c2, c3 = st.columns(3)
            c1.metric(
                "分类",
                processing["category"],
            )
            c2.metric(
                "处理动作",
                processing["action"],
            )
            c3.metric(
                "处理方法",
                processing["method"],
            )

            st.write(
                "**决策依据：**",
                processing["reason"],
            )

            if processing.get("faq_id"):
                st.write(
                    "**FAQ 来源：**",
                    processing["faq_id"],
                )

            if processing.get("suggested_reply"):
                st.text_area(
                    "待审核候选回复",
                    processing["suggested_reply"],
                    disabled=True,
                    height=120,
                )

        metrics = request(
            "GET",
            f"/tickets/{ticket['id']}/agent-execution",
            quiet_404=True,
        )

        if metrics:
            st.divider()
            st.subheader("Agent 运行指标")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric(
                "总 Token",
                metrics["total_tokens"],
            )
            m2.metric(
                "模型调用",
                metrics["model_calls"],
            )
            m3.metric(
                "工具调用",
                metrics["tool_calls"],
            )
            m4.metric(
                "执行耗时",
                f"{metrics['latency_seconds']:.2f}s",
            )

            st.write(
                "**调用工具：**",
                " → ".join(metrics["tool_names"])
                or "无",
            )
            st.write(
                "**节点执行路径：**",
                " → ".join(metrics["trace"]),
            )

            if metrics["error_type"]:
                st.warning(
                    "Agent 异常：" + metrics["error_type"]
                )

            with st.expander("查看完整执行指标"):
                st.json(metrics)

        elif processing:
            st.caption(
                "当前处理方式没有独立的 Agent 指标记录"
            )


with tab_review:
    st.subheader("人工审核工作台")

    if not ticket:
        st.info("请先选择工单")
    else:
        st.write("**工单 ID：**", ticket["id"])
        st.write("**当前状态：**", ticket["status"])
        st.write("**工单问题：**", ticket["content"])

        if processing:
            st.write(
                "**Agent 建议：**",
                processing["action"],
            )
            if processing.get("suggested_reply"):
                st.text_area(
                    "待审核回复",
                    processing["suggested_reply"],
                    disabled=True,
                    height=120,
                )

        status = ticket["status"]

        if status == "processing":
            decisions = {
                "批准候选回复并结单": "approve",
                "驳回并转人工": "reject",
            }
        elif status == "escalated":
            decisions = {
                "人工处理完成并结单": "resolve",
            }
        else:
            decisions = {}

        if decisions:
            with st.form(
                f"review_{ticket['id']}_{status}"
            ):
                reviewer = st.text_input(
                    "审核人",
                    value="staff_001",
                )
                note = st.text_area(
                    "审核意见",
                    value="已核对处理结果",
                )
                label = st.selectbox(
                    "审核决定",
                    list(decisions.keys()),
                )
                submit_review = st.form_submit_button(
                    "确认审核",
                    type="primary",
                )

            if submit_review:
                if not reviewer.strip() or not note.strip():
                    st.warning("请填写审核人和审核意见")
                else:
                    decision = decisions[label]
                    result = request(
                        "POST",
                        f"/tickets/{ticket['id']}/reviews/{decision}",
                        json={
                            "reviewer_id": reviewer.strip(),
                            "note": note.strip(),
                        },
                    )
                    if result:
                        st.rerun()
        else:
            st.info("当前状态无需人工审核")

        st.divider()
        st.subheader("审核记录")

        reviews = request(
            "GET",
            f"/tickets/{ticket['id']}/reviews",
        )
        if reviews is not None:
            st.dataframe(
                reviews,
                hide_index=True,
                use_container_width=True,
            )

        st.subheader("工单状态历史")
        events = request(
            "GET",
            f"/tickets/{ticket['id']}/events",
        )
        if events is not None:
            st.dataframe(
                events,
                hide_index=True,
                use_container_width=True,
            )
