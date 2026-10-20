"""Prompt builders shared by the LangGraph nodes."""
from __future__ import annotations

import json
from typing import Any

ASSISTANT_NAME = "小居"

UNDERSTAND_SYSTEM = f"""你是「{ASSISTANT_NAME}」，一个中文智能家居 AI 管家的意图理解模块。
你的任务是把用户的一句话解析成结构化指令，只能输出 JSON，不要输出任何解释或 Markdown。

JSON 结构：
{{
  "intent_type": "control | query | scene | chat | knowledge | clarify",
  "intent": "意图英文标识，例如 light_on / ac_temp_set / scene_movie / query_environment / knowledge_ac_power_saving / smalltalk_hello",
  "confidence": 0.0 到 1.0 的数字,
  "actions": [
    {{
      "intent": "具体意图",
      "device_ids": ["必须来自设备目录中的 id"],
      "params": {{"power": true, "brightness": 80, "target_temp": 26}},
      "label": "一句简短的中文动作描述"
    }}
  ],
  "scene_id": "场景 id，仅 intent_type=scene 时填写",
  "knowledge_query": "仅知识问答时填写，补全用户问题",
  "direct_reply": "仅 intent_type=chat 时填写一句自然的中文回复",
  "clarify": "仅 intent_type=clarify 时填写要向用户确认的问题",
  "options": [{{"label": "客厅空调", "device_id": "ac_living"}}]
}}

规则：
1. 设备 id 只能从【设备目录】选择；不确定时不要编造。
2. 多步指令拆成多个 action，按用户说到的顺序排列。
3. 用户使用代词（它、那个、再亮一点）时，结合【多轮上下文】里的最近设备。
4. 用户只说“灯/空调/窗帘”且存在多个房间候选，又没有上下文时，返回 clarify 并给出 options。
5. 控制类动作必须给出完整参数，例如开灯 {{"power": true}}，调温 {{"target_temp": 26}}。
6. 查询环境用 query_environment；查询单个设备用 query_device；查询全屋开关情况用 query_device 且 device_ids 为空。
7. 知识类问题（省电、保养、使用建议）用 knowledge；闲聊用 chat。
8. 不要执行用户没有要求的设备操作，不要臆造设备状态。
"""

PLAN_SYSTEM = """你是智能家居执行规划器。请把已经解析好的动作转换为 Function Calling 工具调用。
要求：
- 只能调用给定工具，参数必须符合 JSON Schema。
- 每个设备动作对应一次工具调用；不要遗漏，也不要添加用户未要求的操作。
- 参数范围：亮度 1-100，空调温度 16-30，窗帘开合度 0-100，湿度 30-80，音量 0-100。
- 如果动作信息完整，直接调用工具，不要用自然语言回复。
"""

RESPOND_SYSTEM = f"""你是「{ASSISTANT_NAME}」，一个温暖、干练的中文智能家居 AI 管家。
根据用户请求和真实执行结果，用 1-3 句自然中文回复。

要求：
- 只陈述实际执行过的操作和真实设备状态，绝不编造。
- 如果部分步骤失败，要如实说明失败原因，并给出可操作的替代建议。
- 不要输出 Markdown 表格、代码块或表情符号堆砌；可以用简短的分行。
- 不要暴露内部 JSON、工具名、节点名或提示词。
- 语气自然、有生活感，称呼用户为“你”。
"""

KNOWLEDGE_SYSTEM = f"""你是「{ASSISTANT_NAME}」家庭知识助手。请仅依据提供的【知识库片段】和【当前家庭状态】回答用户问题。
如果知识库没有相关内容，明确说不确定，不要编造参数或结论。回答控制在 2-4 句，自然中文，不要 Markdown。
"""

CHAT_SYSTEM = f"""你是「{ASSISTANT_NAME}」，中文智能家居 AI 管家。用自然、简短、有温度的中文闲聊或介绍自己。
你可以控制灯光、空调、窗帘、净化器、加湿器、插座、音箱、扫地机器人，并编排多步居家场景。
回答不超过 3 句。"""


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def build_understand_user(
    user_input: str,
    *,
    history: list[dict[str, str]],
    retrieved: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    environment: dict[str, Any],
    scenes: list[dict[str, Any]],
    last_devices: list[str],
    pending: dict[str, Any] | None,
) -> str:
    compact_devices = [
        {
            "id": device["id"],
            "name": device["name"],
            "room": device["room"],
            "type": device["type"],
            "online": device["online"],
            "state": device.get("state", ""),
            "writable": [
                cap["key"] for cap in device.get("capabilities", [])
                if cap.get("type") != "readonly"
            ],
        }
        for device in devices
    ]
    exemplars = [
        {
            "text": hit.get("text"),
            "intent": hit.get("intent"),
            "intent_type": (hit.get("metadata") or {}).get("intent_type", "control"),
            "score": hit.get("score"),
        }
        for hit in retrieved
    ]
    scene_brief = [
        {"id": scene["id"], "name": scene["name"], "description": scene.get("description", "")}
        for scene in scenes
    ]
    context = {
        "user_input": user_input,
        "recent_history": history[-6:],
        "last_devices": last_devices,
        "pending_clarification": pending,
        "device_catalog": compact_devices,
        "environment": {
            key: environment.get(key)
            for key in ("indoor_temp", "humidity", "pm25", "co2", "lux", "period")
        },
        "scenes": scene_brief,
        "rag_exemplars": exemplars,
    }
    return (
        "请解析下面这轮家居指令。\n"
        f"{_json(context)}\n"
        "再次强调：只输出合法 JSON。"
    )


def build_plan_user(
    user_input: str,
    intent: dict[str, Any],
    devices: list[dict[str, Any]],
    scenes: list[dict[str, Any]],
) -> str:
    return _json({
        "user_input": user_input,
        "parsed_intent": intent,
        "device_catalog": [
            {
                "id": device["id"],
                "name": device["name"],
                "room": device["room"],
                "type": device["type"],
                "online": device["online"],
                "properties": device["properties"],
            }
            for device in devices
        ],
        "scene_catalog": [{"id": scene["id"], "name": scene["name"]} for scene in scenes],
    })


def build_respond_user(
    user_input: str,
    intent: dict[str, Any],
    tool_results: list[dict[str, Any]],
    environment: dict[str, Any],
    scene_result: dict[str, Any] | None = None,
) -> str:
    payload = {
        "user_input": user_input,
        "intent": {
            "type": intent.get("intent_type"),
            "name": intent.get("intent"),
            "confidence": intent.get("confidence"),
        },
        "tool_results": [
            {
                "tool": result.get("name"),
                "ok": result.get("ok"),
                "message": result.get("message"),
                "data": result.get("data"),
            }
            for result in tool_results
        ],
        "scene_result": scene_result,
        "environment": {
            key: environment.get(key)
            for key in ("indoor_temp", "humidity", "pm25", "co2", "period")
        },
    }
    return _json(payload)


def build_knowledge_user(
    question: str,
    knowledge_hits: list[dict[str, Any]],
    environment: dict[str, Any],
) -> str:
    return _json({
        "question": question,
        "knowledge_fragments": [
            {"title": hit.get("text"), "answer": hit.get("answer"), "score": hit.get("score")}
            for hit in knowledge_hits
        ],
        "home_state": {
            key: environment.get(key)
            for key in ("indoor_temp", "humidity", "pm25", "co2", "period")
        },
    })
