# syntax=docker/dockerfile:1
#
# 智慧居 · SmartHome AI Agent
# 多阶段构建：Node 构建前端 → Python 运行后端，并由 FastAPI 托管 frontend/dist
#
#   docker compose up -d --build
#

# ---------------------------------------------------------------- frontend
FROM node:22-alpine AS web

WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ----------------------------------------------------------------- backend
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

# tzdata 让模拟器的「早晨/午后/傍晚」与宿主机时区一致
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

# 先装依赖，利用镜像层缓存；pymilvus 让容器可以直接连接 Milvus
COPY backend/requirements.txt backend/requirements-milvus.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-milvus.txt

COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist

RUN mkdir -p /app/backend/data

EXPOSE 8000
VOLUME ["/app/backend/data"]

CMD ["python", "run.py"]
