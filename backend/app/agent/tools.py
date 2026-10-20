"""Function-Calling tool schemas + the execution layer.

Heterogeneous devices are exposed as typed JSON-Schema tools. The same tools
are used by the LLM planner and by the deterministic offline planner, so the
execution path is identical in both modes.
"""
from __future__ import annotations

import copy
import time
from typing import Any

from app.devices.registry import DeviceError, DeviceRegistry, humanize_params
from app.devices.specs import ROOM_IDS

TOOL_FOR_TYPE = {
    "light": "control_light",
    "ac": "control_ac",
    "curtain": "control_curtain",
    "purifier": "control_purifier",
    "humidifier": "control_humidifier",
    "socket": "control_socket",
    "speaker": "control_speaker",
    "vacuum": "control_vacuum",
}

CONTROL_TOOL_TYPES = {tool: device_type for device_type, tool in TOOL_FOR_TYPE.items()}

DEVICE_ID_PROP = {
    "type": "string",
    "description": "目标设备 id，必须来自设备目录",
}

BASE_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "control_light",
            "description": "控制灯具：开关、亮度（1-100）、色温（2700-6500K）",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROP,
                    "power": {"type": "boolean", "description": "true 开灯，false 关灯"},
                    "brightness": {"type": "integer", "minimum": 1, "maximum": 100},
                    "color_temp": {"type": "integer", "minimum": 2700, "maximum": 6500},
                },
                "required": ["device_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_ac",
            "description": "控制空调：开关、目标温度（16-30°C）、模式、风速",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROP,
                    "power": {"type": "boolean"},
                    "target_temp": {"type": "integer", "minimum": 16, "maximum": 30},
                    "mode": {
                        "type": "string",
                        "enum": ["cool", "heat", "dry", "fan", "auto"],
                    },
                    "fan_speed": {
                        "type": "string",
                        "enum": ["auto", "low", "medium", "high"],
                    },
                },
                "required": ["device_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_curtain",
            "description": "控制窗帘开合度：0 为完全闭合，100 为完全打开",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROP,
                    "position": {"type": "integer", "minimum": 0, "maximum": 100},
                },
                "required": ["device_id", "position"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_purifier",
            "description": "控制空气净化器：开关与模式",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROP,
                    "power": {"type": "boolean"},
                    "mode": {"type": "string", "enum": ["auto", "sleep", "high"]},
                },
                "required": ["device_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_humidifier",
            "description": "控制加湿器：开关与目标湿度（30-80%）",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROP,
                    "power": {"type": "boolean"},
                    "target_humidity": {"type": "integer", "minimum": 30, "maximum": 80},
                },
                "required": ["device_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_socket",
            "description": "控制智能插座通断电",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROP,
                    "power": {"type": "boolean"},
                },
                "required": ["device_id", "power"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_speaker",
            "description": "控制智能音箱：开关、音量、播放状态与内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROP,
                    "power": {"type": "boolean"},
                    "volume": {"type": "integer", "minimum": 0, "maximum": 100},
                    "playing": {"type": "boolean"},
                    "track": {
                        "type": "string",
                        "enum": ["晨间新闻", "轻音乐", "白噪音", "入睡冥想"],
                    },
                },
                "required": ["device_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_vacuum",
            "description": "控制扫地机器人：启动/停止清扫与清扫模式",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": DEVICE_ID_PROP,
                    "power": {"type": "boolean"},
                    "mode": {"type": "string", "enum": ["auto", "spot", "edge", "mop"]},
                },
                "required": ["device_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_device",
            "description": "查询一个或多个设备的状态。不传 device_id 时查询全屋设备。",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "可选，目标设备 id"},
                    "room": {
                        "type": "string",
                        "enum": list(ROOM_IDS.values()),
                        "description": "可选，按房间过滤",
                    },
                    "device_type": {"type": "string", "description": "可选，按设备类型过滤"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_environment",
            "description": "查询室内环境：温度、湿度、PM2.5、CO2、光照与能耗",
            "parameters": {
                "type": "object",
                "properties": {
                    "room": {
                        "type": "string",
                        "enum": list(ROOM_IDS.values()),
                        "description": "可选，指定房间",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
]


def build_tool_schemas(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Inject concrete device ids into JSON Schema enums."""
    schemas = copy.deepcopy(BASE_TOOL_SCHEMAS)
    ids_by_type: dict[str, list[str]] = {}
    for device in devices:
        ids_by_type.setdefault(device["type"], []).append(device["id"])
    for schema in schemas:
        function = schema["function"]
        if function["name"] in CONTROL_TOOL_TYPES:
            device_type = CONTROL_TOOL_TYPES[function["name"]]
            prop = function["parameters"]["properties"]["device_id"]
            prop["enum"] = ids_by_type.get(device_type, [])
            prop["description"] = (
                f"目标{device_type}设备 id，只能从以下选择："
                + "、".join(ids_by_type.get(device_type, []))
            )
    return schemas


def plan_from_actions(
    actions: list[dict[str, Any]], registry: DeviceRegistry,
) -> list[dict[str, Any]]:
    """Deterministic action -> tool-call conversion (offline planner)."""
    calls: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        intent = action.get("intent", "")
        device_ids = action.get("device_ids") or []
        params = dict(action.get("params") or {})
        if intent == "query_environment":
            args = {key: value for key, value in params.items() if key == "room"}
            calls.append({
                "id": f"call_{index}", "name": "query_environment",
                "args": args, "source": "rule",
            })
            continue
        if intent in {"query_device", "query_status"}:
            args: dict[str, Any] = {}
            if "room" in params:
                args["room"] = params["room"]
            if "device_type" in params:
                args["device_type"] = params["device_type"]
            if intent == "query_device" and len(device_ids) == 1:
                args["device_id"] = device_ids[0]
            calls.append({
                "id": f"call_{index}", "name": "query_device",
                "args": args, "source": "rule",
            })
            continue
        for device_id in device_ids:
            try:
                device = registry.get(device_id)
            except DeviceError:
                continue
            tool = TOOL_FOR_TYPE.get(device["type"])
            if not tool:
                continue
            calls.append({
                "id": f"call_{index}_{device_id}",
                "name": tool,
                "args": {"device_id": device_id, **params},
                "source": "rule",
                "device_id": device_id,
            })
    return calls


def validate_call(
    name: str, args: dict[str, Any], registry: DeviceRegistry,
) -> tuple[dict[str, Any], list[str]]:
    """Static validation/clamping. Returns (normalized args, warnings)."""
    warnings: list[str] = []
    if name in CONTROL_TOOL_TYPES:
        required_type = CONTROL_TOOL_TYPES[name]
        device_id = args.get("device_id")
        if not device_id:
            raise DeviceError("INVALID_PARAM", f"{name} 缺少 device_id")
        device = registry.get(device_id)
        if device["type"] != required_type:
            raise DeviceError(
                "INVALID_PARAM",
                f"{name} 不能控制类型为 {device['type']} 的设备 {device['name']}",
                device_id,
            )
        if not device["online"]:
            raise DeviceError("OFFLINE", f"{device['name']}当前处于离线状态", device_id)
        params = {k: v for k, v in args.items() if k != "device_id"}
        if not params:
            raise DeviceError("EMPTY_COMMAND", f"{device['name']}没有收到可执行参数", device_id)
        normalized = {"device_id": device_id}
        writable = {cap["key"]: cap for cap in device["capabilities"]}
        for key, value in params.items():
            if key not in writable:
                raise DeviceError(
                    "INVALID_PARAM", f"{device['name']}不支持参数 {key}", device_id
                )
            cap = writable[key]
            if cap.get("type") == "range":
                try:
                    number = int(round(float(value)))
                except (TypeError, ValueError) as exc:
                    raise DeviceError(
                        "INVALID_VALUE", f"{cap.get('label', key)} 需要数字", device_id
                    ) from exc
                clamped = max(cap["min"], min(cap["max"], number))
                if clamped != number:
                    warnings.append(
                        f"{device['name']}的{cap['label']}已调整到允许范围 {clamped}{cap.get('unit', '')}"
                    )
                normalized[key] = clamped
            elif cap.get("type") == "enum":
                allowed = [option["value"] for option in cap.get("options", [])]
                if value not in allowed:
                    raise DeviceError(
                        "INVALID_VALUE",
                        f"{device['name']}的{cap.get('label', key)}不支持 {value}",
                        device_id,
                    )
                normalized[key] = value
            else:
                normalized[key] = value
        return normalized, warnings
    if name == "query_device":
        room = args.get("room")
        if room:
            room = ROOM_IDS.get(room, room)
            if room not in ROOM_IDS.values():
                raise DeviceError("INVALID_PARAM", f"未知房间 {room}")
        return {**args, "room": room} if room else dict(args), warnings
    if name == "query_environment":
        room = args.get("room")
        if room:
            room = ROOM_IDS.get(room, room)
            if room not in ROOM_IDS.values():
                raise DeviceError("INVALID_PARAM", f"未知房间 {room}")
        return {**args, "room": room} if room else dict(args), warnings
    raise DeviceError("UNKNOWN_TOOL", f"未知工具 {name}")


def _device_state_text(device: dict[str, Any]) -> str:
    props = device["properties"]
    dtype = device["type"]
    if dtype == "light":
        return (
            f"{'开' if props.get('power') else '关'}"
            + (f"，亮度{props.get('brightness')}%，色温{props.get('color_temp')}K" if props.get("power") else "")
        )
    if dtype == "ac":
        if not props.get("power"):
            return "关闭"
        modes = {"cool": "制冷", "heat": "制热", "dry": "除湿", "fan": "送风", "auto": "自动"}
        return f"{props.get('target_temp')}°C，{modes.get(props.get('mode'), props.get('mode'))}模式"
    if dtype == "curtain":
        return f"开合度{props.get('position')}%"
    if dtype == "purifier":
        state = "运行中" if props.get("power") else "关闭"
        return f"{state}，PM2.5 {props.get('pm25')} μg/m³"
    if dtype == "humidifier":
        return (
            f"运行中，目标湿度{props.get('target_humidity')}%"
            if props.get("power") else "关闭"
        )
    if dtype == "socket":
        return "通电" if props.get("power") else "断电"
    if dtype == "speaker":
        return "播放中" if props.get("playing") else ("待机" if props.get("power") else "关闭")
    if dtype == "vacuum":
        return "清扫中" if props.get("power") else "在充电座"
    if dtype == "sensor":
        return f"{props.get('temperature')}°C，湿度{props.get('humidity')}%"
    return "在线"


class ToolExecutor:
    def __init__(self, registry: DeviceRegistry, simulator) -> None:
        self.registry = registry
        self.simulator = simulator

    def execute(self, call: dict[str, Any]) -> dict[str, Any]:
        name = call.get("name", "")
        args = call.get("args", {}) or {}
        started = time.perf_counter()
        try:
            normalized, warnings = validate_call(name, args, self.registry)
            if name in CONTROL_TOOL_TYPES:
                device_id = normalized.pop("device_id")
                before = self.registry.get(device_id)
                device = self.registry.apply(device_id, normalized)
                action_text = humanize_params(device, normalized)
                message = f"已{action_text}——{device['name']}"
                data = {"device": device, "before": before}
            elif name == "query_environment":
                data = self._environment_payload(normalized.get("room"))
                message = data.pop("message")
            elif name == "query_device":
                data = self._devices_payload(normalized)
                message = data.pop("message")
            else:
                raise DeviceError("UNKNOWN_TOOL", f"未知工具 {name}")
            return {
                "ok": True,
                "name": name,
                "args": args,
                "message": message,
                "warnings": warnings,
                "data": data,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        except DeviceError as exc:
            return {
                "ok": False,
                "name": name,
                "args": args,
                "message": exc.message,
                "error": exc.to_dict(),
                "data": {},
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        except Exception as exc:  # defensive: tools must never crash the graph
            return {
                "ok": False,
                "name": name,
                "args": args,
                "message": f"执行异常：{exc}",
                "error": {"code": "INTERNAL", "message": str(exc)},
                "data": {},
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }

    def _environment_payload(self, room_id: str | None) -> dict[str, Any]:
        env = self.simulator.snapshot()["environment"]
        if room_id:
            room = self.simulator.room(room_id)
            if not room:
                raise DeviceError("NOT_FOUND", f"未知房间 {room_id}")
            from app.devices.specs import ROOM_NAMES

            return {
                "room": room,
                "environment": env,
                "message": (
                    f"{ROOM_NAMES.get(room_id, room_id)}当前温度 {room['temperature']}°C，"
                    f"湿度 {room['humidity']}%。全屋 PM2.5 为 {env['pm25']} μg/m³。"
                ),
            }
        message = (
            f"当前室内温度 {env['indoor_temp']}°C，湿度 {env['humidity']}%，"
            f"PM2.5 {env['pm25']} μg/m³，CO₂ {env['co2']} ppm，"
            f"光照 {env['lux']} lux，实时功率约 {env['power_w']} W。"
        )
        return {"environment": env, "message": message}

    def _devices_payload(self, args: dict[str, Any]) -> dict[str, Any]:
        if args.get("device_id"):
            devices = [self.registry.get(args["device_id"])]
        else:
            devices = self.registry.find(
                room_id=args.get("room"), device_type=args.get("device_type")
            )
        if not devices:
            return {"devices": [], "message": "没有找到符合条件且已接入的设备。"}
        if len(devices) == 1:
            device = devices[0]
            return {
                "devices": devices,
                "message": f"{device['name']}目前{_device_state_text(device)}。",
            }
        online = [d for d in devices if d["online"]]
        parts = [f"{d['name']}：{_device_state_text(d)}" for d in devices]
        return {
            "devices": devices,
            "message": f"共查询到 {len(devices)} 台设备（在线 {len(online)} 台）。" + "；".join(parts),
        }


def tool_catalog() -> list[dict[str, Any]]:
    return [
        {
            "name": schema["function"]["name"],
            "description": schema["function"]["description"],
            "parameters": schema["function"]["parameters"],
        }
        for schema in BASE_TOOL_SCHEMAS
    ]
