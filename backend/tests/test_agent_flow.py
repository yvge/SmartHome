"""End-to-end Agent / SSE tests using the real app lifespan and LangGraphs."""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import (
    assert_event_order,
    events_of,
    last_event,
    stream_events,
)


def test_chat_stream_control_command(client: TestClient) -> None:
    events = stream_events(
        client,
        "POST",
        "/api/v1/chat/stream",
        json={"message": "打开客厅主灯"},
    )

    assert_event_order(
        events, ["run_start", "intent", "tool_result", "response", "done"]
    )

    intent = last_event(events, "intent")
    assert intent is not None
    assert intent["intent"]["intent_type"] == "control"
    assert "light_living_main" in intent["intent"]["targets"]

    tool_result = last_event(events, "tool_result")
    assert tool_result is not None
    assert tool_result["ok"] is True

    response = last_event(events, "response")
    assert response is not None
    assert response["content"].strip()

    done = last_event(events, "done")
    assert done is not None
    assert done["status"] == "success"
    assert done["execution_id"].startswith("exec_")


def test_chat_stream_scene_command(client: TestClient) -> None:
    events = stream_events(
        client,
        "POST",
        "/api/v1/chat/stream",
        json={"message": "开启观影模式"},
    )

    assert_event_order(
        events, ["run_start", "intent", "scene_done", "response", "done"]
    )

    intent = last_event(events, "intent")
    assert intent is not None
    assert intent["intent"]["intent_type"] == "scene"
    assert intent["intent"]["scene_id"] == "scene_movie"

    scene_done = last_event(events, "scene_done")
    assert scene_done is not None
    assert scene_done["result"]["status"] == "success"

    response = last_event(events, "response")
    assert response is not None
    assert response["content"].strip()

    done = last_event(events, "done")
    assert done is not None
    assert done["status"] == "success"


def test_scene_run_stream_all_steps_ok(client: TestClient) -> None:
    scene = client.get("/api/v1/scenes/scene_movie").json()["scene"]
    events = stream_events(client, "POST", "/api/v1/scenes/scene_movie/run")

    assert_event_order(
        events, ["run_start", "scene_start", "scene_step_result", "scene_done", "done"]
    )

    step_results = events_of(events, "scene_step_result")
    assert len(step_results) == len(scene["steps"])
    assert all(result["ok"] is True for result in step_results)

    scene_done = last_event(events, "scene_done")
    assert scene_done is not None
    assert scene_done["result"]["status"] == "success"

    done = last_event(events, "done")
    assert done is not None
    assert done["status"] == "success"


def test_scene_run_falls_back_when_critical_device_offline(client: TestClient) -> None:
    offline = client.post(
        "/api/v1/devices/light_living_main/connectivity",
        json={"online": False},
    )
    assert offline.status_code == 200

    events = stream_events(client, "POST", "/api/v1/scenes/scene_arrive/run")

    fallback = last_event(events, "scene_fallback")
    assert fallback is not None
    assert fallback["actions"]

    scene_done = last_event(events, "scene_done")
    assert scene_done is not None
    result = scene_done["result"]
    assert result["status"] in {"partial", "failed"}
    assert result["fallback_used"] is True

    done = last_event(events, "done")
    assert done is not None
    assert done["status"] in {"partial", "failed"}


def test_execution_history_and_detail(client: TestClient) -> None:
    events = stream_events(
        client,
        "POST",
        "/api/v1/chat/stream",
        json={"message": "打开客厅主灯"},
    )
    done = last_event(events, "done")
    assert done is not None
    execution_id = done["execution_id"]

    listing = client.get("/api/v1/system/executions")
    assert listing.status_code == 200
    executions = listing.json()["executions"]
    assert executions
    row = next((item for item in executions if item["id"] == execution_id), None)
    assert row is not None
    assert row["kind"] == "chat"
    assert row["status"] == "success"

    detail = client.get(f"/api/v1/system/executions/{execution_id}")
    assert detail.status_code == 200
    execution = detail.json()["execution"]
    assert execution["id"] == execution_id
    assert execution["input"] == "打开客厅主灯"
    assert execution["result"]["response"].strip()
    assert execution["tool_calls"]
