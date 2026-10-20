"""Scene library / orchestration endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.runtime import AppRuntime
from app.schemas import ScenePayload
from app.services.scene_manager import (
    SceneValidationError,
    create_scene,
    delete_scene,
    duplicate_scene,
    update_scene,
)
from app.services.scene_service import SceneService

router = APIRouter(prefix="/scenes", tags=["scenes"])

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


@router.get("", summary="场景列表")
async def list_scenes(request: Request) -> dict:
    runtime = _runtime(request)
    scenes = runtime.db.load_scenes()
    for scene in scenes:
        scene["step_count"] = len(scene.get("steps", []))
        scene["fallback_count"] = len(scene.get("fallback", []))
    return {"scenes": scenes}


@router.get("/{scene_id}", summary="场景详情")
async def get_scene(scene_id: str, request: Request) -> dict:
    runtime = _runtime(request)
    scene = runtime.db.get_scene(scene_id)
    if not scene:
        raise HTTPException(404, "场景不存在")
    return {"scene": scene}


@router.post("", summary="创建自定义场景")
async def post_scene(payload: ScenePayload, request: Request) -> dict:
    runtime = _runtime(request)
    try:
        scene = create_scene(runtime, payload)
        return {"scene": scene}
    except SceneValidationError as exc:
        raise HTTPException(422, exc.message) from exc


@router.put("/{scene_id}", summary="更新自定义场景")
async def put_scene(scene_id: str, payload: ScenePayload, request: Request) -> dict:
    runtime = _runtime(request)
    try:
        scene = update_scene(runtime, scene_id, payload)
        return {"scene": scene}
    except SceneValidationError as exc:
        raise HTTPException(422, exc.message) from exc


@router.delete("/{scene_id}", summary="删除自定义场景")
async def remove_scene(scene_id: str, request: Request) -> dict:
    runtime = _runtime(request)
    try:
        delete_scene(runtime, scene_id)
        return {"ok": True}
    except SceneValidationError as exc:
        raise HTTPException(422, exc.message) from exc


@router.post("/{scene_id}/duplicate", summary="复制场景")
async def copy_scene(scene_id: str, request: Request) -> dict:
    runtime = _runtime(request)
    try:
        scene = duplicate_scene(runtime, scene_id)
        return {"scene": scene}
    except SceneValidationError as exc:
        raise HTTPException(422, exc.message) from exc


@router.post("/{scene_id}/run", summary="执行场景（SSE 流式）")
async def run_scene(scene_id: str, request: Request, session_id: str | None = None):
    runtime = _runtime(request)
    scene = runtime.db.get_scene(scene_id)
    if not scene:
        raise HTTPException(404, "场景不存在")
    if not scene.get("enabled", True):
        raise HTTPException(409, "场景已停用")
    service = SceneService(runtime)
    return StreamingResponse(
        service.stream(scene, session_id=session_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
