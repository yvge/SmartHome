"""Seed corpus for intent retrieval and home knowledge Q&A."""
from __future__ import annotations

from typing import Any

CONTROL = "control"
QUERY = "query"
SCENE = "scene"
CHAT = "chat"
KNOWLEDGE = "knowledge"


def _infer_type(intent: str, kind: str) -> str:
    if kind == KNOWLEDGE:
        return KNOWLEDGE
    if intent.startswith("scene_"):
        return SCENE
    if intent.startswith("query_"):
        return QUERY
    if intent.startswith("smalltalk_"):
        return CHAT
    return CONTROL


def _examples(intent: str, device_type: str, texts: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "kind": "intent",
            "text": text,
            "intent": intent,
            "category": "device_control" if device_type else "assistant",
            "device_type": device_type,
            "answer": "",
            "metadata": {
                "intent_type": _infer_type(intent, "intent"),
                "source": "seed",
                "variant": index + 1,
            },
            "id": f"i_{intent}_{index + 1:02d}",
        }
        for index, text in enumerate(texts)
    ]


def _knowledge(
    key: str, texts: list[str], answer: str, category: str = "home_tips",
) -> list[dict[str, Any]]:
    return [
        {
            "kind": "knowledge",
            "text": text,
            "intent": f"knowledge_{key}",
            "category": category,
            "device_type": "",
            "answer": answer,
            "metadata": {"intent_type": KNOWLEDGE, "source": "seed", "topic": key},
            "id": f"k_{key}_{index + 1:02d}",
        }
        for index, text in enumerate(texts)
    ]


INTENT_GROUPS: list[tuple[str, str, list[str]]] = [
    ("light_on", "light", [
        "打开客厅主灯", "帮我把客厅的灯打开", "开一下灯", "客厅灯亮起来", "把主卧床头灯打开",
    ]),
    ("light_off", "light", [
        "关掉客厅灯", "把主卧吸顶灯关了", "关灯", "客厅的灯熄灭", "把灯全关了",
    ]),
    ("light_brightness_set", "light", [
        "客厅灯亮度调到50%", "把灯光亮度设为百分之八十", "主卧床头灯调到30%亮度",
    ]),
    ("light_brightness_up", "light", [
        "把灯调亮一点", "灯光太暗了，亮一点", "客厅灯再亮一些",
    ]),
    ("light_brightness_down", "light", [
        "调暗一点", "灯光太亮了，暗一些", "把客厅灯亮度调低",
    ]),
    ("light_color_set", "light", [
        "把客厅灯调到暖光", "灯太白了，换成暖色", "把灯光设成冷白光", "客厅灯用中性光",
    ]),
    ("ac_on", "ac", [
        "打开客厅空调", "开空调", "客厅有点热，开一下空调", "把主卧空调打开",
    ]),
    ("ac_off", "ac", [
        "关掉空调", "把主卧空调关了", "空调不用了，关了吧", "关闭客厅空调",
    ]),
    ("ac_temp_set", "ac", [
        "空调调到26度", "把客厅空调设成25度", "主卧空调温度设置为27度", "空调开24摄氏度",
    ]),
    ("ac_temp_up", "ac", [
        "空调温度调高一点", "太冷了，把温度调高两度", "空调升到27度",
    ]),
    ("ac_temp_down", "ac", [
        "空调温度调低一点", "有点热，温度调低两度", "把空调降到24度",
    ]),
    ("ac_mode_set", "ac", [
        "空调切换到制热", "开制冷模式", "空调开除湿", "把空调调成送风模式",
    ]),
    ("curtain_open", "curtain", [
        "打开窗帘", "把主卧窗帘拉开", "窗帘开一半", "窗帘打开30%", "客厅窗帘全开",
    ]),
    ("curtain_close", "curtain", [
        "关闭窗帘", "把客厅窗帘拉上", "窗帘关一半", "主卧窗帘合上",
    ]),
    ("purifier_on", "purifier", [
        "打开空气净化器", "客厅净化器开一下", "开净化器",
    ]),
    ("purifier_off", "purifier", [
        "关掉净化器", "把空气净化器停了",
    ]),
    ("purifier_mode", "purifier", [
        "净化器开强力模式", "空气净化器切换到睡眠模式", "净化器调到自动模式",
    ]),
    ("humidifier_on", "humidifier", [
        "打开加湿器", "主卧加湿器开一下",
    ]),
    ("humidifier_off", "humidifier", [
        "关掉加湿器", "把主卧加湿器关了",
    ]),
    ("humidifier_humidity", "humidifier", [
        "加湿器湿度调到60%", "把主卧加湿器目标湿度设为55",
    ]),
    ("socket_on", "socket", [
        "打开电视插座", "把电视通电", "客厅插座打开",
    ]),
    ("socket_off", "socket", [
        "关掉电视插座", "把电视断电", "客厅插座断电",
    ]),
    ("speaker_on", "speaker", [
        "打开音箱", "客厅音箱开一下",
    ]),
    ("speaker_off", "speaker", [
        "关闭音箱", "把客厅音箱关了",
    ]),
    ("speaker_play", "speaker", [
        "播放轻音乐", "让音箱放点白噪音", "播放晨间新闻", "放一首入睡冥想",
    ]),
    ("speaker_volume", "speaker", [
        "音量调到40", "音箱声音小一点", "声音大一些", "把音量调低",
    ]),
    ("vacuum_start", "vacuum", [
        "让扫地机器人开始清扫", "启动扫地机全屋清扫", "扫地机器人拖地",
    ]),
    ("vacuum_dock", "vacuum", [
        "扫地机回充", "让扫地机器人停下来回充电座",
    ]),
    ("scene_arrive", "", [
        "开启回家模式", "我到家了", "帮我执行回家场景", "进入到家模式",
    ]),
    ("scene_leave", "", [
        "出门了，进入离家模式", "开启离家场景", "我要去上班了，关好家里的设备", "执行离家模式",
    ]),
    ("scene_movie", "", [
        "打开观影模式", "我要看电影，进入影院场景", "开启观影场景",
    ]),
    ("scene_sleep", "", [
        "我要睡觉了", "开启睡眠模式", "晚安，帮我关灯睡觉", "执行睡眠场景",
    ]),
    ("scene_morning", "", [
        "早安，打开清晨模式", "开启起床场景", "该起床了，拉开窗帘",
    ]),
    ("scene_energy", "", [
        "开启全屋节能模式", "家里没人时省电模式", "执行节能场景",
    ]),
    ("query_environment", "", [
        "现在室内温度多少", "家里湿度怎么样", "空气质量如何", "客厅现在几度", "家里环境怎么样",
    ]),
    ("query_device", "", [
        "客厅灯开着吗", "空调现在几度", "主卧窗帘开合度是多少", "检查一下客厅设备状态",
    ]),
    ("query_status", "", [
        "哪些设备还开着", "家里设备状态", "帮我看看有没有没关的设备", "全屋设备情况",
    ]),
    ("smalltalk_hello", "", [
        "你好", "早上好", "嗨，在吗",
    ]),
    ("smalltalk_thanks", "", [
        "谢谢你", "辛苦了，谢谢",
    ]),
    ("smalltalk_identity", "", [
        "你是谁", "你叫什么名字",
    ]),
    ("smalltalk_capability", "", [
        "你能做什么", "你有哪些功能", "帮帮我，你能控制哪些设备",
    ]),
    ("ambiguous", "", [
        "把灯关了", "调一下温度", "帮我打开那个", "开一下",
    ]),
]

KNOWLEDGE_GROUPS: list[dict[str, Any]] = [
    {
        "key": "ac_power_saving",
        "texts": ["空调多少度最省电", "空调开几度比较省电", "夏天空调温度建议"],
        "category": "energy",
        "answer": (
            "夏季制冷建议设定在 26–28°C，每上调 1°C 大约可省电 6%–10%。"
            "搭配自动风速、定时关闭和关好门窗效果更好；睡眠时段可以开启睡眠模式，"
            "温度会缓慢上浮，既舒适又省电。"
        ),
    },
    {
        "key": "ac_not_cooling",
        "texts": ["为什么空调不制冷", "空调不凉怎么办"],
        "category": "troubleshooting",
        "answer": (
            "先确认空调处于制冷模式、设定温度低于室温，并检查门窗是否关好。"
            "如果风量明显变小，可能是滤网积灰，建议清洗滤网；室外机散热不良也会影响制冷。"
            "若设备显示离线或持续报错，请检查电源和网络，必要时联系售后。"
        ),
    },
    {
        "key": "purifier_filter",
        "texts": ["空气净化器滤芯多久换一次", "净化器滤芯寿命"],
        "category": "maintenance",
        "answer": (
            "一般 6–12 个月更换一次滤芯；如果所在地区 PM2.5 较高、使用频率大，"
            "建议 6–8 个月更换。出现风量下降、异味或滤芯指示灯亮起时，应尽快更换。"
        ),
    },
    {
        "key": "humidifier_usage",
        "texts": ["加湿器适合开多久", "加湿器怎么用比较健康"],
        "category": "health",
        "answer": (
            "室内相对湿度建议维持在 40%–60%，达到目标后即可停止或切换低档。"
            "冬季可间歇使用 2–4 小时并开窗通风；水箱建议每天换水、每周清洁，"
            "避免湿度过高（超过 70%）滋生霉菌。"
        ),
    },
    {
        "key": "scene_recommend",
        "texts": ["智能家居场景有什么推荐", "有哪些好用的场景模式"],
        "category": "scenes",
        "answer": (
            "常用场景包括回家、离家、观影、睡眠、清晨和全屋节能。"
            "回家模式会自动开灯并把空调调到舒适温度；睡眠模式会调暗灯光、合上窗帘；"
            "离家模式则关闭非必要设备。你也可以在「场景编排」里组合自己的多步场景。"
        ),
    },
    {
        "key": "leave_home",
        "texts": ["离家时应该注意什么", "出门前要关哪些设备"],
        "category": "safety",
        "answer": (
            "离家前建议关闭灯光和空调、断开电视等非必要插座、合上窗帘，"
            "并确认门锁状态。直接说「开启离家模式」可以一键完成这些操作；"
            "扫地机器人也可以安排在离家后自动清扫。"
        ),
    },
    {
        "key": "create_scene",
        "texts": ["怎么创建自己的场景", "如何添加自动化场景"],
        "category": "scenes",
        "answer": (
            "进入「场景编排」页面点击「新建场景」，选择要联动的设备和动作，"
            "可以设置执行顺序、延时与失败兜底；还能添加温度或时间条件。"
            "保存后既可以在场景卡片中一键执行，也可以直接对我说场景名称。"
        ),
    },
    {
        "key": "sleep_benefit",
        "texts": ["睡眠模式有什么好处", "睡觉时空调开多少度"],
        "category": "health",
        "answer": (
            "睡眠模式会降低灯光亮度、合上窗帘，并把空调维持在 26–27°C 的舒适区间，"
            "同时降低风速和噪音。适宜的光线和温度有助于褪黑素分泌，提升深睡比例。"
            "如果空气干燥，可以同步开启加湿器并设定 50%–55% 的湿度。"
        ),
    },
    {
        "key": "color_temperature",
        "texts": ["灯光色温怎么选", "暖光和冷光有什么区别"],
        "category": "lighting",
        "answer": (
            "2700–3000K 的暖光适合休息和睡前，4000K 中性光适合日常活动，"
            "5000–6500K 冷白光更适合阅读和专注工作。建议白天使用中性或冷白光，"
            "日落后逐步切换到暖光，帮助身体进入放松状态。"
        ),
    },
    {
        "key": "save_energy",
        "texts": ["怎么让家里更省电", "智能家居省电技巧"],
        "category": "energy",
        "answer": (
            "把空调设在 26°C 以上、使用自动风速，离开房间及时关灯；"
            "电视等设备不用时通过智能插座断电，避免待机功耗；"
            "净化器和加湿器使用自动模式，并用「离家模式」一键关闭非必要设备。"
        ),
    },
]


def build_seed_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for intent, device_type, texts in INTENT_GROUPS:
        entries.extend(_examples(intent, device_type, texts))
    for group in KNOWLEDGE_GROUPS:
        entries.extend(
            _knowledge(group["key"], group["texts"], group["answer"], group["category"])
        )
    return entries


SCENE_SEEDS: list[dict[str, Any]] = [
    {
        "id": "scene_arrive",
        "name": "回家模式",
        "icon": "home",
        "description": "点亮客厅、调节空调，让家提前进入舒适状态",
        "condition": {
            "type": "time", "op": "between", "value": ["16:00", "23:59"],
            "optional": True, "label": "傍晚到家",
        },
        "steps": [
            {
                "device_id": "light_living_main", "params": {"power": True, "brightness": 80, "color_temp": 3500},
                "delay_ms": 320, "critical": True, "label": "点亮客厅主灯",
            },
            {
                "device_id": "light_living_strip", "params": {"power": True, "brightness": 45, "color_temp": 2900},
                "delay_ms": 260, "label": "打开氛围灯带",
            },
            {
                "device_id": "ac_living", "params": {"power": True, "target_temp": 26, "mode": "cool"},
                "delay_ms": 220, "label": "客厅空调 26°C",
                "when": {"device_id": "sensor_living", "property": "temperature", "op": ">=", "value": 25.5},
            },
            {
                "device_id": "curtain_living", "params": {"position": 30},
                "delay_ms": 180, "label": "窗帘合上七成",
            },
            {
                "device_id": "purifier_living", "params": {"power": True, "mode": "auto"},
                "delay_ms": 160, "label": "空气净化器自动运行",
            },
            {
                "device_id": "speaker_living",
                "params": {"power": True, "playing": True, "track": "轻音乐", "volume": 25},
                "delay_ms": 160, "label": "播放回家轻音乐",
            },
        ],
        "fallback": [
            {
                "device_id": "light_living_main", "params": {"power": True, "brightness": 100},
                "label": "兜底：客厅灯全亮",
            },
            {
                "device_id": "ac_living", "params": {"power": True, "target_temp": 26, "mode": "cool"},
                "label": "兜底：空调保持 26°C",
            },
        ],
    },
    {
        "id": "scene_leave",
        "name": "离家模式",
        "icon": "door-open",
        "description": "一键关闭非必要设备，安心出门",
        "condition": None,
        "steps": [
            {"device_id": "light_living_main", "params": {"power": False}, "delay_ms": 220, "critical": True, "label": "关闭客厅主灯"},
            {"device_id": "light_living_strip", "params": {"power": False}, "delay_ms": 180, "label": "关闭氛围灯带"},
            {"device_id": "light_bed_main", "params": {"power": False}, "delay_ms": 160, "label": "关闭主卧吸顶灯"},
            {"device_id": "light_bed_bedside", "params": {"power": False}, "delay_ms": 160, "label": "关闭床头灯"},
            {"device_id": "light_study", "params": {"power": False}, "delay_ms": 160, "label": "关闭书房台灯"},
            {"device_id": "light_kitchen", "params": {"power": False}, "delay_ms": 160, "label": "关闭厨房灯"},
            {"device_id": "ac_living", "params": {"power": False}, "delay_ms": 220, "label": "关闭客厅空调"},
            {"device_id": "ac_bed", "params": {"power": False}, "delay_ms": 200, "label": "关闭主卧空调"},
            {"device_id": "curtain_living", "params": {"position": 0}, "delay_ms": 200, "label": "合上客厅窗帘"},
            {"device_id": "curtain_bed", "params": {"position": 0}, "delay_ms": 180, "label": "合上主卧窗帘"},
            {"device_id": "purifier_living", "params": {"power": False}, "delay_ms": 160, "label": "关闭空气净化器"},
            {"device_id": "socket_tv", "params": {"power": False}, "delay_ms": 160, "label": "电视插座断电"},
            {"device_id": "speaker_living", "params": {"power": False, "playing": False}, "delay_ms": 160, "label": "关闭智能音箱"},
            {"device_id": "humidifier_bed", "params": {"power": False}, "delay_ms": 160, "label": "关闭加湿器"},
        ],
        "fallback": [
            {"device_id": "light_living_main", "params": {"power": False}, "label": "兜底：确保客厅灯关闭"},
            {"device_id": "ac_living", "params": {"power": False}, "label": "兜底：确保空调关闭"},
        ],
    },
    {
        "id": "scene_movie",
        "name": "观影模式",
        "icon": "clapperboard",
        "description": "低亮度暖光与合拢窗帘，营造沉浸式影院氛围",
        "condition": None,
        "steps": [
            {"device_id": "light_living_main", "params": {"power": True, "brightness": 12, "color_temp": 2700}, "delay_ms": 300, "label": "主灯调至 12% 暖光"},
            {"device_id": "light_living_strip", "params": {"power": True, "brightness": 30, "color_temp": 2900}, "delay_ms": 220, "label": "氛围灯带微亮"},
            {"device_id": "curtain_living", "params": {"position": 0}, "delay_ms": 260, "label": "合拢客厅窗帘"},
            {"device_id": "ac_living", "params": {"power": True, "target_temp": 24, "mode": "cool", "fan_speed": "low"}, "delay_ms": 220, "label": "空调 24°C 低风速"},
            {"device_id": "socket_tv", "params": {"power": True}, "delay_ms": 180, "label": "电视插座通电"},
            {"device_id": "speaker_living", "params": {"power": True, "volume": 35, "playing": False}, "delay_ms": 180, "label": "音箱准备就绪"},
        ],
        "fallback": [
            {"device_id": "light_living_main", "params": {"power": True, "brightness": 30}, "label": "兜底：恢复基础照明"},
            {"device_id": "curtain_living", "params": {"position": 60}, "label": "兜底：窗帘半开"},
        ],
    },
    {
        "id": "scene_sleep",
        "name": "睡眠模式",
        "icon": "moon",
        "description": "关灯、合帘、调温，安静的睡眠环境",
        "condition": {"type": "time", "op": "between", "value": ["21:00", "23:59"], "optional": True, "label": "夜间时段"},
        "steps": [
            {"device_id": "light_living_main", "params": {"power": False}, "delay_ms": 220, "critical": True, "label": "关闭客厅主灯"},
            {"device_id": "light_living_strip", "params": {"power": False}, "delay_ms": 180, "label": "关闭氛围灯带"},
            {"device_id": "light_bed_main", "params": {"power": False}, "delay_ms": 180, "label": "关闭主卧吸顶灯"},
            {"device_id": "light_bed_bedside", "params": {"power": True, "brightness": 8, "color_temp": 2700}, "delay_ms": 200, "label": "床头灯留 8% 暖光"},
            {"device_id": "curtain_living", "params": {"position": 0}, "delay_ms": 200, "label": "合上客厅窗帘"},
            {"device_id": "curtain_bed", "params": {"position": 0}, "delay_ms": 200, "label": "合上主卧窗帘"},
            {"device_id": "ac_living", "params": {"power": False}, "delay_ms": 180, "label": "关闭客厅空调"},
            {"device_id": "ac_bed", "params": {"power": True, "target_temp": 27, "mode": "cool", "fan_speed": "low"}, "delay_ms": 240, "critical": True, "label": "主卧空调 27°C 低风速"},
            {"device_id": "humidifier_bed", "params": {"power": True, "target_humidity": 55}, "delay_ms": 180, "label": "加湿器 55%"},
            {"device_id": "purifier_living", "params": {"power": True, "mode": "sleep"}, "delay_ms": 180, "label": "净化器睡眠模式"},
            {"device_id": "socket_tv", "params": {"power": False}, "delay_ms": 160, "label": "电视插座断电"},
            {"device_id": "speaker_living", "params": {"power": True, "playing": False}, "delay_ms": 160, "label": "音箱静音待机"},
        ],
        "fallback": [
            {"device_id": "light_bed_bedside", "params": {"power": True, "brightness": 10}, "label": "兜底：保留床头微光"},
            {"device_id": "ac_bed", "params": {"power": True, "target_temp": 27}, "label": "兜底：维持主卧 27°C"},
        ],
    },
    {
        "id": "scene_morning",
        "name": "清晨模式",
        "icon": "sunrise",
        "description": "拉开窗帘、柔和叫醒，开启新的一天",
        "condition": {"type": "time", "op": "between", "value": ["05:30", "09:30"], "optional": True, "label": "清晨时段"},
        "steps": [
            {"device_id": "curtain_bed", "params": {"position": 100}, "delay_ms": 380, "critical": True, "label": "拉开主卧窗帘"},
            {"device_id": "curtain_living", "params": {"position": 100}, "delay_ms": 260, "label": "拉开客厅窗帘"},
            {"device_id": "light_bed_bedside", "params": {"power": True, "brightness": 35, "color_temp": 3000}, "delay_ms": 280, "label": "床头灯柔和亮起"},
            {"device_id": "ac_bed", "params": {"power": False}, "delay_ms": 200, "label": "关闭主卧空调"},
            {"device_id": "humidifier_bed", "params": {"power": False}, "delay_ms": 180, "label": "关闭加湿器"},
            {"device_id": "speaker_living", "params": {"power": True, "playing": True, "track": "晨间新闻", "volume": 28}, "delay_ms": 220, "label": "播放晨间新闻"},
        ],
        "fallback": [
            {"device_id": "curtain_bed", "params": {"position": 100}, "label": "兜底：拉开窗帘"},
            {"device_id": "light_bed_bedside", "params": {"power": True, "brightness": 50}, "label": "兜底：点亮床头灯"},
        ],
    },
    {
        "id": "scene_energy",
        "name": "全屋节能",
        "icon": "leaf",
        "description": "降低灯光与空调能耗，保留必要设备",
        "condition": None,
        "steps": [
            {"device_id": "light_living_main", "params": {"power": True, "brightness": 30}, "delay_ms": 240, "label": "客厅主灯降至 30%"},
            {"device_id": "light_living_strip", "params": {"power": False}, "delay_ms": 180, "label": "关闭氛围灯带"},
            {"device_id": "light_study", "params": {"power": False}, "delay_ms": 160, "label": "关闭书房台灯"},
            {"device_id": "ac_living", "params": {"power": True, "target_temp": 27, "mode": "cool", "fan_speed": "auto"}, "delay_ms": 240, "label": "客厅空调 27°C"},
            {"device_id": "ac_bed", "params": {"power": False}, "delay_ms": 180, "label": "关闭主卧空调"},
            {"device_id": "purifier_living", "params": {"power": True, "mode": "auto"}, "delay_ms": 160, "label": "净化器自动模式"},
            {"device_id": "socket_tv", "params": {"power": False}, "delay_ms": 160, "label": "电视插座断电"},
        ],
        "fallback": [
            {"device_id": "socket_tv", "params": {"power": False}, "label": "兜底：切断待机功耗"},
        ],
    },
]
