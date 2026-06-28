from agent_graph.nodes.common import flow_step


def response_node(state):
    if state.get("approval_required"):
        selected = state.get("selected_tool") or {}
        review = state.get("security_review") or {}
        reply = (
            f"找到工具 {selected.get('name') or selected.get('tool_id')}，安装前需要权限审批。\n"
            f"风险等级：{review.get('risk_level')}。\n"
            f"原因：{review.get('reason')}。"
        )
    elif state.get("vision_result"):
        images = state["vision_result"].get("images", [])
        reply = "已完成图片输入分析。\n" + "\n".join(f"- {item.get('filename')}: {item.get('visual_summary')}" for item in images)
    elif state.get("execution_result"):
        result = state["execution_result"]
        if result.get("ok") and isinstance(result.get("result"), dict):
            payload = result["result"]
            content = payload.get("content", "")
            reply = f"web_reader 已读取网页：{payload.get('title') or payload.get('url')}\n\n{content[:1000]}"
        else:
            error = result.get("error") or {}
            reply = f"工具执行失败：{error.get('message') or error.get('code') or 'unknown error'}"
    else:
        reply = "我是 V-Agent。可以进行普通对话，也可以安装受权限审查的工具、执行已安装工具，并处理图片输入。"
    state["final_reply"] = reply
    state["emotion"] = "thinking"
    state.setdefault("agent_flow", []).append(flow_step("Response Agent", "final_reply", reason="compose compatible response"))
    return state

