"""Scene CRUD validation and conversion."""
from __future__ import annotations

from typing import Any

from app.agent.tools import TOOL_FOR_TYPE, validate_call
from app.db import new_id, now_iso
from app.devices.registry import DeviceError, humanize_params
from app.runtime import AppRuntime
from app.schemas import ScenePayload


class SceneValidationError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


CONDITION_TYPES = {"time", "temperature", "humidity", "device_property"}
VALID_OPS = {">", ">=", "<", "<=", "==", "!=", "between"}


def validate_condition(condition: dict[str, Any] | None, runtime: AppRuntime) -> dict[str, Any] | None:
    if condition is None:
        return None
    if not isinstance(condition, dict):
        raise SceneValidationError("条件必须是 JSON 对象")
    condition = dict(condition)
    ctype = condition.get("type", "device_property")
    if ctype not in CONDITION_TYPES:
        raise SceneValidationError(f"不支持的条件类型：{ctype}")
    condition["type"] = ctype
    if ctype == "time":
        value = condition.get("value")
        if not (isinstance(value, list) and len(value) == 2):
            raise SceneValidationError("时间条件需要 [开始, 结束]，例如 [\"18:00\", \"23:00\"]")
        for item in value:
            try:
                hours, minutes = str(item).split(":")[:2]
                if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                    raise ValueError
            except Exception as exc:
                raise SceneValidationError(f"时间格式不正确：{item}") from exc
        condition["optional"] = bool(condition.get("optional", False))
        return condition
    if ctype in {"temperature", "humidity"}:
        try:
            float(condition.get("value"))
        except (TypeError, ValueError) as exc:
            raise SceneValidationError("阈值必须是数字") from exc
        condition["op"] = str(condition.get("op", ">="))
        if condition["op"] not in VALID_OPS - {"between"}:
            raise SceneValidationError("不支持的比较运算符")
        condition["optional"] = bool(condition.get("optional", False))
        return condition

    device_id = condition.get("device_id")
    try:
        device = runtime.devices.get(str(device_id))
    except DeviceError as exc:
        raise SceneValidationError(f"条件设备不存在：{device_id}") from exc
    prop = condition.get("property")
    if not prop or prop not in device["properties"]:
        raise SceneValidationError(f"{device['name']}没有属性 {prop}")
    condition["op"] = str(condition.get("op", "=="))
    if condition["op"] not in VALID_OPS | {"between"}:
        raise SceneValidationError("不支持的比较运算符")
    condition["optional"] = bool(condition.get("optional", False))
    return condition


def build_steps(raw_steps: list[Any], runtime: AppRuntime, *, fallback: bool = False) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise SceneValidationError(f"第 {index + 1} 个动作格式不正确")
        device_id = str(raw.get("device_id", ""))
        try:
            device = runtime.devices.get(device_id)
        except DeviceError as exc:
            raise SceneValidationError(f"第 {index + 1} 个动作的设备不存在：{device_id}") from exc
        tool = TOOL_FOR_TYPE.get(device["type"])
        if not tool:
            raise SceneValidationError(f"{device['name']}不支持场景控制")
        params = raw.get("params") or {}
        if not isinstance(params, dict):
            raise SceneValidationError(f"第 {index + 1} 个动作的参数格式不正确")
        try:
            normalized, _ = validate_call(tool, {"device_id": device_id, **params}, runtime.devices)
        except DeviceError as exc:
            raise SceneValidationError(f"第 {index + 1} 个动作无效：{exc.message}") from exc
        normalized.pop("device_id", None)
        label = raw.get("label") or f"{device['name']} · {humanize_params(device, normalized)}"
        step: dict[str, Any] = {
            "device_id": device_id,
            "params": normalized,
            "label": str(label)[:80],
            "delay_ms": max(0, min(2000, int(raw.get("delay_ms", 200)))),
            "critical": bool(raw.get("critical", False)),
        }
        when = raw.get("when")
        if when:
            validated_when = validate_condition(when, runtime)
            if validated_when and validated_when.get("type") == "time":
                raise SceneValidationError("单个动作暂不支持时间条件，请使用设备属性或温湿度条件")
            step["when"] = validated_when
        steps.append(step)
    return steps


def create_scene(runtime: AppRuntime, payload: ScenePayload) -> dict[str, Any]:
    condition = validate_condition(payload.condition, runtime)
    steps = build_steps([step.model_dump() for step in payload.steps], runtime)
    fallback = build_steps([step.model_dump() for step in payload.fallback], runtime, fallback=True)
    now = now_iso()
    scene = {
        "id": new_id("scene_custom_"),
        "name": payload.name,
        "icon": payload.icon or "sparkles",
        "description": payload.description,
        "condition": condition,
        "steps": steps,
        "fallback": fallback,
        "builtin": False,
        "enabled": True,
        "created_at": now,
    }
    runtime.db.save_scene(scene)
    runtime.reload_scene_catalog()
    return runtime.db.get_scene(scene["id"]) or scene


def update_scene(runtime: AppRuntime, scene_id: str, payload: ScenePayload) -> dict[str, Any]:
    existing = runtime.db.get_scene(scene_id)
    if not existing:
        raise SceneValidationError("场景不存在")
    if existing.get("builtin"):
        raise SceneValidationError("内置场景不可修改，可以复制一份再编辑")
    condition = validate_condition(payload.condition, runtime)
    steps = build_steps([step.model_dump() for step in payload.steps], runtime)
    fallback = build_steps([step.model_dump() for step in payload.fallback], runtime, fallback=True)
    scene = {
        **existing,
        "name": payload.name,
        "icon": payload.icon or existing.get("icon", "sparkles"),
        "description": payload.description,
        "condition": condition,
        "steps": steps,
        "fallback": fallback,
        "updated_at": now_iso(),
    }
    runtime.db.save_scene(scene)
    runtime.reload_scene_catalog()
    return runtime.db.get_scene(scene_id) or scene


def duplicate_scene(runtime: AppRuntime, scene_id: str) -> dict[str, Any]:
    existing = runtime.db.get_scene(scene_id)
    if not existing:
        raise SceneValidationError("场景不存在")
    now = now_iso()
    scene = {
        **existing,
        "id": new_id("scene_custom_"),
        "name": f"{existing['name']} 副本"[:30],
        "builtin": False,
        "enabled": True,
        "created_at": now,
        "updated_at": now,
    }
    runtime.db.save_scene(scene)
    runtime.reload_scene_catalog()
    return runtime.db.get_scene(scene["id"]) or scene


def delete_scene(runtime: AppRuntime, scene_id: str) -> None:
    existing = runtime.db.get_scene(scene_id)
    if not existing:
        raise SceneValidationError("场景不存在")
    if existing.get("builtin"):
        raise SceneValidationError("内置场景不可删除")
    if not runtime.db.delete_scene(scene_id):
        raise SceneValidationError("场景删除失败")
    runtime.reload_scene_catalog()
