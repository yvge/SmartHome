"""Device REST endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.devices.registry import DeviceError
from app.runtime import AppRuntime
from app.schemas import ConnectivityPatch, DevicePatch

router = APIRouter(prefix="/devices", tags=["devices"])

STATUS_BY_CODE = {
    "NOT_FOUND": 404,
    "OFFLINE": 409,
    "READ_ONLY": 403,
    "INVALID_PARAM": 422,
    "INVALID_VALUE": 422,
    "EMPTY_COMMAND": 422,
}


def _runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


def _raise(exc: DeviceError) -> None:
    raise HTTPException(
        status_code=STATUS_BY_CODE.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message, "device_id": exc.device_id},
    )


@router.get("", summary="设备列表与家庭快照")
async def list_devices(request: Request) -> dict:
    runtime = _runtime(request)
    snapshot = runtime.snapshot()
    return snapshot


@router.get("/{device_id}", summary="设备详情")
async def get_device(device_id: str, request: Request) -> dict:
    runtime = _runtime(request)
    try:
        return {"device": runtime.devices.get(device_id)}
    except DeviceError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.patch("/{device_id}", summary="控制设备属性")
async def patch_device(device_id: str, payload: DevicePatch, request: Request) -> dict:
    runtime = _runtime(request)
    try:
        device = runtime.devices.apply(device_id, payload.properties)
        return {"ok": True, "device": device}
    except DeviceError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post("/{device_id}/connectivity", summary="模拟设备离线/上线")
async def set_connectivity(
    device_id: str, payload: ConnectivityPatch, request: Request,
) -> dict:
    runtime = _runtime(request)
    try:
        device = runtime.devices.set_online(device_id, payload.online)
        return {"ok": True, "device": device}
    except DeviceError as exc:
        _raise(exc)
        raise  # pragma: no cover
