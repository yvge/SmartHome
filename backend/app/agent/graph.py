r"""Top-level LangGraph agent.

    understand -> plan -> guard -> execute -> verify -> respond
              \-> scene (multi-step subgraph) ---------/
              \-> respond (chat / knowledge / clarify)
    plan/guard failures -> fallback -> respond

The graph is compiled with an in-memory checkpointer so follow-ups such as
“再亮一点” can resolve against the previous turn's devices.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agent import prompts
from app.agent.events import RunContext
from app.agent.llm import LLMError
from app.agent.nlu import (
    CLARIFY,
    CHAT,
    CONTROL,
    KNOWLEDGE,
    QUERY,
    SCENE,
    OfflineNLU,
    ParsedIntent,
    normalize_llm_result,
)
from app.agent.responder import offline_response
from app.agent.tools import (
    CONTROL_TOOL_TYPES,
    build_tool_schemas,
    plan_from_actions,
    validate_call,
)

INTENT_TYPE_LABELS = {
    CONTROL: "设备控制",
    QUERY: "状态查询",
    SCENE: "场景执行",
    CHAT: "闲聊",
    KNOWLEDGE: "知识问答",
    CLARIFY: "澄清确认",
}


class AgentState(TypedDict, total=False):
    session_id: str
    user_input: str
    history: list[dict[str, str]]
    last_devices: list[str]
    pending: dict[str, Any] | None
    retrieval: list[dict[str, Any]]
    rag_latency_ms: float
    intent: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    blocked_results: list[dict[str, Any]]
    verification: list[dict[str, Any]]
    scene_result: dict[str, Any] | None
    response: str
    status: str
    error: str | None


def _ctx(config: RunnableConfig) -> RunContext:
    return config["configurable"]["ctx"]


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


def _device_label(runtime, device_id: str | None) -> str:
    if not device_id:
        return "全屋设备"
    try:
        return runtime.devices.get(device_id)["name"]
    except Exception:
        return device_id


async def _emit_text(ctx: RunContext, text: str, *, delay: float = 0.012) -> None:
    """Chunked pseudo-streaming for deterministic offline answers."""
    if not text:
        return
    chunk_size = 6
    for start in range(0, len(text), chunk_size):
        await ctx.emit("token", content=text[start:start + chunk_size])
        if delay:
            await asyncio.sleep(delay)


def build_agent_graph(runtime):
    nlu: OfflineNLU = runtime.nlu

    # ------------------------------------------------------------ understand
    async def understand(state: AgentState, config: RunnableConfig) -> AgentState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "understand"
        await ctx.node_start(node)
        user_input = state["user_input"]
        history = state.get("history", [])
        previous_devices = state.get("last_devices", [])
        pending = state.get("pending")

        intent_result, knowledge_result = await asyncio.gather(
            runtime.rag.search(user_input, top_k=5, kind="intent"),
            runtime.rag.search(user_input, top_k=3, kind="knowledge"),
        )
        retrieved = sorted(
            [*intent_result["hits"], *knowledge_result["hits"]],
            key=lambda hit: float(hit.get("score") or 0),
            reverse=True,
        )
        latency = round(intent_result["latency_ms"] + knowledge_result["latency_ms"], 2)
        await ctx.emit(
            "retrieval",
            intents=intent_result["hits"],
            knowledge=knowledge_result["hits"],
            latency_ms=latency,
            backend=runtime.rag.store.backend if runtime.rag.store else "none",
        )

        parsed: ParsedIntent | None = None
        notes: list[str] = []
        if runtime.llm.enabled:
            try:
                payload = prompts.build_understand_user(
                    user_input,
                    history=history,
                    retrieved=retrieved,
                    devices=runtime.devices.snapshot(),
                    environment=runtime.simulator.environment,
                    scenes=runtime.db.load_scenes(),
                    last_devices=previous_devices,
                    pending=pending,
                )
                data = await runtime.llm.json_chat(prompts.UNDERSTAND_SYSTEM, payload)
                parsed = normalize_llm_result(
                    data,
                    registry=runtime.devices,
                    scenes=runtime.db.load_scenes(),
                    retrieved=retrieved,
                    user_input=user_input,
                )
                if parsed is None:
                    notes.append("模型结构化结果不完整，已使用本地解析")
            except LLMError as exc:
                notes.append("模型服务不可用，已切换本地意图解析")
                await ctx.emit("notice", level="warning", message=f"LLM 回退：{exc}")
        if parsed is None:
            parsed = nlu.parse(
                user_input,
                retrieved=retrieved,
                last_devices=previous_devices,
                pending=pending,
            )
            if notes:
                parsed.source = "rule-fallback"

        intent_dict = parsed.to_dict()
        # Reset per-run state and persist conversational context.
        last_devices = list(dict.fromkeys([*parsed.targets, *previous_devices]))[:8]
        await ctx.emit(
            "intent",
            intent=intent_dict,
            label=INTENT_TYPE_LABELS.get(parsed.intent_type, parsed.intent_type),
            notes=notes,
            latency_ms=latency,
        )
        summary = (
            f"{INTENT_TYPE_LABELS.get(parsed.intent_type, parsed.intent_type)}"
            f" · 置信度 {round(parsed.confidence * 100)}%"
        )
        if parsed.source in {"rule-fallback", "llm"}:
            summary += f" · {parsed.source}"
        await ctx.node_end(node, _ms(started), summary=summary)
        return {
            "retrieval": retrieved,
            "rag_latency_ms": latency,
            "intent": intent_dict,
            "last_devices": last_devices,
            "pending": parsed.pending,
            "tool_calls": [],
            "tool_results": [],
            "blocked_results": [],
            "verification": [],
            "scene_result": None,
            "response": "",
            "status": parsed.intent_type,
            "error": None,
        }

    def route_after_understand(state: AgentState) -> str:
        status = state.get("status")
        if status in {CONTROL, QUERY}:
            return "plan"
        if status == SCENE:
            return "scene"
        return "respond"

    # ------------------------------------------------------------------ plan
    async def plan(state: AgentState, config: RunnableConfig) -> AgentState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "plan"
        await ctx.node_start(node)
        intent = state["intent"]
        actions = intent.get("actions", [])
        calls: list[dict[str, Any]] = []
        source = "rule"

        if intent.get("intent_type") == CONTROL and intent.get("source") == "llm" and runtime.llm.enabled:
            try:
                tools = build_tool_schemas(runtime.devices.snapshot())
                llm_calls, text = await runtime.llm.tool_plan(
                    prompts.PLAN_SYSTEM,
                    prompts.build_plan_user(
                        state["user_input"], intent,
                        runtime.devices.snapshot(), runtime.db.load_scenes(),
                    ),
                    tools,
                )
                target_ids = set(intent.get("targets", []))
                filtered = []
                for call in llm_calls:
                    name = call.get("name", "")
                    args = call.get("args", {})
                    if name in CONTROL_TOOL_TYPES:
                        if args.get("device_id") not in target_ids:
                            continue
                    filtered.append(call)
                if filtered:
                    calls = filtered
                    source = "llm"
            except LLMError as exc:
                await ctx.emit("notice", level="warning", message=f"工具规划回退：{exc}")
        if not calls:
            calls = plan_from_actions(actions, runtime.devices)
            source = "rule"
        for index, call in enumerate(calls):
            call.setdefault("id", f"call_{index}")
            call.setdefault("source", source)
        await ctx.emit("plan", tool_calls=calls, source=source)
        await ctx.node_end(
            node, _ms(started),
            summary=f"生成 {len(calls)} 个工具调用",
        )
        return {"tool_calls": calls}

    # ----------------------------------------------------------------- guard
    async def guard(state: AgentState, config: RunnableConfig) -> AgentState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "guard"
        await ctx.node_start(node)
        normalized: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        warnings: list[str] = []
        for call in state.get("tool_calls", []):
            try:
                args, call_warnings = validate_call(
                    call.get("name", ""), call.get("args", {}) or {}, runtime.devices,
                )
                warnings.extend(call_warnings)
                normalized.append({**call, "args": args})
            except Exception as exc:
                message = getattr(exc, "message", str(exc))
                blocked_result = {
                    "ok": False,
                    "name": call.get("name"),
                    "args": call.get("args", {}),
                    "call_id": call.get("id"),
                    "message": message,
                    "error": getattr(exc, "to_dict", lambda: {"code": "BLOCKED", "message": message})(),
                    "data": {},
                    "duration_ms": 0.0,
                    "blocked": True,
                }
                blocked.append(blocked_result)
                await ctx.emit("tool_result", **blocked_result)
        if warnings:
            for warning in warnings:
                await ctx.emit("notice", level="warning", message=warning)
        await ctx.emit(
            "guard",
            passed=len(normalized),
            blocked=len(blocked),
            warnings=warnings,
            blocked_results=blocked,
        )
        if not normalized:
            error = "；".join(result["message"] for result in blocked) or "没有可执行的有效指令"
            await ctx.node_end(node, _ms(started), summary=f"拦截 {len(blocked)} 个无效调用")
            return {
                "tool_calls": [],
                "blocked_results": blocked,
                "error": error,
                "status": "blocked",
            }
        await ctx.node_end(
            node, _ms(started),
            summary=f"通过 {len(normalized)} 个调用" + (f"，拦截 {len(blocked)} 个" if blocked else ""),
        )
        return {"tool_calls": normalized, "blocked_results": blocked}

    def route_after_guard(state: AgentState) -> str:
        return "execute" if state.get("tool_calls") else "fallback"

    # --------------------------------------------------------------- execute
    async def execute(state: AgentState, config: RunnableConfig) -> AgentState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "execute"
        await ctx.node_start(node)
        results: list[dict[str, Any]] = list(state.get("blocked_results", []))
        for call in state.get("tool_calls", []):
            device_id = (call.get("args") or {}).get("device_id")
            label = _device_label(runtime, device_id)
            await ctx.emit(
                "tool_call",
                call_id=call.get("id"),
                name=call.get("name"),
                args=call.get("args", {}),
                label=label,
                source=call.get("source"),
            )
            await asyncio.sleep(0.14)
            result = runtime.tool_executor.execute(call)
            result["call_id"] = call.get("id")
            result["source"] = call.get("source")
            results.append(result)
            payload = {
                "call_id": call.get("id"),
                "name": result["name"],
                "ok": result["ok"],
                "message": result.get("message", ""),
                "args": call.get("args", {}),
                "duration_ms": result.get("duration_ms"),
            }
            if result.get("data", {}).get("device"):
                payload["device"] = result["data"]["device"]
            await ctx.emit("tool_result", **payload)
        success = sum(1 for result in results if result.get("ok"))
        failed = len(results) - success
        await ctx.node_end(
            node, _ms(started),
            summary=f"执行 {len(results)} 个动作，成功 {success}，失败 {failed}",
        )
        return {"tool_results": results}

    # ---------------------------------------------------------------- verify
    async def verify(state: AgentState, config: RunnableConfig) -> AgentState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "verify"
        await ctx.node_start(node)
        verification: list[dict[str, Any]] = []
        call_by_id = {call.get("id"): call for call in state.get("tool_calls", [])}
        for result in state.get("tool_results", []):
            if not result.get("ok") or result.get("blocked"):
                continue
            if str(result.get("name", "")).startswith("query_"):
                continue
            call = call_by_id.get(result.get("call_id"), {})
            args = dict(call.get("args") or {})
            args.pop("device_id", None)
            device = (result.get("data") or {}).get("device")
            if not device:
                continue
            mismatch = [
                key for key, expected in args.items()
                if device.get("properties", {}).get(key) != expected
            ]
            verification.append({
                "call_id": result.get("call_id"),
                "device_id": device.get("id"),
                "device_name": device.get("name"),
                "verified": not mismatch,
                "mismatch": mismatch,
            })
        mismatches = [item for item in verification if not item["verified"]]
        if mismatches:
            for item in mismatches:
                await ctx.emit(
                    "notice", level="warning",
                    message=f"{item['device_name']}状态校验存在偏差：{', '.join(item['mismatch'])}",
                )
        await ctx.emit("verification", items=verification, mismatches=len(mismatches))
        await ctx.node_end(
            node, _ms(started),
            summary=(
                f"校验 {len(verification)} 项设备状态"
                + (f"，{len(mismatches)} 项存在偏差" if mismatches else "，全部通过")
            ),
        )
        return {"verification": verification}

    # ----------------------------------------------------------------- scene
    async def scene(state: AgentState, config: RunnableConfig) -> AgentState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "scene"
        await ctx.node_start(node, scene_id=state["intent"].get("scene_id"))
        final_state = await runtime.scene_graph.ainvoke(
            {
                "scene_id": state["intent"].get("scene_id"),
                "index": 0,
                "results": [],
                "failures": [],
            },
            config=config,
        )
        scene_result = final_state.get("result")
        if not scene_result:
            scene_result = {
                "status": "failed",
                "message": "场景执行异常，未返回结果。",
                "results": [], "failures": [], "fallback_used": False,
                "condition": None,
            }
        await ctx.node_end(
            node, _ms(started),
            summary=f"「{scene_result.get('scene_name', '场景')}」{scene_result.get('status')}",
        )
        return {"scene_result": scene_result, "status": "scene_done"}

    # -------------------------------------------------------------- fallback
    async def fallback(state: AgentState, config: RunnableConfig) -> AgentState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "fallback"
        await ctx.node_start(node)
        error = state.get("error") or "执行链路未能完成"
        response = offline_response(state.get("intent", {}), state.get("tool_results", []), error=error)
        await ctx.emit("error", message=error, recoverable=True)
        await ctx.node_end(node, _ms(started), summary="已生成兜底回复")
        return {"response": response, "status": "fallback"}

    # --------------------------------------------------------------- respond
    async def respond(state: AgentState, config: RunnableConfig) -> AgentState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "respond"
        await ctx.node_start(node)
        intent = state.get("intent", {})
        scene_result = state.get("scene_result")
        text = ""
        used_llm = False

        # Scene results are deterministic and already user-facing.
        if scene_result:
            text = scene_result.get("message", "")
        elif state.get("response"):
            text = state["response"]
        elif intent.get("intent_type") == CLARIFY:
            text = offline_response(intent, state.get("tool_results", []))
        elif intent.get("intent_type") == CHAT and intent.get("direct_reply"):
            text = str(intent["direct_reply"])
        elif runtime.llm.enabled and intent.get("intent_type") != CLARIFY:
            try:
                history = state.get("history", [])[-6:]
                messages = [*history, {"role": "user", "content": state["user_input"]}]
                if intent.get("intent_type") == KNOWLEDGE:
                    knowledge_payload = prompts.build_knowledge_user(
                        state["user_input"], intent.get("knowledge", []),
                        runtime.simulator.environment,
                    )
                    messages = [{
                        "role": "user",
                        "content": f"{knowledge_payload}\n请回答用户的问题：{state['user_input']}",
                    }]
                    stream = runtime.llm.stream_text(prompts.KNOWLEDGE_SYSTEM, messages)
                elif intent.get("intent_type") == CHAT:
                    stream = runtime.llm.stream_text(prompts.CHAT_SYSTEM, messages)
                else:
                    messages = [{
                        "role": "user",
                        "content": prompts.build_respond_user(
                            state["user_input"], intent,
                            state.get("tool_results", []),
                            runtime.simulator.environment,
                            scene_result,
                        ),
                    }]
                    stream = runtime.llm.stream_text(prompts.RESPOND_SYSTEM, messages)
                chunks: list[str] = []
                async for chunk in stream:
                    chunks.append(chunk)
                    await ctx.emit("token", content=chunk)
                text = "".join(chunks).strip()
                used_llm = bool(text)
                if not text:
                    text = offline_response(
                        intent, state.get("tool_results", []),
                        scene_result=scene_result,
                        environment=runtime.simulator.environment,
                    )
            except LLMError as exc:
                await ctx.emit("notice", level="warning", message=f"回复生成回退：{exc}")
                text = offline_response(
                    intent, state.get("tool_results", []),
                    scene_result=scene_result,
                    environment=runtime.simulator.environment,
                )
            except Exception as exc:  # pragma: no cover
                await ctx.emit("notice", level="warning", message=f"回复生成异常：{exc}")
                text = offline_response(
                    intent, state.get("tool_results", []),
                    scene_result=scene_result,
                    environment=runtime.simulator.environment,
                )

        if not text:
            text = offline_response(
                intent,
                state.get("tool_results", []),
                scene_result=scene_result,
                environment=runtime.simulator.environment,
                error=state.get("error"),
            )

        if not used_llm:
            await _emit_text(ctx, text)
        await ctx.emit("response", content=text)
        await ctx.node_end(
            node, _ms(started),
            summary=("模型生成" if used_llm else "本地生成") + f" · {len(text)} 字",
        )
        return {"response": text, "status": "responded"}

    graph = StateGraph(AgentState)
    graph.add_node("understand", understand)
    graph.add_node("plan", plan)
    graph.add_node("guard", guard)
    graph.add_node("execute", execute)
    graph.add_node("verify", verify)
    graph.add_node("scene", scene)
    graph.add_node("fallback", fallback)
    graph.add_node("respond", respond)

    graph.add_edge(START, "understand")
    graph.add_conditional_edges(
        "understand",
        route_after_understand,
        {"plan": "plan", "scene": "scene", "respond": "respond"},
    )
    graph.add_edge("plan", "guard")
    graph.add_conditional_edges(
        "guard", route_after_guard, {"execute": "execute", "fallback": "fallback"}
    )
    graph.add_edge("execute", "verify")
    graph.add_edge("verify", "respond")
    graph.add_edge("scene", "respond")
    graph.add_edge("fallback", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=runtime.memory)
