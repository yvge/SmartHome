"""Small helpers for consuming SSE endpoints through FastAPI TestClient."""
from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient


def stream_events(
    client: TestClient, method: str, url: str, **kwargs: Any,
) -> list[dict[str, Any]]:
    """Fully drain an SSE response into ``[{"event": ..., "data": ...}]``."""
    events: list[dict[str, Any]] = []
    with client.stream(method, url, **kwargs) as response:
        assert response.status_code == 200, response.read()
        event_name = "message"
        data_lines: list[str] = []
        for raw_line in response.iter_lines():
            line = raw_line.rstrip("\r")
            if not line:
                if data_lines:
                    events.append({
                        "event": event_name,
                        "data": json.loads("\n".join(data_lines)),
                    })
                event_name = "message"
                data_lines = []
                continue
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
            if field == "event":
                event_name = value.strip()
            elif field == "data":
                data_lines.append(value)
        if data_lines:
            events.append({
                "event": event_name,
                "data": json.loads("\n".join(data_lines)),
            })
    return events


def events_of(events: list[dict[str, Any]], event_name: str) -> list[dict[str, Any]]:
    return [event["data"] for event in events if event["event"] == event_name]


def last_event(
    events: list[dict[str, Any]], event_name: str,
) -> dict[str, Any] | None:
    matches = events_of(events, event_name)
    return matches[-1] if matches else None


def assert_event_order(events: list[dict[str, Any]], names: list[str]) -> None:
    """Assert each named event occurs and that their first occurrences are ordered."""
    seq = [event["event"] for event in events]
    positions = [seq.index(name) for name in names]
    assert positions == sorted(positions), f"unexpected SSE order: {seq}"
