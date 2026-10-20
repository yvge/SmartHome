"""Scene condition evaluation (time / sensor thresholds)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.devices.registry import DeviceError, DeviceRegistry

OP_LABELS = {
    ">": "大于", ">=": "不低于", "<": "小于", "<=": "不高于",
    "==": "等于", "!=": "不等于", "between": "处于",
}


def _to_minutes(value: str) -> int:
    hours, minutes = value.split(":")[:2]
    return int(hours) * 60 + int(minutes)


def _compare(actual: Any, op: str, expected: Any) -> bool:
    try:
        if op in {">", ">=", "<", "<=", "==", "!="}:
            actual_num = float(actual)
            expected_num = float(expected)
            return {
                ">": actual_num > expected_num,
                ">=": actual_num >= expected_num,
                "<": actual_num < expected_num,
                "<=": actual_num <= expected_num,
                "==": actual_num == expected_num,
                "!=": actual_num != expected_num,
            }[op]
        if op == "between":
            low, high = expected
            return float(low) <= float(actual) <= float(high)
    except (TypeError, ValueError):
        return False
    return False


def evaluate(condition: dict[str, Any] | None, registry: DeviceRegistry, simulator) -> dict[str, Any]:
    if not condition:
        return {"passed": True, "reason": "未设置条件，直接执行", "condition": None}
    condition_type = condition.get("type")
    now = datetime.now()

    if condition_type == "time":
        raw_value = condition.get("value") or []
        if len(raw_value) != 2:
            return {"passed": False, "reason": "时间条件配置不完整", "condition": condition}
        start, end = _to_minutes(str(raw_value[0])), _to_minutes(str(raw_value[1]))
        current = now.hour * 60 + now.minute
        if start <= end:
            passed = start <= current <= end
        else:  # overnight range, e.g. 21:00 -> 06:00
            passed = current >= start or current <= end
        return {
            "passed": passed,
            "reason": (
                f"当前 {now.strftime('%H:%M')} "
                f"{'处于' if passed else '不在'} {raw_value[0]}–{raw_value[1]} 时段内"
            ),
            "condition": condition,
            "actual": now.strftime("%H:%M"),
        }

    if condition_type == "temperature":
        room_id = condition.get("room")
        if room_id:
            room = simulator.room(room_id)
            actual = room["temperature"] if room else simulator.environment["indoor_temp"]
        else:
            actual = simulator.environment["indoor_temp"]
        op = str(condition.get("op", ">="))
        expected = condition.get("value")
        passed = _compare(actual, op, expected)
        return {
            "passed": passed,
            "reason": f"当前温度 {actual}°C {OP_LABELS.get(op, op)} {expected}°C，条件{'成立' if passed else '不成立'}",
            "condition": condition,
            "actual": actual,
        }

    if condition_type == "humidity":
        actual = simulator.environment["humidity"]
        op = str(condition.get("op", ">="))
        expected = condition.get("value")
        passed = _compare(actual, op, expected)
        return {
            "passed": passed,
            "reason": f"当前湿度 {actual}% {OP_LABELS.get(op, op)} {expected}%，条件{'成立' if passed else '不成立'}",
            "condition": condition,
            "actual": actual,
        }

    if condition_type == "device_property" or condition.get("device_id"):
        device_id = condition.get("device_id")
        prop = condition.get("property", "power")
        op = str(condition.get("op", "=="))
        expected = condition.get("value")
        try:
            device = registry.get(device_id)
        except DeviceError:
            return {"passed": False, "reason": f"条件设备 {device_id} 不存在", "condition": condition}
        actual = device["properties"].get(prop)
        if isinstance(actual, bool) and isinstance(expected, str):
            expected = expected.lower() in {"true", "1", "on", "开"}
        passed = _compare(actual, op, expected) if not isinstance(actual, bool) else actual == expected
        return {
            "passed": passed,
            "reason": (
                f"{device['name']}的{prop}当前为 {actual}，"
                f"条件{'成立' if passed else '不成立'}"
            ),
            "condition": condition,
            "actual": actual,
        }

    return {"passed": True, "reason": "未知条件类型，按通过处理", "condition": condition}
