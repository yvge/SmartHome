"""Rule-based Chinese NLU.

This is the deterministic "brain" used when no LLM key is configured. It is
also the validator/fallback for LLM output. It resolves rooms, device
aliases, pronouns, follow-up deltas, multi-command utterances and clarifies
ambiguous targets.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.devices.registry import DeviceError, DeviceRegistry
from app.devices.specs import ROOM_NAMES, TYPE_LABELS

CONTROL = "control"
QUERY = "query"
SCENE = "scene"
CHAT = "chat"
KNOWLEDGE = "knowledge"
CLARIFY = "clarify"

ROOM_ALIASES: dict[str, list[str]] = {
    "living": ["客厅", "起居室", "大厅"],
    "bedroom": ["主卧", "主卧室", "大卧室", "卧室"],
    "second_bedroom": ["次卧", "次卧室", "小卧室", "客房"],
    "study": ["书房"],
    "kitchen": ["厨房"],
    "balcony": ["阳台"],
}

TYPE_KEYWORDS: dict[str, list[str]] = {
    "light": ["灯光", "吸顶灯", "灯带", "台灯", "床头灯", "照明", "灯"],
    "ac": ["空调", "冷气", "暖气"],
    "curtain": ["窗帘", "帘子"],
    "purifier": ["空气净化器", "净化器", "净化机"],
    "humidifier": ["加湿器", "增湿器"],
    "socket": ["电视插座", "插座", "电视"],
    "speaker": ["智能音箱", "音箱", "音响", "扬声器"],
    "vacuum": ["扫地机器人", "扫地机", "扫地", "机器人"],
}

SPECIFIC_ALIASES: list[tuple[str, list[str]]] = [
    ("light_living_strip", ["氛围灯带", "氛围灯", "灯带"]),
    ("light_bed_bedside", ["床头灯"]),
    ("light_study", ["台灯"]),
    ("socket_tv", ["电视插座", "电视"]),
    ("vacuum_robot", ["扫地机器人", "扫地机"]),
    ("purifier_living", ["空气净化器", "净化器", "净化机"]),
    ("humidifier_bed", ["加湿器", "增湿器"]),
    ("speaker_living", ["智能音箱", "音箱", "音响", "扬声器"]),
    ("curtain_living", ["客厅窗帘"]),
    ("curtain_bed", ["主卧窗帘"]),
]

SCENE_ALIASES: dict[str, list[str]] = {
    "scene_arrive": ["回家模式", "回家场景", "回家", "到家", "我回来了", "居家模式", "居家场景"],
    "scene_leave": ["离家模式", "离家场景", "离家", "出门", "去上班", "外出"],
    "scene_movie": ["观影模式", "观影场景", "观影", "看电影", "影院"],
    "scene_sleep": ["睡眠模式", "睡眠场景", "睡眠", "睡觉", "晚安"],
    "scene_morning": ["清晨模式", "清晨场景", "起床模式", "起床", "早安"],
    "scene_energy": ["节能模式", "节能场景", "省电模式", "全屋节能", "节能"],
}

ON_WORDS = ["打开", "开启", "启动", "开一下", "放点", "播放", "通电", "亮起来", "亮起", "开"]
OFF_WORDS = ["关闭", "关掉", "关上", "关了", "停止", "停掉", "停下", "断电", "熄灭", "熄灯", "关"]
OPEN_WORDS = ["拉开", "全开", "打开", "开一半", "半开"]
CLOSE_WORDS = ["拉上", "合上", "关闭", "关上", "合拢"]
QUERY_WORDS = ["几度", "多少度", "多少", "状态", "情况", "开着吗", "开着没", "关了吗", "开了吗", "开合度", "查一下", "查查", "看看", "检查", "有没有", "哪些"]
QUESTION_WORDS = ["怎么", "如何", "为什么", "多少", "哪些", "多久", "什么", "是否", "吗", "呢", "？", "?"]
ENV_WORDS = ["温度", "湿度", "pm2.5", "pm25", "空气质量", "二氧化碳", "co2", "光照", "环境", "几度", "多少度"]
KNOWLEDGE_HINTS = ["省电", "耗电", "滤芯", "保养", "多久换", "怎么用", "推荐", "注意", "好处", "技巧", "适合", "为什么", "怎么办", "怎么创建", "如何创建", "合适", "建议", "最好", "多久"]

GREETING_REPLY = (
    "你好，我是小居，你的智能家居 AI 管家。你可以直接说「打开客厅灯」"
    "「空调调到 26 度」或者「开启回家模式」。"
)
THANKS_REPLY = "不客气，随时叫我。"
IDENTITY_REPLY = (
    "我是小居，负责理解你的自然语言指令、调用全屋设备，并用 LangGraph 编排多步场景。"
)
CAPABILITY_REPLY = (
    "我可以控制灯光、空调、窗帘、空气净化器、加湿器、智能插座、音箱和扫地机器人，"
    "也能一键编排回家、离家、观影、睡眠等场景。试试说：「观影模式」或「把客厅灯调到暖光」。"
)

_FILLER = re.compile(r"[。！？!?，,；;：:、\s]+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("摄氏度", "度").replace("℃", "度")
    return text.strip()


def clean_for_match(text: str) -> str:
    return _FILLER.sub("", text)


def cn_to_int(value: str) -> int | None:
    digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100}
    if not value:
        return None
    if all(char in digits for char in value):
        return int("".join(str(digits[char]) for char in value))
    total, current = 0, 0
    for char in value:
        if char in digits:
            current = digits[char]
        elif char == "十":
            total += (current or 1) * 10
            current = 0
        elif char == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current


def extract_number(text: str, *, percent: bool = False, temperature: bool = False) -> int | None:
    if percent:
        match = re.search(r"百分之\s*([零一二两三四五六七八九十百\d]+)", text)
        if not match:
            match = re.search(r"([\d]+(?:\.\d+)?)\s*%", text)
        if match:
            raw = match.group(1)
            return int(float(raw)) if re.fullmatch(r"[\d.]+", raw) else cn_to_int(raw)
    if temperature:
        match = re.search(r"([\d]+(?:\.\d+)?)\s*(?:度|°c|c)", text)
        if not match:
            match = re.search(r"温度[^\d零一二两三四五六七八九十百]{0,3}([零一二两三四五六七八九十百]+)", text)
        if match:
            raw = match.group(1)
            return int(float(raw)) if re.fullmatch(r"[\d.]+", raw) else cn_to_int(raw)
    match = re.search(r"([\d]+(?:\.\d+)?)", text)
    if match:
        return int(float(match.group(1)))
    match = re.search(r"([零一二两三四五六七八九十百]{1,3})(?=\s*度|\s*%|\s*个百分点)", text)
    if match:
        return cn_to_int(match.group(1))
    return None


def detect_room(text: str) -> str | None:
    for room_id, aliases in ROOM_ALIASES.items():
        for alias in aliases:
            if alias in text:
                return room_id
    return None


def detect_global(text: str) -> bool:
    return any(word in text for word in ["全屋", "所有", "全部", "每个房间", "各个房间", "整屋"])


def detect_types(text: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for device_type, keywords in TYPE_KEYWORDS.items():
        positions = [text.find(keyword) for keyword in keywords if keyword in text]
        if positions:
            found.append((min(positions), device_type))
    found.sort()
    return [device_type for _, device_type in found]


def detect_specific(text: str, registry: DeviceRegistry) -> tuple[str | None, str | None]:
    for device in registry.snapshot():
        if device["name"] and device["name"] in text:
            return device["id"], device["type"]
    for device_id, aliases in SPECIFIC_ALIASES:
        if any(alias in text for alias in aliases):
            try:
                device = registry.get(device_id)
            except DeviceError:
                continue
            return device["id"], device["type"]
    if "主灯" in text or "吸顶灯" in text:
        room = detect_room(text)
        candidates = registry.find(room_id=room, device_type="light") if room else registry.find(device_type="light")
        candidates = [d for d in candidates if "吸顶灯" in d["name"] or "主灯" in d["name"]]
        if candidates:
            return candidates[0]["id"], "light"
    return None, None


def _is_question(text: str) -> bool:
    return any(word in text for word in QUESTION_WORDS)


def _color_temp(text: str) -> int | None:
    match = re.search(r"([\d]{4,5})\s*k", text)
    if match:
        return int(match.group(1))
    if any(word in text for word in ["暖光", "暖色", "暖白", "黄光", "温馨", "调暖", "暖一点", "暖一些"]):
        return 3000
    if any(word in text for word in ["中性光", "自然光", "自然白", "中性色"]):
        return 4000
    if any(word in text for word in ["冷白", "冷光", "白光", "日光", "调冷", "冷一点", "冷一些"]):
        return 6000
    if "正白" in text:
        return 5000
    return None


def _ac_mode(text: str) -> str | None:
    if any(word in text for word in ["制热", "暖风", "加热"]):
        return "heat"
    if any(word in text for word in ["除湿", "抽湿"]):
        return "dry"
    if any(word in text for word in ["送风", "通风"]):
        return "fan"
    if "自动" in text:
        return "auto"
    if any(word in text for word in ["制冷", "冷风", "降温模式"]):
        return "cool"
    return None


def _fan_speed(text: str) -> str | None:
    if any(word in text for word in ["低风", "低档", "小风"]):
        return "low"
    if any(word in text for word in ["中风", "中档"]):
        return "medium"
    if any(word in text for word in ["高风", "高档", "强劲", "最大风"]):
        return "high"
    if "自动风" in text:
        return "auto"
    return None


def _track(text: str) -> str | None:
    if "新闻" in text:
        return "晨间新闻"
    if "白噪音" in text or "白噪声" in text:
        return "白噪音"
    if "冥想" in text:
        return "入睡冥想"
    if "轻音乐" in text or "音乐" in text:
        return "轻音乐"
    return None


@dataclass
class Action:
    intent: str
    device_ids: list[str]
    params: dict[str, Any] = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "device_ids": self.device_ids,
            "params": self.params,
            "label": self.label,
        }


@dataclass
class ParsedIntent:
    intent_type: str
    intent: str
    confidence: float
    source: str
    actions: list[Action] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)
    scene_id: str | None = None
    direct_reply: str | None = None
    clarify: str | None = None
    options: list[dict[str, Any]] = field(default_factory=list)
    pending: dict[str, Any] | None = None
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    room: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "intent": self.intent,
            "confidence": round(float(self.confidence), 3),
            "source": self.source,
            "actions": [action.to_dict() for action in self.actions],
            "targets": self.targets,
            "slots": self.slots,
            "scene_id": self.scene_id,
            "direct_reply": self.direct_reply,
            "clarify": self.clarify,
            "options": self.options,
            "pending": self.pending,
            "knowledge": self.knowledge,
            "room": self.room,
        }


class OfflineNLU:
    def __init__(self, registry: DeviceRegistry, simulator, scenes: list[dict[str, Any]]) -> None:
        self.registry = registry
        self.simulator = simulator
        self.scenes = scenes

    # --------------------------------------------------------------- public
    def parse(
        self,
        text: str,
        *,
        retrieved: list[dict[str, Any]],
        last_devices: list[str],
        pending: dict[str, Any] | None = None,
    ) -> ParsedIntent:
        raw = normalize(text)
        compact = clean_for_match(raw)
        if not compact:
            return self._chat("我在，想让我做什么？比如开灯、调空调或者启动场景。", confidence=0.3)

        if pending:
            resolved = self._resolve_pending(raw, compact, pending, last_devices)
            if resolved is not None:
                return resolved

        # 1. Scenes (before generic action parsing, after question filtering).
        scene = self._match_scene(raw, compact)
        if scene:
            return scene

        # 2. Pure greetings / chit-chat that must not be parsed as device verbs.
        chat = self._match_chat(compact)
        if chat:
            return chat

        # 3. Explicit environment queries.
        environment = self._match_environment(raw, compact)
        if environment:
            return environment

        # 4. Knowledge questions take precedence over device queries when the
        #    question is advisory ("空调多少度最省电").
        knowledge = self._match_knowledge(raw, compact, retrieved)
        if knowledge:
            return knowledge

        # 5. Device state queries.
        device_query = self._match_device_query(raw, compact, last_devices)
        if device_query:
            return device_query

        # 6. Control commands (possibly multiple clauses).
        control = self._parse_controls(raw, compact, last_devices)
        if control:
            return control

        # 7. RAG-assisted fallback for paraphrases the rules missed.
        assisted = self._rag_assist(raw, compact, retrieved, last_devices)
        if assisted:
            return assisted

        return self._chat(
            "这句话我还没完全理解。你可以试试：打开客厅主灯、空调调到 26 度、"
            "开启观影模式，或者问我现在室内的温湿度。",
            confidence=0.28,
        )

    # -------------------------------------------------------------- scenes
    def _match_scene(self, raw: str, compact: str) -> ParsedIntent | None:
        for scene in self.scenes:
            name = scene["name"]
            aliases = SCENE_ALIASES.get(scene["id"], []) + [name, name.replace("模式", "")]
            matched = any(alias and alias in raw for alias in aliases)
            if not matched:
                continue
            command_like = any(
                word in raw for word in ["模式", "场景", "开启", "执行", "进入", "打开", "启动"]
            )
            if _is_question(raw) and not command_like:
                return None
            if scene["id"] == "scene_energy" and ("省电" in raw or "耗电" in raw) and _is_question(raw):
                return None
            if not command_like and len(compact) > 14:
                continue
            return ParsedIntent(
                intent_type=SCENE,
                intent=scene["id"],
                confidence=0.94,
                source="rule",
                scene_id=scene["id"],
                targets=[],
                slots={"scene_name": name},
                direct_reply=None,
            )
        if "场景" in raw and any(word in raw for word in ["所有", "哪些", "有什么", "列表"]):
            names = "、".join(scene["name"] for scene in self.scenes)
            return self._chat(f"目前有这些场景：{names}。你可以说「开启回家模式」直接执行。", confidence=0.7)
        return None

    # --------------------------------------------------------------- chat
    def _match_chat(self, compact: str) -> ParsedIntent | None:
        greetings = ["你好", "您好", "早上好", "上午好", "下午好", "晚上好", "嗨", "在吗", "hello", "hi"]
        thanks = ["谢谢", "谢了", "辛苦了", "感谢"]
        identity = ["你是谁", "你叫什么", "介绍一下你自己", "你是什么"]
        capability = ["你能做什么", "你会什么", "有哪些功能", "能控制什么", "可以做什么", "帮我做什么"]
        if any(word in compact for word in capability):
            return self._chat(CAPABILITY_REPLY, confidence=0.9, intent="smalltalk_capability")
        if any(word in compact for word in identity):
            return self._chat(IDENTITY_REPLY, confidence=0.92, intent="smalltalk_identity")
        if any(word in compact for word in thanks):
            return self._chat(THANKS_REPLY, confidence=0.92, intent="smalltalk_thanks")
        if any(word in compact for word in greetings) and len(compact) <= 12:
            return self._chat(GREETING_REPLY, confidence=0.9, intent="smalltalk_hello")
        return None

    @staticmethod
    def _chat(
        reply: str, *, confidence: float, intent: str = "smalltalk_fallback",
    ) -> ParsedIntent:
        return ParsedIntent(
            intent_type=CHAT,
            intent=intent,
            confidence=confidence,
            source="rule",
            direct_reply=reply,
        )

    # -------------------------------------------------------- environment
    def _match_environment(self, raw: str, compact: str) -> ParsedIntent | None:
        if not any(word in raw for word in ENV_WORDS):
            return None
        # Knowledge questions and device-specific questions take precedence.
        if any(word in raw for word in KNOWLEDGE_HINTS) or detect_types(raw):
            return None
        if any(word in raw for word in ["空气质量", "pm2.5", "pm25"]):
            room = detect_room(raw)
            return ParsedIntent(
                intent_type=QUERY, intent="query_environment", confidence=0.9,
                source="rule", room=room,
                actions=[Action("query_environment", [], {"room": room} if room else {})],
                slots={"room": room} if room else {},
            )
        if not any(word in raw for word in ["温度", "湿度", "几度", "多少度", "环境", "空气质量", "co2", "二氧化碳", "光照", "pm"]):
            return None
        room = detect_room(raw)
        return ParsedIntent(
            intent_type=QUERY,
            intent="query_environment",
            confidence=0.9,
            source="rule",
            room=room,
            actions=[Action("query_environment", [], {"room": room} if room else {})],
            slots={"room": room} if room else {},
        )

    # ----------------------------------------------------------- device query
    def _match_device_query(
        self, raw: str, compact: str, last_devices: list[str],
    ) -> ParsedIntent | None:
        queryish = any(word in raw for word in QUERY_WORDS)
        all_scope = any(word in raw for word in ["哪些", "所有", "全屋", "有没有没关", "设备状态", "什么情况"])
        if not queryish:
            return None
        device_types = detect_types(raw)
        if not device_types and all_scope:
            action = Action("query_status", [], {"scope": "all"})
            return ParsedIntent(
                intent_type=QUERY, intent="query_status", confidence=0.88,
                source="rule", actions=[action], slots={"scope": "all"},
            )
        if not device_types:
            # "现在家里情况怎么样" without explicit device -> environment overview.
            if any(word in raw for word in ["家里", "家", "环境", "情况"]):
                return ParsedIntent(
                    intent_type=QUERY, intent="query_environment", confidence=0.75,
                    source="rule",
                    actions=[Action("query_environment", [], {})],
                )
            return None
        if any(word in raw for word in ["温度", "湿度", "pm", "空气质量"]) and "空调" not in raw:
            return None
        room = detect_room(raw)
        specific_id, _ = detect_specific(raw, self.registry)
        device_type = device_types[0]
        if specific_id:
            device_name = self.registry.get(specific_id)["name"]
            action = Action("query_device", [specific_id], {}, f"查询{device_name}")
            return ParsedIntent(
                intent_type=QUERY, intent="query_device", confidence=0.9, source="rule",
                actions=[action], targets=[specific_id], slots={"room": room} if room else {},
            )
        candidates = self.registry.find(room_id=room, device_type=device_type)
        if not candidates:
            return None
        if len(candidates) == 1:
            action = Action(
                "query_device", [candidates[0]["id"]], {},
                f"查询{candidates[0]['name']}",
            )
            return ParsedIntent(
                intent_type=QUERY, intent="query_device", confidence=0.88, source="rule",
                actions=[action], targets=[candidates[0]["id"]],
            )
        params = {"device_type": device_type}
        if room:
            params["room"] = room
        action = Action("query_device", [], params, f"查询{TYPE_LABELS.get(device_type, device_type)}状态")
        return ParsedIntent(
            intent_type=QUERY, intent="query_device", confidence=0.82, source="rule",
            actions=[action],
        )

    # ------------------------------------------------------------ knowledge
    def _match_knowledge(
        self, raw: str, compact: str, retrieved: list[dict[str, Any]],
    ) -> ParsedIntent | None:
        top = next((hit for hit in retrieved if hit.get("kind") == "knowledge"), None)
        hinted = any(word in raw for word in KNOWLEDGE_HINTS)
        question = _is_question(raw)
        if top and float(top.get("score") or 0) >= 0.55 and question:
            return self._knowledge_intent(raw, retrieved, float(top.get("score")))
        if hinted and question:
            return self._knowledge_intent(raw, retrieved, 0.55)
        if hinted and not question and any(word in raw for word in ["怎么", "如何", "为什么"]):
            return self._knowledge_intent(raw, retrieved, 0.5)
        return None

    @staticmethod
    def _knowledge_intent(
        question: str, retrieved: list[dict[str, Any]], score: float,
    ) -> ParsedIntent:
        hits = [hit for hit in retrieved if hit.get("kind") == "knowledge"][:3]
        return ParsedIntent(
            intent_type=KNOWLEDGE,
            intent=hits[0].get("intent") if hits else "knowledge_general",
            confidence=min(0.92, max(0.55, score + 0.15)),
            source="rule",
            knowledge=hits,
            slots={"question": question},
        )

    # -------------------------------------------------------------- control
    def _parse_controls(
        self, raw: str, compact: str, last_devices: list[str],
    ) -> ParsedIntent | None:
        clauses = self._split_clauses(raw)
        actions: list[Action] = []
        clarifications: list[ParsedIntent] = []
        for clause in clauses:
            if not clause.strip():
                continue
            parsed = self._parse_clause(clause, last_devices)
            if parsed is None:
                continue
            clause_actions, clarification = parsed
            actions.extend(clause_actions)
            if clarification:
                clarifications.append(clarification)
        if clarifications:
            # Present the first ambiguity; keep already-parsed actions as context.
            return clarifications[0]
        if not actions:
            return None
        merged = self._merge_actions(actions)
        return ParsedIntent(
            intent_type=CONTROL,
            intent=merged[0].intent,
            confidence=0.9 if len(merged) == 1 else 0.86,
            source="rule",
            actions=merged,
            targets=[device_id for action in merged for device_id in action.device_ids],
            slots={key: value for action in merged for key, value in action.params.items()},
        )

    @staticmethod
    def _split_clauses(raw: str) -> list[str]:
        normalized = re.sub(r"[，,。；;]+", "|", raw)
        normalized = re.sub(r"(然后|接着|并且|同时|顺便|再帮我|再把)", "|", normalized)
        parts = [part.strip() for part in normalized.split("|") if part.strip()]

        def is_parameter_fragment(fragment: str) -> bool:
            """A short trailing fragment such as 开一半 / 亮度调到80%."""
            if detect_types(fragment) or detect_room(fragment):
                return False
            if any(word in fragment for word in ["模式", "场景"]):
                return False
            return bool(
                re.search(r"(调到|设成|设为|开到|拉到|开一半|关一半|半开|全开|全关|一点|一些|再|到\d)", fragment)
                or re.fullmatch(r"[\d零一二两三四五六七八九十百]+(度|%|个百分点)", fragment)
            )

        merged: list[str] = []
        for part in parts:
            if merged and is_parameter_fragment(part):
                merged[-1] = f"{merged[-1]}，{part}"
            else:
                merged.append(part)
        return merged

    def _parse_clause(
        self, clause: str, last_devices: list[str],
    ) -> tuple[list[Action], ParsedIntent | None] | None:
        compact = clean_for_match(clause)
        types = detect_types(clause)
        specific_id, specific_type = detect_specific(clause, self.registry)
        room = detect_room(clause)
        global_scope = detect_global(clause)

        # Directional follow-ups without an explicit device noun.
        if not types:
            inferred = self._infer_type_from_keywords(clause, last_devices)
            if inferred:
                types = [inferred]
            else:
                return None

        # Deduplicate while preserving order; a specific device narrows the type.
        if specific_type and specific_type in types:
            types = [specific_type] + [t for t in types if t != specific_type]

        actions: list[Action] = []
        on = self._has_any(clause, ON_WORDS)
        off = self._has_any(clause, OFF_WORDS) and not self._has_open_close_conflict(clause)
        if "开" in clause and not on:
            on = True

        for device_type in types:
            result = self._build_actions_for_type(
                device_type, clause, compact, room, global_scope, specific_id,
                last_devices, on, off,
            )
            if result is None:
                continue
            clause_actions, clarify = result
            actions.extend(clause_actions)
            if clarify:
                return actions, clarify
        if not actions:
            return None
        return actions, None

    @staticmethod
    def _has_any(text: str, words: list[str]) -> bool:
        return any(word in text for word in words)

    @staticmethod
    def _has_open_close_conflict(text: str) -> bool:
        return any(word in text for word in ["拉开", "打开", "开启"]) and any(
            word in text for word in ["拉上", "合上", "关闭", "关上"]
        )

    def _infer_type_from_keywords(self, clause: str, last_devices: list[str]) -> str | None:
        if any(word in clause for word in ["亮一点", "亮一些", "暗一点", "暗一些", "调亮", "调暗", "太亮", "太暗", "亮度"]):
            return "light"
        if any(word in clause for word in ["温度", "太热", "太冷", "冷一点", "热一点", "制冷", "制热", "除湿", "风速"]):
            return "ac"
        if any(word in clause for word in ["音量", "声音", "大一点", "小一点", "播放", "音乐", "新闻", "白噪音", "冥想"]):
            return "speaker"
        if any(word in clause for word in ["湿度", "加湿"]):
            return "humidifier"
        if any(word in clause for word in ["扫地", "清扫", "回充"]):
            return "vacuum"
        if any(word in clause for word in ["它", "那个", "这个", "再", "继续"]):
            for device_id in last_devices:
                try:
                    return self.registry.get(device_id)["type"]
                except DeviceError:
                    continue
        return None

    def _build_actions_for_type(
        self,
        device_type: str,
        clause: str,
        compact: str,
        room: str | None,
        global_scope: bool,
        specific_id: str | None,
        last_devices: list[str],
        on: bool,
        off: bool,
    ) -> tuple[list[Action], ParsedIntent | None] | None:
        if specific_id:
            try:
                if self.registry.get(specific_id)["type"] != device_type:
                    specific_id = None
            except DeviceError:
                specific_id = None
        targets, candidates, reason = self._resolve_targets(
            device_type, room, global_scope or self._global_for_type(device_type, clause, room),
            specific_id, clause, last_devices, off=off,
        )

        if reason == "ambiguous" and candidates:
            intent = self._intent_for_basic(device_type, on, off)
            pending = {
                "kind": "choice",
                "intent": intent,
                "params": self._basic_params(device_type, on, off),
                "device_type": device_type,
                "candidates": [
                    {"id": candidate["id"], "name": candidate["name"], "room": candidate["room"]}
                    for candidate in candidates
                ],
            }
            clarify = ParsedIntent(
                intent_type=CLARIFY,
                intent=intent,
                confidence=0.6,
                source="rule",
                clarify=f"你想控制哪一台{TYPE_LABELS.get(device_type, device_type)}？",
                options=[
                    {"label": f"{candidate['name']}", "device_id": candidate["id"]}
                    for candidate in candidates
                ],
                pending=pending,
                room=room,
            )
            return [], clarify
        if not targets:
            return None

        actions_by_device: list[Action] = []
        for device_id in targets:
            try:
                device = self.registry.get(device_id)
            except DeviceError:
                continue
            action = self._action_for_device(device, clause, compact, on, off)
            if action:
                actions_by_device.append(action)
        if not actions_by_device:
            return None
        return actions_by_device, None

    @staticmethod
    def _global_for_type(device_type: str, clause: str, room: str | None) -> bool:
        if device_type == "light" and not room:
            return any(word in clause for word in ["把灯全", "所有灯", "全部灯", "全屋的灯", "灯都", "都关", "都开"])
        return False

    def _resolve_targets(
        self,
        device_type: str,
        room: str | None,
        global_scope: bool,
        specific_id: str | None,
        clause: str,
        last_devices: list[str],
        *,
        off: bool = False,
    ) -> tuple[list[str], list[dict[str, Any]], str]:
        all_devices = self.registry.find(device_type=device_type)
        if not all_devices:
            return [], [], "none"
        candidates = [d for d in all_devices if (not room or d["room_id"] == room)]
        if specific_id:
            specific = [d for d in candidates if d["id"] == specific_id]
            if specific:
                return [specific_id], [], "specific"
        if global_scope:
            return [d["id"] for d in candidates], [], "global"
        if room:
            if len(candidates) == 1:
                return [candidates[0]["id"]], [], "room"
            if device_type == "light":
                primary = self._primary_light(candidates, clause)
                return [primary["id"]], [], "primary"
            return [d["id"] for d in candidates], [], "room-all"
        if len(candidates) == 1:
            return [candidates[0]["id"]], [], "unique"

        context_target = self._context_device(device_type, last_devices, candidates)
        if context_target:
            return [context_target["id"]], [], "context"

        if device_type == "light":
            if off:
                on_lights = [d for d in candidates if d["properties"].get("power")]
                if on_lights:
                    return [d["id"] for d in on_lights], [], "all-on"
                return [d["id"] for d in candidates], [], "all"
            primary = self._primary_light(candidates, clause)
            return [primary["id"]], [], "default"
        if device_type == "vacuum" or device_type == "purifier" or device_type == "humidifier" or device_type == "socket" or device_type == "speaker":
            return [candidates[0]["id"]], [], "default"
        return [], candidates, "ambiguous"

    @staticmethod
    def _primary_light(candidates: list[dict[str, Any]], clause: str) -> dict[str, Any]:
        if "主灯" in clause or "吸顶灯" in clause:
            for device in candidates:
                if "吸顶灯" in device["name"] or "主灯" in device["name"]:
                    return device
        if "灯带" in clause or "氛围" in clause:
            for device in candidates:
                if "氛围" in device["name"] or "灯带" in device["name"]:
                    return device
        for device in candidates:
            if "吸顶灯" in device["name"] or "主灯" in device["name"]:
                return device
        return candidates[0]

    @staticmethod
    def _context_device(
        device_type: str, last_devices: list[str], candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        candidate_ids = {device["id"] for device in candidates}
        for device_id in reversed(last_devices):
            if device_id in candidate_ids:
                for device in candidates:
                    if device["id"] == device_id:
                        return device
        return None

    def _action_for_device(
        self, device: dict[str, Any], clause: str, compact: str, on: bool, off: bool,
    ) -> Action | None:
        device_type = device["type"]
        props = device["properties"]
        name = device["name"]

        if device_type == "light":
            brightness = extract_number(clause, percent=True)
            color_temp = _color_temp(clause)
            up = any(word in clause for word in ["亮一点", "亮一些", "调亮", "太暗", "再亮"])
            down = any(word in clause for word in ["暗一点", "暗一些", "调暗", "太亮", "再暗"])
            if brightness is None and any(word in clause for word in ["亮度", "调到"]):
                brightness = extract_number(clause)
            if off:
                return Action("light_off", [device["id"]], {"power": False}, f"关闭{name}")

            params: dict[str, Any] = {}
            labels: list[str] = []
            if brightness is not None and 1 <= brightness <= 100:
                params["brightness"] = brightness
                labels.append(f"亮度{brightness}%")
            elif up or down:
                current = int(props.get("brightness", 60))
                params["brightness"] = min(100, current + 10) if up else max(1, current - 10)
                labels.append(f"亮度{params['brightness']}%")
            if color_temp:
                params["color_temp"] = color_temp
                labels.append(f"色温{color_temp}K")
            if params:
                params["power"] = True
                intent = "light_brightness_set" if "brightness" in params else "light_color_set"
                if up:
                    intent = "light_brightness_up"
                elif down:
                    intent = "light_brightness_down"
                return Action(intent, [device["id"]], params, f"{name}{'，'.join(labels)}")
            if on:
                return Action("light_on", [device["id"]], {"power": True}, f"打开{name}")
            return None

        if device_type == "ac":
            temperature = extract_number(clause, temperature=True)
            if temperature is None and any(word in clause for word in ["温度", "度", "调到", "设成", "设为"]):
                temperature = extract_number(clause)
            mode = _ac_mode(clause)
            fan = _fan_speed(clause)
            up = any(word in clause for word in ["调高", "升高", "热一点", "太冷", "高一点", "高两度"])
            down = any(word in clause for word in ["调低", "降低", "冷一点", "太热", "低一点", "低两度"])
            if off:
                return Action("ac_off", [device["id"]], {"power": False}, f"关闭{name}")
            params: dict[str, Any] = {}
            if temperature is not None and 16 <= temperature <= 30:
                params["target_temp"] = temperature
            elif up or down:
                current = int(props.get("target_temp", 26))
                params["target_temp"] = min(30, current + 1) if up else max(16, current - 1)
            if mode:
                params["mode"] = mode
            if fan:
                params["fan_speed"] = fan
            if params:
                params["power"] = True
                intent = "ac_temp_set" if "target_temp" in params else ("ac_mode_set" if mode else "ac_fan_set")
                label_parts = []
                if "target_temp" in params:
                    label_parts.append(f"{params['target_temp']}°C")
                if mode:
                    label_parts.append({"cool": "制冷", "heat": "制热", "dry": "除湿", "fan": "送风", "auto": "自动"}[mode])
                if fan:
                    label_parts.append({"low": "低风", "medium": "中风", "high": "高风", "auto": "自动风"}[fan])
                return Action(intent, [device["id"]], params, f"{name}调至{'，'.join(label_parts)}")
            if on:
                return Action("ac_on", [device["id"]], {"power": True}, f"打开{name}")
            return None

        if device_type == "curtain":
            position = extract_number(clause, percent=True)
            if position is None:
                if "一半" in clause or "半开" in clause:
                    position = 50
                elif extract_number(clause) is not None:
                    position = extract_number(clause)
            if position is None:
                if any(word in clause for word in CLOSE_WORDS):
                    position = 0
                elif any(word in clause for word in OPEN_WORDS + ["窗帘"]):
                    position = 100
            if position is None:
                return None
            position = max(0, min(100, int(position)))
            intent = "curtain_close" if position == 0 else ("curtain_open" if position == 100 else "curtain_position_set")
            label = "合上" if position == 0 else ("完全打开" if position == 100 else f"开到{position}%")
            return Action(intent, [device["id"]], {"position": position}, f"{name}{label}")
        if device_type == "purifier":
            if off:
                return Action("purifier_off", [device["id"]], {"power": False}, f"关闭{name}")
            mode = None
            if "睡眠" in clause:
                mode = "sleep"
            elif "强力" in clause or "最大" in clause:
                mode = "high"
            elif "自动" in clause:
                mode = "auto"
            if mode:
                return Action("purifier_mode", [device["id"]], {"power": True, "mode": mode}, f"{name}切换到{mode}模式")
            if on:
                return Action("purifier_on", [device["id"]], {"power": True}, f"打开{name}")
            return None

        if device_type == "humidifier":
            humidity = extract_number(clause, percent=True)
            if humidity is None and "湿度" in clause:
                humidity = extract_number(clause)
            if off:
                return Action("humidifier_off", [device["id"]], {"power": False}, f"关闭{name}")
            if humidity is not None:
                return Action(
                    "humidifier_humidity", [device["id"]],
                    {"power": True, "target_humidity": max(30, min(80, humidity))},
                    f"{name}目标湿度{humidity}%",
                )
            if on:
                return Action("humidifier_on", [device["id"]], {"power": True}, f"打开{name}")
            return None

        if device_type == "socket":
            if off or any(word in clause for word in ["断电", "关"]):
                return Action("socket_off", [device["id"]], {"power": False}, f"{name}断电")
            if on or any(word in clause for word in ["通电", "开", "打开"]):
                return Action("socket_on", [device["id"]], {"power": True}, f"{name}通电")
            return None

        if device_type == "speaker":
            volume = extract_number(clause, percent=True)
            if volume is None and any(word in clause for word in ["音量", "声音"]):
                volume = extract_number(clause)
            up = any(word in clause for word in ["大一点", "大一些", "调大", "大声"])
            down = any(word in clause for word in ["小一点", "小一些", "调小", "小声", "安静"])
            track = _track(clause)
            if off:
                return Action("speaker_off", [device["id"]], {"power": False, "playing": False}, f"关闭{name}")
            if "暂停" in clause or "别放" in clause:
                return Action("speaker_pause", [device["id"]], {"playing": False}, f"暂停{name}")
            track = track or ("轻音乐" if "播放" in clause or "放点" in clause or "放一首" in clause else None)
            if volume is not None and 0 <= volume <= 100:
                params = {"volume": volume, "power": True}
                if track:
                    params.update({"playing": True, "track": track})
                    return Action("speaker_play", [device["id"]], params, f"{name}播放{track}，音量{volume}%")
                return Action("speaker_volume", [device["id"]], {"volume": volume, "power": True}, f"{name}音量调到{volume}%")
            if up or down:
                current = int(props.get("volume", 30))
                value = min(100, current + 10) if up else max(0, current - 10)
                return Action("speaker_volume", [device["id"]], {"volume": value, "power": True}, f"{name}音量调到{value}%")
            if track:
                return Action("speaker_play", [device["id"]], {"power": True, "playing": True, "track": track}, f"{name}播放{track}")
            if on:
                return Action("speaker_on", [device["id"]], {"power": True}, f"打开{name}")
            return None

        if device_type == "vacuum":
            if any(word in clause for word in ["回充", "充电", "回座", "停止", "停下", "别扫"]):
                return Action("vacuum_dock", [device["id"]], {"power": False}, f"{name}返回充电座")
            mode = "auto"
            if "拖地" in clause:
                mode = "mop"
            elif "定点" in clause:
                mode = "spot"
            elif "沿边" in clause or "边角" in clause:
                mode = "edge"
            if any(word in clause for word in ["清扫", "扫地", "打扫", "启动", "开始扫"]):
                return Action("vacuum_start", [device["id"]], {"power": True, "mode": mode}, f"{name}开始清扫")
            if off:
                return Action("vacuum_dock", [device["id"]], {"power": False}, f"{name}停止清扫")
            return None

        return None

    @staticmethod
    def _basic_params(device_type: str, on: bool, off: bool) -> dict[str, Any]:
        if device_type == "curtain":
            return {"position": 0 if off else 100}
        if device_type in {"light", "ac", "purifier", "humidifier", "socket", "speaker", "vacuum"}:
            return {"power": False if off else True}
        return {}

    def _intent_for_basic(self, device_type: str, on: bool, off: bool) -> str:
        suffix = "off" if off else "on"
        if device_type == "vacuum" and not off:
            return "vacuum_start"
        return f"{device_type}_{suffix}"

    # -------------------------------------------------------------- pending
    def _resolve_pending(
        self, raw: str, compact: str, pending: dict[str, Any], last_devices: list[str],
    ) -> ParsedIntent | None:
        if any(word in raw for word in ["取消", "算了", "不用了", "没事"]):
            return self._chat("好的，已取消。", confidence=0.8)
        kind = pending.get("kind")
        if kind == "choice":
            candidates = pending.get("candidates", [])
            selected = self._select_candidate(raw, compact, candidates)
            if not selected:
                # A brand-new command abandons the pending clarification.
                if any(word in raw for word in ON_WORDS + OFF_WORDS + ["调到", "打开", "关闭", "开启"]):
                    return None
                return ParsedIntent(
                    intent_type=CLARIFY,
                    intent=pending.get("intent", ""),
                    confidence=0.5,
                    source="rule",
                    clarify="我还是没确认是哪一台，你直接说房间或设备名就好。",
                    options=[
                        {"label": candidate["name"], "device_id": candidate["id"]}
                        for candidate in candidates
                    ],
                    pending=pending,
                )
            device = self.registry.get(selected["id"])
            intent = pending.get("intent", "")
            params = dict(pending.get("params", {}))
            # Recompute directional values against the chosen device.
            if intent in {"light_brightness_up", "light_brightness_down", "ac_temp_up", "ac_temp_down"}:
                if "light" in intent:
                    current = int(device["properties"].get("brightness", 60))
                    params["brightness"] = min(100, current + 10) if intent.endswith("up") else max(1, current - 10)
                else:
                    current = int(device["properties"].get("target_temp", 26))
                    params["target_temp"] = min(30, current + 1) if intent.endswith("up") else max(16, current - 1)
            action = Action(intent, [device["id"]], params, f"{device['name']}已选择")
            return ParsedIntent(
                intent_type=CONTROL,
                intent=intent,
                confidence=0.9,
                source="rule-pending",
                actions=[action],
                targets=[device["id"]],
                slots=params,
            )
        if kind == "value":
            value = extract_number(raw) if any(char.isdigit() for char in raw) else None
            if value is None:
                return None
            slot = pending.get("slot", "target_temp")
            minimum, maximum = pending.get("min", 0), pending.get("max", 100)
            value = max(minimum, min(maximum, value))
            action = Action(
                pending.get("intent", "set_device"),
                pending.get("device_ids", []),
                {slot: value, "power": True},
                f"设置{slot}为{value}",
            )
            return ParsedIntent(
                intent_type=CONTROL,
                intent=pending.get("intent", "set_device"),
                confidence=0.9,
                source="rule-pending",
                actions=[action],
                targets=action.device_ids,
                slots={slot: value},
            )
        return None

    @staticmethod
    def _select_candidate(
        raw: str, compact: str, candidates: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        ordinal_map = {"第一": 0, "第二": 1, "第三": 2, "1": 0, "2": 1, "3": 2}
        for token, index in ordinal_map.items():
            if token in raw and index < len(candidates):
                return candidates[index]
        for candidate in candidates:
            if candidate["name"] in raw or candidate["room"] in raw:
                return candidate
        if any(word in raw for word in ["都", "全部", "所有"]):
            return None
        return None

    # ------------------------------------------------------------- RAG assist
    def _rag_assist(
        self,
        raw: str,
        compact: str,
        retrieved: list[dict[str, Any]],
        last_devices: list[str],
    ) -> ParsedIntent | None:
        top = next((hit for hit in retrieved if hit.get("kind") == "intent"), None)
        if not top or float(top.get("score") or 0) < 0.42:
            return None
        intent = top.get("intent", "")
        device_type = top.get("device_type") or ""
        if intent in {"ambiguous"} or intent.startswith("smalltalk"):
            return None
        if intent.startswith("scene_"):
            scene = next((s for s in self.scenes if s["id"] == intent), None)
            if scene:
                return ParsedIntent(
                    intent_type=SCENE, intent=intent, confidence=0.65, source="rag",
                    scene_id=intent, slots={"scene_name": scene["name"]},
                )
        if intent.startswith("query_"):
            room = detect_room(raw)
            return ParsedIntent(
                intent_type=QUERY, intent=intent, confidence=0.55, source="rag",
                actions=[Action(intent, [], {"room": room} if room else {})],
            )
        if not device_type:
            return None
        # Reuse the structured control parser with the RAG-suggested type.
        on = self._has_any(raw, ON_WORDS)
        off = self._has_any(raw, OFF_WORDS) and not self._has_open_close_conflict(raw)
        room = detect_room(raw)
        specific_id, _ = detect_specific(raw, self.registry)
        result = self._build_actions_for_type(
            device_type, raw, compact, room, detect_global(raw), specific_id,
            last_devices, on, off,
        )
        if not result:
            return None
        actions, clarify = result
        if clarify:
            clarify.confidence = 0.55
            return clarify
        if not actions:
            return None
        return ParsedIntent(
            intent_type=CONTROL, intent=actions[0].intent, confidence=0.58, source="rag",
            actions=actions, targets=[d for action in actions for d in action.device_ids],
            slots={k: v for action in actions for k, v in action.params.items()},
        )

    @staticmethod
    def _merge_actions(actions: list[Action]) -> list[Action]:
        merged: dict[tuple[str, tuple[str, ...]], Action] = {}
        for action in actions:
            key = (action.intent, tuple(action.device_ids))
            if key not in merged:
                merged[key] = action
            else:
                merged[key].params.update(action.params)

        param_intents = {
            "light_brightness_set", "light_color_set",
            "light_brightness_up", "light_brightness_down",
            "ac_temp_set", "ac_temp_up", "ac_temp_down", "ac_mode_set", "ac_fan_set",
            "curtain_position_set", "purifier_mode", "humidifier_humidity",
            "speaker_play", "speaker_volume", "vacuum_start",
        }
        power_intents = {
            "light_on", "ac_on", "purifier_on", "humidifier_on",
            "socket_on", "speaker_on", "curtain_open",
        }
        # A pure "turn on" is redundant when the same utterance already carries
        # a parameter for that device (e.g. 打开客厅主灯，亮度调到 80%）。
        coalesced: list[Action] = []
        for action in merged.values():
            if action.intent in power_intents:
                has_detail = any(
                    other.intent in param_intents
                    and other.device_ids == action.device_ids
                    for other in merged.values()
                )
                if has_detail:
                    continue
            if action.intent in param_intents:
                if action.intent.startswith("curtain_"):
                    pass
                else:
                    action.params.setdefault("power", True)
            coalesced.append(action)
        # Keep a stable order while dropping duplicate exact intents created by
        # different clauses that pointed at the same device.
        seen: set[tuple[str, tuple[str, ...]]] = set()
        result: list[Action] = []
        for action in coalesced:
            key = (action.intent, tuple(action.device_ids))
            if key in seen:
                continue
            seen.add(key)
            result.append(action)

        # Merge compatible parameter actions that touch the same single device
        # (播放轻音乐 + 音量 40%，亮度 + 色温，温度 + 模式 ...).
        groups: dict[str, list[Action]] = {}
        for action in result:
            if len(action.device_ids) == 1 and action.intent in param_intents:
                groups.setdefault(action.device_ids[0], []).append(action)
        preferred = {
            "speaker_play", "vacuum_start", "light_brightness_set",
            "ac_temp_set", "curtain_position_set", "purifier_mode", "humidifier_humidity",
        }
        dropped: set[int] = set()
        for group in groups.values():
            if len(group) < 2:
                continue
            primary = next((item for item in group if item.intent in preferred), group[0])
            for other in group:
                if other is primary:
                    continue
                primary.params.update(other.params)
                if other.intent in preferred and primary.intent not in preferred:
                    primary.intent = other.intent
                if other.label:
                    primary.label = OfflineNLU._join_labels(primary.label, other.label)
                dropped.add(id(other))
        return [action for action in result if id(action) not in dropped]

    @staticmethod
    def _join_labels(first: str, second: str) -> str:
        if not first:
            return second
        if not second:
            return first
        common = 0
        for left, right in zip(first, second):
            if left != right:
                break
            common += 1
        if common >= 2:
            return f"{first[:common]}{first[common:]}，{second[common:]}"
        return f"{first}，{second}"

    @staticmethod
    def _name(device_id: str) -> str:
        return device_id

    def _client_device(self, device_id: str) -> dict[str, Any] | None:
        try:
            return self.registry.get(device_id)
        except DeviceError:
            return None


def normalize_llm_result(
    data: dict[str, Any],
    *,
    registry: DeviceRegistry,
    scenes: list[dict[str, Any]],
    retrieved: list[dict[str, Any]],
    user_input: str,
) -> ParsedIntent | None:
    """Validate LLM JSON and convert it into the same ParsedIntent structure."""
    if not isinstance(data, dict):
        return None
    intent_type = str(data.get("intent_type", "")).strip().lower()
    if intent_type not in {CONTROL, QUERY, SCENE, CHAT, KNOWLEDGE, CLARIFY}:
        return None
    confidence = data.get("confidence", 0.7)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.7
    actions: list[Action] = []
    targets: list[str] = []
    raw_actions = data.get("actions") or []
    if isinstance(raw_actions, dict):
        raw_actions = [raw_actions]
    for raw_action in raw_actions if isinstance(raw_actions, list) else []:
        if not isinstance(raw_action, dict):
            continue
        device_ids = raw_action.get("device_ids") or []
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        valid_ids = []
        for device_id in device_ids:
            try:
                registry.get(str(device_id))
                valid_ids.append(str(device_id))
            except DeviceError:
                continue
        params = raw_action.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        actions.append(Action(
            intent=str(raw_action.get("intent", data.get("intent", ""))),
            device_ids=valid_ids,
            params=params,
            label=str(raw_action.get("label", "")),
        ))
        targets.extend(valid_ids)
    if intent_type == CONTROL and (not actions or not any(a.device_ids for a in actions)):
        return None
    if intent_type == QUERY and not actions:
        intent = str(data.get("intent", ""))
        if intent == "query_environment":
            actions = [Action("query_environment", [], {})]
        elif intent in {"query_status", "query_device"}:
            actions = [Action("query_status" if intent == "query_status" else "query_device", [], {})]
        else:
            return None
    scene_id = data.get("scene_id") or None
    if intent_type == SCENE:
        scene = next((s for s in scenes if s["id"] == scene_id), None)
        if not scene:
            scene = next(
                (s for s in scenes if s["name"] in user_input or s["name"].replace("模式", "") in user_input),
                None,
            )
        if not scene:
            return None
        scene_id = scene["id"]
    options = data.get("options") or []
    if not isinstance(options, list):
        options = []
    pending = None
    if intent_type == CLARIFY and options:
        candidates = []
        for option in options:
            if not isinstance(option, dict):
                continue
            try:
                device = registry.get(str(option.get("device_id")))
            except DeviceError:
                continue
            candidates.append({"id": device["id"], "name": device["name"], "room": device["room"]})
        if candidates:
            first_intent = actions[0].intent if actions else str(data.get("intent", ""))
            pending = {
                "kind": "choice",
                "intent": first_intent,
                "params": actions[0].params if actions else {},
                "device_type": registry.get(candidates[0]["id"])["type"],
                "candidates": candidates,
            }
            options = [
                {"label": candidate["name"], "device_id": candidate["id"]}
                for candidate in candidates
            ]
    knowledge_hits = [hit for hit in retrieved if hit.get("kind") == "knowledge"][:3]
    return ParsedIntent(
        intent_type=intent_type,
        intent=str(data.get("intent", "")),
        confidence=confidence,
        source="llm",
        actions=actions,
        targets=list(dict.fromkeys(targets)),
        slots={key: value for action in actions for key, value in action.params.items()},
        scene_id=scene_id,
        direct_reply=(data.get("direct_reply") or None),
        clarify=(data.get("clarify") or None),
        options=options,
        pending=pending,
        knowledge=knowledge_hits if intent_type == KNOWLEDGE else [],
        room=detect_room(user_input),
    )
