"""Heterogeneous device definitions.

Every device type is described once here: its writable capabilities (which
later become the vocabulary of the Function-Calling tools and the UI
controls), its read-only telemetry fields, and its seed instances.
"""
from __future__ import annotations

from typing import Any

ROOMS: list[dict[str, str]] = [
    {"id": "living", "name": "客厅", "icon": "sofa"},
    {"id": "bedroom", "name": "主卧", "icon": "bed"},
    {"id": "second_bedroom", "name": "次卧", "icon": "bed-single"},
    {"id": "study", "name": "书房", "icon": "book-open"},
    {"id": "kitchen", "name": "厨房", "icon": "utensils"},
    {"id": "balcony", "name": "阳台", "icon": "trees"},
]

ROOM_NAMES = {room["id"]: room["name"] for room in ROOMS}
ROOM_IDS = {room["name"]: room["id"] for room in ROOMS}


def _range(key: str, label: str, minimum: int, maximum: int, step: int,
           unit: str, default: int) -> dict[str, Any]:
    return {
        "key": key, "label": label, "type": "range",
        "min": minimum, "max": maximum, "step": step,
        "unit": unit, "default": default,
    }


def _enum(key: str, label: str, options: list[dict[str, str]],
          default: str) -> dict[str, Any]:
    return {
        "key": key, "label": label, "type": "enum",
        "options": options, "default": default,
    }


def _bool(key: str, label: str, default: bool) -> dict[str, Any]:
    return {"key": key, "label": label, "type": "boolean", "default": default}


def _readonly(key: str, label: str, unit: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "type": "readonly", "unit": unit}


TYPE_SPECS: dict[str, dict[str, Any]] = {
    "light": {
        "label": "灯光",
        "icon": "ceiling-light",
        "writable": ["power", "brightness", "color_temp"],
        "capabilities": [
            _bool("power", "开关", True),
            _range("brightness", "亮度", 1, 100, 1, "%", 80),
            _range("color_temp", "色温", 2700, 6500, 100, "K", 4000),
        ],
        "defaults": {"power": True, "brightness": 80, "color_temp": 4000},
    },
    "ac": {
        "label": "空调",
        "icon": "air-vent",
        "writable": ["power", "target_temp", "mode", "fan_speed"],
        "capabilities": [
            _bool("power", "开关", False),
            _range("target_temp", "设定温度", 16, 30, 1, "°C", 26),
            _enum("mode", "模式", [
                {"value": "cool", "label": "制冷"},
                {"value": "heat", "label": "制热"},
                {"value": "dry", "label": "除湿"},
                {"value": "fan", "label": "送风"},
                {"value": "auto", "label": "自动"},
            ], "cool"),
            _enum("fan_speed", "风速", [
                {"value": "auto", "label": "自动"},
                {"value": "low", "label": "低速"},
                {"value": "medium", "label": "中速"},
                {"value": "high", "label": "高速"},
            ], "auto"),
        ],
        "defaults": {
            "power": False, "target_temp": 26, "mode": "cool", "fan_speed": "auto",
        },
    },
    "curtain": {
        "label": "窗帘",
        "icon": "blinds",
        "writable": ["position"],
        "capabilities": [
            _range("position", "开合度", 0, 100, 1, "%", 0),
        ],
        "defaults": {"position": 0},
    },
    "purifier": {
        "label": "空气净化器",
        "icon": "wind",
        "writable": ["power", "mode"],
        "capabilities": [
            _bool("power", "开关", False),
            _enum("mode", "模式", [
                {"value": "auto", "label": "自动"},
                {"value": "sleep", "label": "睡眠"},
                {"value": "high", "label": "强力"},
            ], "auto"),
            _readonly("pm25", "PM2.5", "μg/m³"),
        ],
        "defaults": {"power": False, "mode": "auto", "pm25": 21},
    },
    "humidifier": {
        "label": "加湿器",
        "icon": "droplets",
        "writable": ["power", "target_humidity"],
        "capabilities": [
            _bool("power", "开关", False),
            _range("target_humidity", "目标湿度", 30, 80, 1, "%", 55),
        ],
        "defaults": {"power": False, "target_humidity": 55},
    },
    "socket": {
        "label": "智能插座",
        "icon": "plug",
        "writable": ["power"],
        "capabilities": [
            _bool("power", "通断电", True),
            _readonly("power_w", "功率", "W"),
        ],
        "defaults": {"power": True, "power_w": 18},
    },
    "speaker": {
        "label": "智能音箱",
        "icon": "speaker",
        "writable": ["power", "volume", "playing", "track"],
        "capabilities": [
            _bool("power", "开关", True),
            _range("volume", "音量", 0, 100, 1, "%", 30),
            _bool("playing", "播放", False),
            _enum("track", "内容", [
                {"value": "晨间新闻", "label": "晨间新闻"},
                {"value": "轻音乐", "label": "轻音乐"},
                {"value": "白噪音", "label": "白噪音"},
                {"value": "入睡冥想", "label": "入睡冥想"},
            ], "轻音乐"),
        ],
        "defaults": {"power": True, "volume": 30, "playing": False, "track": "轻音乐"},
    },
    "vacuum": {
        "label": "扫地机器人",
        "icon": "bot",
        "writable": ["power", "mode"],
        "capabilities": [
            _bool("power", "启动清扫", False),
            _enum("mode", "清扫模式", [
                {"value": "auto", "label": "全屋清扫"},
                {"value": "spot", "label": "定点清扫"},
                {"value": "edge", "label": "沿边清扫"},
                {"value": "mop", "label": "拖地"},
            ], "auto"),
            _readonly("battery", "电量", "%"),
        ],
        "defaults": {"power": False, "mode": "auto", "battery": 100, "state": "docked"},
    },
    "sensor": {
        "label": "环境传感器",
        "icon": "thermometer",
        "writable": [],
        "capabilities": [
            _readonly("temperature", "温度", "°C"),
            _readonly("humidity", "湿度", "%"),
            _readonly("pm25", "PM2.5", "μg/m³"),
            _readonly("battery", "电量", "%"),
        ],
        "defaults": {
            "temperature": 26.4, "humidity": 52, "pm25": 21, "battery": 92,
        },
    },
}

# Human labels used by the offline NLU / planner.
TYPE_LABELS = {key: spec["label"] for key, spec in TYPE_SPECS.items()}


def capabilities_for(device_type: str) -> list[dict[str, Any]]:
    return [dict(cap) for cap in TYPE_SPECS[device_type]["capabilities"]]


def default_properties(device_type: str) -> dict[str, Any]:
    return dict(TYPE_SPECS[device_type]["defaults"])


DEVICE_SEEDS: list[dict[str, Any]] = [
    {
        "id": "light_living_main", "name": "客厅主灯", "room": "客厅",
        "room_id": "living", "type": "light", "icon": "ceiling-light",
        "sort_order": 1,
        "properties": {"power": True, "brightness": 72, "color_temp": 3800},
    },
    {
        "id": "light_living_strip", "name": "客厅氛围灯带", "room": "客厅",
        "room_id": "living", "type": "light", "icon": "lightbulb",
        "sort_order": 2,
        "properties": {"power": True, "brightness": 35, "color_temp": 2900},
    },
    {
        "id": "light_bed_main", "name": "主卧吸顶灯", "room": "主卧",
        "room_id": "bedroom", "type": "light", "icon": "ceiling-light",
        "sort_order": 3,
        "properties": {"power": False, "brightness": 65, "color_temp": 3500},
    },
    {
        "id": "light_bed_bedside", "name": "主卧床头灯", "room": "主卧",
        "room_id": "bedroom", "type": "light", "icon": "lamp",
        "sort_order": 4,
        "properties": {"power": False, "brightness": 30, "color_temp": 2700},
    },
    {
        "id": "light_study", "name": "书房台灯", "room": "书房",
        "room_id": "study", "type": "light", "icon": "lamp-desk",
        "sort_order": 5,
        "properties": {"power": False, "brightness": 70, "color_temp": 4500},
    },
    {
        "id": "light_kitchen", "name": "厨房灯", "room": "厨房",
        "room_id": "kitchen", "type": "light", "icon": "ceiling-light",
        "sort_order": 6,
        "properties": {"power": False, "brightness": 85, "color_temp": 5000},
    },
    {
        "id": "ac_living", "name": "客厅空调", "room": "客厅",
        "room_id": "living", "type": "ac", "icon": "air-vent",
        "sort_order": 7,
        "properties": {
            "power": True, "target_temp": 26, "mode": "cool", "fan_speed": "auto",
        },
    },
    {
        "id": "ac_bed", "name": "主卧空调", "room": "主卧",
        "room_id": "bedroom", "type": "ac", "icon": "air-vent",
        "sort_order": 8,
        "properties": {
            "power": False, "target_temp": 26, "mode": "cool", "fan_speed": "auto",
        },
    },
    {
        "id": "curtain_living", "name": "客厅窗帘", "room": "客厅",
        "room_id": "living", "type": "curtain", "icon": "blinds",
        "sort_order": 9, "properties": {"position": 100},
    },
    {
        "id": "curtain_bed", "name": "主卧窗帘", "room": "主卧",
        "room_id": "bedroom", "type": "curtain", "icon": "blinds",
        "sort_order": 10, "properties": {"position": 0},
    },
    {
        "id": "purifier_living", "name": "客厅空气净化器", "room": "客厅",
        "room_id": "living", "type": "purifier", "icon": "wind",
        "sort_order": 11,
        "properties": {"power": True, "mode": "auto", "pm25": 21},
    },
    {
        "id": "humidifier_bed", "name": "主卧加湿器", "room": "主卧",
        "room_id": "bedroom", "type": "humidifier", "icon": "droplets",
        "sort_order": 12,
        "properties": {"power": False, "target_humidity": 55},
    },
    {
        "id": "socket_tv", "name": "电视插座", "room": "客厅",
        "room_id": "living", "type": "socket", "icon": "plug",
        "sort_order": 13, "properties": {"power": True, "power_w": 18},
    },
    {
        "id": "speaker_living", "name": "客厅智能音箱", "room": "客厅",
        "room_id": "living", "type": "speaker", "icon": "speaker",
        "sort_order": 14,
        "properties": {
            "power": True, "volume": 30, "playing": False, "track": "轻音乐",
        },
    },
    {
        "id": "vacuum_robot", "name": "扫地机器人", "room": "客厅",
        "room_id": "living", "type": "vacuum", "icon": "bot",
        "sort_order": 15,
        "properties": {
            "power": False, "mode": "auto", "battery": 100, "state": "docked",
        },
    },
    {
        "id": "sensor_second", "name": "次卧温湿度传感器", "room": "次卧",
        "room_id": "second_bedroom", "type": "sensor", "icon": "thermometer",
        "sort_order": 20,
        "properties": {
            "temperature": 26.9, "humidity": 49, "pm25": 21, "battery": 88,
        },
    },
    {
        "id": "sensor_living", "name": "客厅温湿度传感器", "room": "客厅",
        "room_id": "living", "type": "sensor", "icon": "thermometer",
        "sort_order": 16,
        "properties": {
            "temperature": 26.4, "humidity": 52, "pm25": 21, "battery": 92,
        },
    },
    {
        "id": "light_second", "name": "次卧吸顶灯", "room": "次卧",
        "room_id": "second_bedroom", "type": "light", "icon": "ceiling-light",
        "sort_order": 17,
        "properties": {"power": False, "brightness": 60, "color_temp": 3500},
    },
    {
        "id": "light_balcony", "name": "阳台灯", "room": "阳台",
        "room_id": "balcony", "type": "light", "icon": "lightbulb",
        "sort_order": 18,
        "properties": {"power": False, "brightness": 55, "color_temp": 4000},
    },
    {
        "id": "curtain_balcony", "name": "阳台窗帘", "room": "阳台",
        "room_id": "balcony", "type": "curtain", "icon": "blinds",
        "sort_order": 19, "properties": {"position": 100},
    },
]


def build_device_seed(seed: dict[str, Any]) -> dict[str, Any]:
    """Attach the schema-derived capabilities/defaults to a seed instance."""
    spec = TYPE_SPECS[seed["type"]]
    properties = dict(spec["defaults"])
    properties.update(seed.get("properties", {}))
    return {
        **seed,
        "online": seed.get("online", True),
        "properties": properties,
        "capabilities": capabilities_for(seed["type"]),
        "updated_at": "",
    }


def kelvin_to_hex(kelvin: int) -> str:
    """Cheap black-body approximation used for light glow in the UI."""
    stops = [
        (2700, (255, 180, 107)),
        (3000, (255, 194, 125)),
        (4000, (255, 228, 196)),
        (5000, (255, 246, 232)),
        (6500, (234, 244, 255)),
    ]
    kelvin = max(2000, min(7000, kelvin))
    if kelvin <= stops[0][0]:
        r, g, b = stops[0][1]
    elif kelvin >= stops[-1][0]:
        r, g, b = stops[-1][1]
    else:
        for (k1, c1), (k2, c2) in zip(stops, stops[1:]):
            if k1 <= kelvin <= k2:
                ratio = (kelvin - k1) / (k2 - k1)
                r = round(c1[0] + (c2[0] - c1[0]) * ratio)
                g = round(c1[1] + (c2[1] - c1[1]) * ratio)
                b = round(c1[2] + (c2[2] - c1[2]) * ratio)
                break
        else:  # pragma: no cover
            r, g, b = stops[2][1]
    return f"#{r:02x}{g:02x}{b:02x}"
