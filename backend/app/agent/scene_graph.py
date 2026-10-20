"""LangGraph subgraph for multi-step scene orchestration.

Flow:
    load -> conditions -> plan -> execute (loop per device action)
         -> fallback (on critical failure) -> verify -> END

The loop over device steps demonstrates dynamic paths: conditions can skip
the whole scene or individual steps, and a critical failure diverts execution
to a best-effort fallback branch before verification.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agent.conditions import evaluate
from app.agent.events import RunContext
from app.agent.responder import build_scene_result
from app.devices.registry import DeviceError


class SceneState(TypedDict, total=False):
    scene_id: str
    scene: dict[str, Any]
    scene_name: str
    condition: dict[str, Any] | None
    condition_result: dict[str, Any] | None
    plan: list[dict[str, Any]]
    skipped_steps: list[dict[str, Any]]
    index: int
    results: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    need_fallback: bool
    fallback_used: bool
    fallback_results: list[dict[str, Any]]
    verification: list[dict[str, Any]]
    status: str
    result: dict[str, Any] | None
    response: str
    error: str | None


def _ctx(config: RunnableConfig) -> RunContext:
    return config["configurable"]["ctx"]


def build_scene_graph(runtime) -> Any:
    async def scene_load(state: SceneState, config: RunnableConfig) -> SceneState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "scene_load"
        await ctx.node_start(node, scene_id=state.get("scene_id"))
        scene = runtime.db.get_scene(state.get("scene_id", ""))
        if not scene or not scene.get("enabled", True):
            message = "这个场景不存在或已被停用。"
            result = {
                "scene_id": state.get("scene_id"),
                "scene_name": "未知场景",
                "status": "failed",
                "message": message,
                "results": [],
                "failures": [{"label": "加载场景", "message": message}],
                "fallback_used": False,
                "fallback_results": [],
                "condition": None,
            }
            await ctx.emit("error", message=message)
            await ctx.emit("scene_done", result=result)
            await ctx.node_end(node, (time.perf_counter() - started) * 1000, summary=message)
            return {"status": "failed", "result": result, "response": message, "error": message}
        await ctx.emit(
            "scene_start",
            scene_id=scene["id"],
            name=scene["name"],
            icon=scene.get("icon", "sparkles"),
            description=scene.get("description", ""),
            total_steps=len(scene.get("steps", [])),
        )
        await ctx.node_end(
            node, (time.perf_counter() - started) * 1000,
            summary=f"加载「{scene['name']}」，共 {len(scene.get('steps', []))} 个动作",
        )
        return {
            "scene": scene,
            "scene_name": scene["name"],
            "condition": scene.get("condition"),
            "plan": [],
            "skipped_steps": [],
            "index": 0,
            "results": [],
            "failures": [],
            "need_fallback": False,
            "fallback_used": False,
            "fallback_results": [],
            "verification": [],
            "status": "running",
            "result": None,
            "response": "",
            "error": None,
        }

    async def scene_conditions(state: SceneState, config: RunnableConfig) -> SceneState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "scene_conditions"
        await ctx.node_start(node)
        condition = state.get("condition")
        evaluation = evaluate(condition, runtime.devices, runtime.simulator)
        optional = bool((condition or {}).get("optional", False))
        await ctx.emit(
            "scene_condition",
            condition=condition,
            passed=evaluation["passed"],
            reason=evaluation["reason"],
            optional=optional,
            actual=evaluation.get("actual"),
        )
        scene = state["scene"]
        if not evaluation["passed"] and not optional:
            result = build_scene_result(
                scene, results=[], failures=[], fallback_used=False,
                fallback_results=[], condition=evaluation,
                skipped_reason=evaluation["reason"],
            )
            await ctx.emit("scene_done", result=result)
            await ctx.node_end(
                node, (time.perf_counter() - started) * 1000,
                summary="条件不满足，跳过场景",
            )
            return {
                "condition_result": evaluation,
                "status": "skipped",
                "result": result,
                "response": result["message"],
            }
        note = evaluation["reason"]
        if not evaluation["passed"] and optional:
            note += "（可选条件，继续执行）"
        await ctx.node_end(
            node, (time.perf_counter() - started) * 1000, summary=note,
        )
        return {"condition_result": evaluation}

    async def scene_plan(state: SceneState, config: RunnableConfig) -> SceneState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "scene_plan"
        await ctx.node_start(node)
        plan: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for index, step in enumerate(state["scene"].get("steps", [])):
            when = step.get("when")
            if when:
                evaluation = evaluate(when, runtime.devices, runtime.simulator)
                if not evaluation["passed"]:
                    skipped.append({
                        "index": index,
                        "label": step.get("label", "条件动作"),
                        "reason": evaluation["reason"],
                    })
                    await ctx.emit(
                        "scene_step_skipped",
                        index=index + 1,
                        label=step.get("label", "条件动作"),
                        reason=evaluation["reason"],
                    )
                    continue
            try:
                device = runtime.devices.get(step["device_id"])
                device_name = device["name"]
                online = device["online"]
            except DeviceError:
                device_name = step["device_id"]
                online = False
            plan.append({
                "index": index,
                "device_id": step["device_id"],
                "device_name": device_name,
                "params": dict(step.get("params") or {}),
                "label": step.get("label") or f"控制{device_name}",
                "critical": bool(step.get("critical", False)),
                "delay_ms": int(step.get("delay_ms", 150)),
                "online": online,
            })
        await ctx.node_end(
            node, (time.perf_counter() - started) * 1000,
            summary=f"编排 {len(plan)} 个动作" + (f"，跳过 {len(skipped)} 个条件动作" if skipped else ""),
        )
        return {"plan": plan, "skipped_steps": skipped}

    async def scene_execute(state: SceneState, config: RunnableConfig) -> SceneState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "scene_execute"
        plan = state.get("plan", [])
        index = int(state.get("index", 0))
        step = plan[index]
        results = list(state.get("results", []))
        failures = list(state.get("failures", []))
        await ctx.node_start(
            node, step_index=index + 1, total=len(plan),
            step_label=step["label"],
        )
        await ctx.emit(
            "scene_step",
            index=index + 1,
            total=len(plan),
            label=step["label"],
            device_id=step["device_id"],
            device_name=step["device_name"],
            params=step["params"],
        )
        await asyncio.sleep(min(step.get("delay_ms", 150), 450) / 1000 + 0.08)
        try:
            device = runtime.devices.apply(step["device_id"], step["params"])
            result = {
                "index": index + 1,
                "label": step["label"],
                "device_id": step["device_id"],
                "device_name": step["device_name"],
                "ok": True,
                "message": f"{step['label']}已完成",
                "device": device,
            }
            results.append(result)
            await ctx.emit("scene_step_result", **result)
            summary = f"{step['label']} ✓"
        except DeviceError as exc:
            failure = {
                "index": index + 1,
                "label": step["label"],
                "device_id": step["device_id"],
                "device_name": step["device_name"],
                "ok": False,
                "message": exc.message,
                "code": exc.code,
                "critical": step["critical"],
            }
            failures.append(failure)
            await ctx.emit("scene_step_result", **failure)
            summary = f"{step['label']} 失败：{exc.message}"
        except Exception as exc:  # pragma: no cover
            failure = {
                "index": index + 1,
                "label": step["label"],
                "device_id": step["device_id"],
                "device_name": step["device_name"],
                "ok": False,
                "message": str(exc),
                "code": "INTERNAL",
                "critical": step["critical"],
            }
            failures.append(failure)
            await ctx.emit("scene_step_result", **failure)
            summary = f"{step['label']} 失败：{exc}"
        need_fallback = bool(
            failures and failures[-1].get("ok") is False and failures[-1].get("critical")
        )
        await ctx.node_end(
            node, (time.perf_counter() - started) * 1000,
            summary=summary, step_index=index + 1, total=len(plan),
        )
        return {
            "index": index + 1,
            "results": results,
            "failures": failures,
            "need_fallback": need_fallback,
        }

    async def scene_fallback(state: SceneState, config: RunnableConfig) -> SceneState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "scene_fallback"
        await ctx.node_start(node)
        actions = state["scene"].get("fallback") or []
        fallback_results: list[dict[str, Any]] = []
        for action in actions:
            label = action.get("label") or "兜底动作"
            try:
                device = runtime.devices.apply(action["device_id"], action.get("params", {}))
                fallback_results.append({
                    "label": label, "ok": True, "device_id": action["device_id"],
                    "message": f"{label}已执行", "device": device,
                })
            except DeviceError as exc:
                fallback_results.append({
                    "label": label, "ok": False, "device_id": action.get("device_id"),
                    "message": exc.message,
                })
            await asyncio.sleep(0.12)
        await ctx.emit(
            "scene_fallback",
            actions=actions,
            results=fallback_results,
            success=all(result["ok"] for result in fallback_results) if fallback_results else False,
        )
        await ctx.node_end(
            node, (time.perf_counter() - started) * 1000,
            summary=f"执行 {len(fallback_results)} 个兜底动作",
        )
        return {"fallback_used": True, "fallback_results": fallback_results, "need_fallback": False}

    async def scene_verify(state: SceneState, config: RunnableConfig) -> SceneState:
        ctx = _ctx(config)
        started = time.perf_counter()
        node = "scene_verify"
        await ctx.node_start(node)
        verification: list[dict[str, Any]] = []
        for result in state.get("results", []):
            if not result.get("ok"):
                continue
            step = next(
                (item for item in state.get("plan", []) if item["index"] + 1 == result["index"]),
                None,
            )
            if not step:
                continue
            try:
                device = runtime.devices.get(step["device_id"])
                mismatch = [
                    key for key, value in step["params"].items()
                    if device["properties"].get(key) != value
                ]
                verification.append({
                    "label": step["label"],
                    "device_id": step["device_id"],
                    "verified": not mismatch,
                    "mismatch": mismatch,
                })
            except DeviceError:
                verification.append({
                    "label": step["label"], "device_id": step["device_id"],
                    "verified": False, "mismatch": ["device_missing"],
                })
        mismatches = [item for item in verification if not item["verified"]]
        failures = list(state.get("failures", []))
        failures.extend({
            "label": item["label"], "device_id": item["device_id"],
            "ok": False, "message": "状态校验未通过",
            "code": "VERIFY_FAILED", "critical": False,
        } for item in mismatches)
        scene = state["scene"]
        result = build_scene_result(
            scene,
            results=state.get("results", []),
            failures=failures,
            fallback_used=state.get("fallback_used", False),
            fallback_results=state.get("fallback_results", []),
            condition=state.get("condition_result"),
        )
        result["verification"] = verification
        result["skipped_steps"] = state.get("skipped_steps", [])
        await ctx.emit("scene_verify", verification=verification, status=result["status"])
        await ctx.emit("scene_done", result=result)
        await ctx.node_end(
            node, (time.perf_counter() - started) * 1000,
            summary=f"校验 {len(verification)} 个动作，{len(mismatches)} 个未通过",
        )
        return {"verification": verification, "failures": failures, "status": result["status"],
                "result": result, "response": result["message"]}

    def route_after_load(state: SceneState) -> str:
        return "end" if state.get("status") == "failed" else "conditions"

    def route_after_conditions(state: SceneState) -> str:
        return "end" if state.get("status") == "skipped" else "plan"

    def route_after_plan(state: SceneState) -> str:
        return "execute" if state.get("plan") else "verify"

    def route_after_execute(state: SceneState) -> str:
        if state.get("need_fallback"):
            return "fallback"
        if int(state.get("index", 0)) < len(state.get("plan", [])):
            return "execute"
        return "verify"

    graph = StateGraph(SceneState)
    graph.add_node("load", scene_load)
    graph.add_node("conditions", scene_conditions)
    graph.add_node("plan", scene_plan)
    graph.add_node("execute", scene_execute)
    graph.add_node("fallback", scene_fallback)
    graph.add_node("verify", scene_verify)

    graph.add_edge(START, "load")
    graph.add_conditional_edges("load", route_after_load, {"end": END, "conditions": "conditions"})
    graph.add_conditional_edges(
        "conditions", route_after_conditions, {"end": END, "plan": "plan"}
    )
    graph.add_conditional_edges(
        "plan", route_after_plan, {"execute": "execute", "verify": "verify"}
    )
    graph.add_conditional_edges(
        "execute",
        route_after_execute,
        {"execute": "execute", "fallback": "fallback", "verify": "verify"},
    )
    graph.add_edge("fallback", "verify")
    graph.add_edge("verify", END)
    return graph.compile()
