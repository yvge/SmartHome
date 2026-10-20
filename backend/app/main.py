"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import chat, devices, rag, scenes, system
from app.config import BASE_DIR, get_settings
from app.devices.registry import DeviceError
from app.runtime import AppRuntime

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("smarthome")


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = AppRuntime(settings)
    app.state.runtime = runtime
    await runtime.start()
    logger.info(
        "SmartHome AI Agent ready | LLM=%s | RAG=%s | http://127.0.0.1:8000",
        "enabled" if settings.llm_enabled else "offline-rules",
        runtime.rag.store.backend if runtime.rag.store else "none",
    )
    try:
        yield
    finally:
        await runtime.stop()


app = FastAPI(
    title="智慧居 · 智能家居 AI Agent 平台",
    description=(
        "FastAPI + SSE + RAG(Milvus) + LangGraph + Function Calling 的智能家居 Agent。\n\n"
        "- 自然语言 → 意图识别（Embedding + Milvus）→ JSON Schema 工具调用 → 设备执行\n"
        "- LangGraph 多步场景编排：条件判断、设备联动、动态路径与异常兜底\n"
        "- SSE 实时推送节点轨迹、工具调用、设备状态与生成回复"
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "chat", "description": "对话与流式执行轨迹"},
        {"name": "devices", "description": "设备状态与控制"},
        {"name": "scenes", "description": "场景编排与执行"},
        {"name": "rag", "description": "意图知识库与向量检索"},
        {"name": "system", "description": "系统状态、运行记录与实时事件"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=settings.cors_origin_list != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (chat.router, devices.router, scenes.router, rag.router, system.router):
    app.include_router(router, prefix=settings.api_prefix)


@app.exception_handler(DeviceError)
async def device_error_handler(request: Request, exc: DeviceError) -> JSONResponse:
    status = {
        "NOT_FOUND": 404,
        "OFFLINE": 409,
        "READ_ONLY": 403,
        "INVALID_PARAM": 422,
        "INVALID_VALUE": 422,
        "EMPTY_COMMAND": 422,
    }.get(exc.code, 400)
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": exc.code, "message": exc.message, "device_id": exc.device_id}},
    )


@app.get("/api/health", tags=["system"], summary="健康检查")
async def health() -> dict:
    runtime: AppRuntime = app.state.runtime
    return {
        "status": "ok" if runtime.started else "starting",
        "version": settings.app_version,
        "uptime_seconds": runtime.uptime_seconds,
        "llm": runtime.llm.status(),
        "rag_backend": runtime.rag.store.backend if runtime.rag.store else "none",
    }


@app.get(f"{settings.api_prefix}/health", tags=["system"], include_in_schema=False)
async def health_prefixed() -> dict:
    return await health()


frontend_dist = BASE_DIR.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "api": f"{settings.api_prefix}",
            "docs": "/docs",
            "frontend": "npm run dev (frontend/) or npm run build",
        }
