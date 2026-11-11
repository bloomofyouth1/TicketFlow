import os

import httpx
import streamlit as st


API = os.getenv(
    "TICKETFLOW_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

st.set_page_config(
    page_title="TicketFlow",
    page_icon="🎫",
    layout="wide",
)


def api(method, path, **kwargs):
    try:
        with httpx.Client(timeout=15) as client:
            response = client.request(
                method, API + path, **kwargs
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get(
                "detail", exc.response.text
            )
        except ValueError:
            detail = exc.response.text
        st.error(
            f"API 错误 {exc.response.status_code}: {detail}"
        )
    except httpx.RequestError as exc:
        st.error(
            f"无法连接后端 API：{type(exc).__name__}"
        )
    return None


def set_selected(ticket_id):
    st.session_state.selected_ticket = ticket_id


st.title("🎫 TicketFlow")
st.caption(
    "企业智能工单处置平台 · "
    "DeepSeek + LangGraph + FastAPI"
)

health = api("GET", "/health")
if health is None:
    st.warning(
        "FastAPI 尚不可用。请先启动后端服务。"
    )
    st.stop()

tab1, tab2, tab3 = st.tabs([
    "📋 工单管理",
    "🤖 Agent 工作台",
    "👤 人工审核",
])

with tab1:
    st.subheader("创建工单")

    with st.form("create_ticket", clear_on_submit=True):
        user_id = st.text_input(
            "客户编号", value="demo_customer"
        )
        content = st.text_area(
            "工单内容",
            placeholder="例如：忘记密码，怎么重置密码？",
        )
        submitted = st.form_submit_button(
            "提交工单", type="primary"
        )

        if submitted:
            if not user_id.strip() or not content.strip():
                st.error("客户编号和工单内容不能为空")
            else:
                data = api(
                    "POST", "/tickets",
                    json={
                        "user_id": user_id.strip(),
                        "content": content.strip(),
                    },
                )
                if data:
                    set_selected(data["id"])
                    st.success(
                        f"工单创建成功：{data['id']}"
                    )

    st.divider()
    st.subheader("工单列表")

    left, right = st.columns([2, 1])

    with left:
        status = st.selectbox(
            "状态筛选",
            ["all", "pending", "processing",
             "escalated", "resolved"],
        )
    with right:
        if st.button("刷新列表"):
            st.rerun()

    params = {"limit": 100, "offset": 0}
    if status != "all":
        params["status"] = status

    tickets = api(
        "GET", "/tickets", params=params
    )

    if tickets is not None:
        st.dataframe(
            tickets,
            use_container_width=True,
            hide_index=True,
        )

        if tickets:
            ids = [item["id"] for item in tickets]
            choice = st.selectbox(
                "选择工单",
                ids,
                format_func=lambda ticket_id: (
                    next(
                        (
                            t["content"][:55]
                            for t in tickets
                            if t["id"] == ticket_id
                        ),
                        ticket_id,
                    )
                    + " | " + ticket_id[:8]
                ),
            )
            if st.button("查看该工单"):
                set_selected(choice)
                st.success("已切换当前工单")


selected = st.session_state.get("selected_ticket")

with tab2:
    st.subheader("Agent 工作台")

    ticket_id = st.text_input(
        "当前工单 ID",
        value=selected or "",
        key="agent_ticket_id",
    ).strip()

    if ticket_id:
        ticket = api(
            "GET", f"/tickets/{ticket_id}"
        )
        if ticket:
            st.write("**工单状态：**", ticket["status"])
            st.write("**客户问题：**", ticket["content"])

            if ticket["status"] == "pending":
                if st.button(
                    "启动异步 Agent",
                    type="primary",
                ):
                    task = api(
                        "POST",
                        f"/tickets/{ticket_id}/process-async",
                    )
                    if task:
                        st.session_state.current_task = task["id"]
                        st.success(
                            f"任务已提交：{task['id']}"
                        )

            result = api(
                "GET",
                f"/tickets/{ticket_id}/processing-result",
            )
            if result:
                st.subheader("处置结果")
                st.json(result)

    task_id = st.text_input(
        "任务 ID",
        value=st.session_state.get(
            "current_task", ""
        ),
        key="task_id_input",
    ).strip()

    if task_id:
        if st.button("刷新任务状态"):
            st.rerun()

        task = api(
            "GET", f"/agent-tasks/{task_id}"
        )
        if task:
            st.write("**任务状态：**", task["status"])
            st.json(task)

with tab3:
    st.subheader("人工审核")

    review_ticket_id = st.text_input(
        "待审核工单 ID",
        value=selected or "",
        key="review_ticket_id",
    ).strip()

    if review_ticket_id:
        ticket = api(
            "GET", f"/tickets/{review_ticket_id}"
        )

        if ticket:
            st.write("**当前状态：**", ticket["status"])
            st.write("**工单内容：**", ticket["content"])

            processing = api(
                "GET",
                f"/tickets/{review_ticket_id}/processing-result",
            )
            if processing:
                st.write("**Agent 处理动作：**",
                         processing["action"])
                if processing.get("suggested_reply"):
                    st.text_area(
                        "候选回复",
                        processing["suggested_reply"],
                        disabled=True,
                    )

            reviewer = st.text_input(
                "审核人员编号",
                value="staff_001",
            )
            note = st.text_area(
                "审核意见",
                value="已核对工单处置结果",
            )

            if ticket["status"] == "processing":
                decisions = {
                    "批准并结单": "approve",
                    "驳回并转人工": "reject",
                }
            elif ticket["status"] == "escalated":
                decisions = {
                    "人工处理完成并结单": "resolve",
                }
            else:
                decisions = {}

            if decisions:
                selected_action = st.selectbox(
                    "审核决定",
                    list(decisions.keys()),
                )

                if st.button(
                    "提交审核决定",
                    type="primary",
                ):
                    if not reviewer.strip() or not note.strip():
                        st.error("审核人员和意见不能为空")
                    else:
                        decision = decisions[selected_action]
                        result = api(
                            "POST",
                            (
                                f"/tickets/{review_ticket_id}"
                                f"/reviews/{decision}"
                            ),
                            json={
                                "reviewer_id": reviewer.strip(),
                                "note": note.strip(),
                            },
                        )
                        if result:
                            st.success("审核操作成功")
                            st.rerun()
            else:
                st.info(
                    "当前状态不支持人工审核操作"
                )

            st.divider()
            st.subheader("审核记录")

            reviews = api(
                "GET",
                f"/tickets/{review_ticket_id}/reviews",
            )
            if reviews is not None:
                st.dataframe(
                    reviews,
                    use_container_width=True,
                    hide_index=True,
                )

            st.subheader("状态变更历史")

            events = api(
                "GET",
                f"/tickets/{review_ticket_id}/events",
            )
            if events is not None:
                st.dataframe(
                    events,
                    use_container_width=True,
                    hide_index=True,
                )
