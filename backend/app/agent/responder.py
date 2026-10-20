"""Deterministic Chinese responses used in offline mode and as LLM fallback."""
from __future__ import annotations

from typing import Any


def _join(items: list[str], limit: int = 4) -> str:
    items = [item for item in items if item]
    if len(items) > limit:
        return "、".join(items[:limit]) + f"等 {len(items)} 项"
    return "、".join(items)


def _punct(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    return text if text[-1] in "。！？!?…" else text + "。"


def offline_response(
    intent: dict[str, Any],
    tool_results: list[dict[str, Any]],
    *,
    scene_result: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
    error: str | None = None,
) -> str:
    if error:
        return (
            f"抱歉，刚才的处理出现了问题：{error}。"
            "你可以换个说法再试一次，或者直接在设备面板手动操作。"
        )
    if scene_result:
        return scene_result.get("message") or "场景已执行完成。"
    if intent.get("direct_reply"):
        return str(intent["direct_reply"])
    if intent.get("intent_type") == "clarify":
        question = intent.get("clarify") or "我需要确认一下你的目标。"
        options = [option.get("label") for option in intent.get("options", []) if option.get("label")]
        if options:
            return f"{_punct(question)} 可选：{'、'.join(options)}。"
        return _punct(question)
    if intent.get("intent_type") == "knowledge":
        hits = intent.get("knowledge") or []
        answer = next((hit.get("answer") for hit in hits if hit.get("answer")), None)
        if answer:
            return answer
        return (
            "我暂时没在家庭知识库里找到确切答案。"
            "你可以换个更具体的问法，或者问我设备状态、场景推荐和节能建议。"
        )

    successes = [result for result in tool_results if result.get("ok")]
    failures = [result for result in tool_results if not result.get("ok")]
    is_query = str(intent.get("intent", "")).startswith("query_")
    is_query = is_query or any(
        result.get("name", "").startswith("query_") for result in tool_results
    )

    if is_query and successes:
        messages = [result.get("message", "") for result in successes]
        return _punct(" ".join(messages))
    if is_query and not successes:
        if failures:
            return _punct("查询没有完成：" + "；".join(f.get("message", "未知错误") for f in failures))
        return "我暂时没有查到设备状态，请稍后再试。"

    if successes and not failures:
        messages = [result.get("message", "") for result in successes]
        return _punct("好的，" + "；".join(messages))
    if successes and failures:
        success_text = _join([result.get("message", "") for result in successes])
        failure_text = _join([result.get("message", "未知错误") for result in failures])
        return (
            f"已完成{success_text}。不过{failure_text}。"
            "设备可能离线或暂时不可用，你可以在设备面板检查连接后重试。"
        )
    if failures:
        failure_text = _join([result.get("message", "未知错误") for result in failures])
        return (
            f"抱歉，操作没有完成：{failure_text}。"
            "你可以在设备面板确认设备是否在线，或者换一种说法再试。"
        )
    return "我在，想让我做什么？比如开灯、调空调或启动场景。"


def build_scene_result(
    scene: dict[str, Any],
    *,
    results: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    fallback_used: bool,
    fallback_results: list[dict[str, Any]],
    condition: dict[str, Any] | None,
    skipped_reason: str | None = None,
) -> dict[str, Any]:
    name = scene.get("name", "场景")
    if skipped_reason:
        message = f"「{name}」没有执行：{_punct(skipped_reason)}"
        return {
            "scene_id": scene.get("id"),
            "scene_name": name,
            "status": "skipped",
            "message": message,
            "results": results,
            "failures": failures,
            "fallback_used": False,
            "fallback_results": [],
            "condition": condition,
        }

    success_labels = [result.get("label") or result.get("message") for result in results if result.get("ok")]
    failure_labels = [
        f"{failure.get('label') or failure.get('device_name', '设备')}（{failure.get('message', '失败')}）"
        for failure in failures
    ]
    fallback_labels = [
        result.get("label") or result.get("message")
        for result in fallback_results if result.get("ok")
    ]

    if not failures:
        message = f"「{name}」已完成：{_join(success_labels, 6)}。"
        if fallback_used and fallback_labels:
            message += f" 过程中触发了兜底：{_join(fallback_labels, 3)}。"
        status = "success"
    elif results:
        message = f"「{name}」部分完成：{_join(success_labels, 4)}。"
        message += f" 未成功：{_join(failure_labels, 3)}。"
        if fallback_labels:
            message += f" 已启用兜底：{_join(fallback_labels, 3)}。"
        status = "partial"
    elif fallback_labels:
        message = f"「{name}」主流程未完成：{_join(failure_labels, 3)}。"
        message += f" 已通过兜底恢复：{_join(fallback_labels, 3)}，建议检查相关设备连接。"
        status = "partial"
    else:
        message = f"「{name}」执行失败：{_join(failure_labels, 3)}。"
        status = "failed"

    return {
        "scene_id": scene.get("id"),
        "scene_name": name,
        "status": status,
        "message": message,
        "results": results,
        "failures": failures,
        "fallback_used": fallback_used,
        "fallback_results": fallback_results,
        "condition": condition,
    }
