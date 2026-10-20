"""REST API tests: health, devices, scenes and RAG knowledge base."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings


def test_health_returns_ok(client: TestClient, settings: Settings) -> None:
    runtime = client.app.state.runtime
    assert runtime.db.path == settings.db_path

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["llm"]["enabled"] is False
    assert body["rag_backend"] == "local"


def test_patch_device_property_success_and_clamp(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/devices/light_living_main",
        json={"properties": {"brightness": 75}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["device"]["properties"]["brightness"] == 75

    response = client.patch(
        "/api/v1/devices/light_living_main",
        json={"properties": {"brightness": 999}},
    )
    assert response.status_code == 200
    assert response.json()["device"]["properties"]["brightness"] == 100

    detail = client.get("/api/v1/devices/light_living_main")
    assert detail.status_code == 200
    assert detail.json()["device"]["properties"]["brightness"] == 100


def test_patch_light_with_unsupported_parameter_returns_422(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/devices/light_living_main",
        json={"properties": {"target_temp": 26}},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_PARAM"
    assert detail["device_id"] == "light_living_main"


def test_patch_offline_device_returns_409(client: TestClient) -> None:
    response = client.post(
        "/api/v1/devices/light_living_main/connectivity",
        json={"online": False},
    )
    assert response.status_code == 200
    assert response.json()["device"]["online"] is False

    response = client.patch(
        "/api/v1/devices/light_living_main",
        json={"properties": {"power": True}},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "OFFLINE"
    assert detail["device_id"] == "light_living_main"


def _custom_scene_payload() -> dict:
    return {
        "name": "睡前阅读模式",
        "description": "床头灯 40% 暖光",
        "icon": "book-open",
        "steps": [
            {
                "device_id": "light_bed_bedside",
                "params": {"power": True, "brightness": 40},
                "label": "打开主卧床头灯",
            }
        ],
    }


def test_custom_scene_create_list_duplicate_delete(client: TestClient) -> None:
    created = client.post("/api/v1/scenes", json=_custom_scene_payload())
    assert created.status_code == 200
    scene = created.json()["scene"]
    scene_id = scene["id"]
    assert scene_id.startswith("scene_custom_")
    assert scene["name"] == "睡前阅读模式"
    assert scene["builtin"] is False
    assert len(scene["steps"]) == 1

    listing = client.get("/api/v1/scenes").json()["scenes"]
    listed = next((row for row in listing if row["id"] == scene_id), None)
    assert listed is not None
    assert listed["step_count"] == 1

    duplicated = client.post(f"/api/v1/scenes/{scene_id}/duplicate")
    assert duplicated.status_code == 200
    copy = duplicated.json()["scene"]
    assert copy["id"] != scene_id
    assert copy["builtin"] is False
    assert "副本" in copy["name"]

    deleted = client.delete(f"/api/v1/scenes/{scene_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    remaining = client.get("/api/v1/scenes").json()["scenes"]
    assert all(row["id"] != scene_id for row in remaining)


def test_delete_builtin_scene_returns_422(client: TestClient) -> None:
    response = client.delete("/api/v1/scenes/scene_arrive")

    assert response.status_code == 422
    assert "内置场景不可删除" in response.json()["detail"]
    assert client.get("/api/v1/scenes/scene_arrive").status_code == 200


def test_rag_search_returns_hits(client: TestClient) -> None:
    response = client.post(
        "/api/v1/rag/search",
        json={"query": "空调调高一点", "top_k": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["backend"] == "local"
    assert body["hits"]
    assert all(hit["text"] for hit in body["hits"])


def test_rag_add_entry_increments_stats_count(client: TestClient) -> None:
    before = client.get("/api/v1/rag/stats").json()["count"]

    response = client.post(
        "/api/v1/rag/entries",
        json={
            "kind": "knowledge",
            "text": "测试知识：空调滤网多久清洗一次",
            "intent": "knowledge_test_filter",
            "category": "maintenance",
            "answer": "建议每两周清洗一次滤网，换季前做一次深度清洁。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entry"]["id"].startswith("kb_custom_")
    assert body["stats"]["count"] == before + 1

    after = client.get("/api/v1/rag/stats").json()["count"]
    assert after == before + 1
