"""Unit tests for the deterministic offline NLU (no HTTP, no RAG)."""
from __future__ import annotations

from app.agent import nlu as nlu_module
from app.agent.nlu import OfflineNLU


def parse(nlu: OfflineNLU, text: str):
    return nlu.parse(text, retrieved=[], last_devices=[], pending=None)


def test_open_living_room_main_light(nlu: OfflineNLU) -> None:
    parsed = parse(nlu, "打开客厅主灯")

    assert parsed.intent_type == nlu_module.CONTROL
    assert parsed.intent == "light_on"
    assert parsed.targets == ["light_living_main"]
    assert len(parsed.actions) == 1
    assert parsed.actions[0].device_ids == ["light_living_main"]
    assert parsed.actions[0].params["power"] is True


def test_ac_temperature_without_room_asks_for_clarification(nlu: OfflineNLU) -> None:
    parsed = parse(nlu, "空调调到26度")

    assert parsed.intent_type == nlu_module.CLARIFY
    assert parsed.intent == "ac_on"
    assert parsed.pending is not None
    assert parsed.pending["kind"] == "choice"
    candidate_ids = {candidate["id"] for candidate in parsed.pending["candidates"]}
    assert candidate_ids == {"ac_living", "ac_bed"}
    assert {option["device_id"] for option in parsed.options} == {
        "ac_living", "ac_bed",
    }


def test_close_living_room_curtain_sets_position_zero(nlu: OfflineNLU) -> None:
    parsed = parse(nlu, "关闭客厅窗帘")

    assert parsed.intent_type == nlu_module.CONTROL
    assert parsed.targets == ["curtain_living"]
    assert parsed.intent == "curtain_close"
    assert parsed.actions[0].device_ids == ["curtain_living"]
    assert parsed.actions[0].params["position"] == 0


def test_all_lights_off_produces_multiple_light_off_actions(nlu: OfflineNLU) -> None:
    parsed = parse(nlu, "所有灯都关掉")

    assert parsed.intent_type == nlu_module.CONTROL
    assert len(parsed.actions) >= 2
    assert all(action.intent == "light_off" for action in parsed.actions)
    assert all(action.params["power"] is False for action in parsed.actions)
    assert "light_living_main" in parsed.targets
    assert len(parsed.targets) == len(set(parsed.targets))


def test_arrive_home_scene(nlu: OfflineNLU) -> None:
    parsed = parse(nlu, "开启回家模式")

    assert parsed.intent_type == nlu_module.SCENE
    assert parsed.intent == "scene_arrive"
    assert parsed.scene_id == "scene_arrive"


def test_at_home_alias_matches_arrive_scene(nlu: OfflineNLU) -> None:
    parsed = parse(nlu, "开启居家模式")

    assert parsed.intent_type == nlu_module.SCENE
    assert parsed.intent == "scene_arrive"
    assert parsed.scene_id == "scene_arrive"


def test_ac_energy_question_is_knowledge_not_device_query(nlu: OfflineNLU) -> None:
    parsed = parse(nlu, "空调多少度最省电")

    assert parsed.intent_type == nlu_module.KNOWLEDGE
    assert parsed.intent_type != nlu_module.QUERY
    assert not parsed.intent.startswith("query_")
