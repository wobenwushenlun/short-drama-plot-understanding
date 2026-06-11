from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from backend.tests.test_api_contract_smoke import ContractFakeAIService


SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"


def _schema_signature(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _schema_signature(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_schema_signature(value[0])] if value else []
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if value is None:
        return "null"
    return "str"


def _assert_matches_snapshot(name: str, payload: dict[str, Any]) -> None:
    snapshot_path = SNAPSHOT_DIR / f"{name}.json"
    assert snapshot_path.exists(), f"missing contract snapshot: {snapshot_path}"
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
    actual = _schema_signature(_contract_view(name, payload))
    assert actual == expected


def _first(items: Any) -> Any:
    return items[0] if isinstance(items, list) and items else {}


def _pick(source: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: source.get(key) for key in keys if key in source}


def _contract_view(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if name == "timed_events_contract":
        return {
            **_pick(
                payload,
                [
                    "timelineSchemaVersion",
                    "eventCount",
                    "episode",
                    "nodes",
                    "candidateNodes",
                    "events",
                    "evidenceGraph",
                ],
            ),
            "nodes": [_first(payload.get("nodes"))],
            "candidateNodes": [_first(payload.get("candidateNodes"))],
            "events": [_first(payload.get("events"))],
            "evidenceGraph": _pick(
                payload.get("evidenceGraph") if isinstance(payload.get("evidenceGraph"), dict) else {},
                ["schemaVersion", "sourceStatus", "nodeCount", "evidenceCount", "relationCount", "storyFacets"],
            ),
        }
    if name == "evidence_graph_contract":
        return {
            **_pick(
                payload,
                [
                    "schemaVersion",
                    "episodeId",
                    "focusTimeMs",
                    "sourceStatus",
                    "evidenceSources",
                    "nodeCount",
                    "evidenceCount",
                    "relationCount",
                    "storyFacets",
                    "nodes",
                    "evidence",
                    "relations",
                    "explanations",
                ],
            ),
            "nodes": [_first(payload.get("nodes"))],
            "evidence": [_first(payload.get("evidence"))],
            "relations": [_first(payload.get("relations"))],
            "explanations": [_first(payload.get("explanations"))],
        }
    if name == "operations_dashboard_contract":
        return {
            **_pick(
                payload,
                [
                    "storage",
                    "episodeId",
                    "overview",
                    "trend",
                    "trendSummary",
                    "hotNodes",
                    "highlightStrategies",
                    "agnesGeneration",
                    "profile",
                ],
            ),
            "trend": [_first(payload.get("trend"))],
            "hotNodes": [_first(payload.get("hotNodes"))],
            "highlightStrategies": [_first(payload.get("highlightStrategies"))],
        }
    return payload


@pytest.mark.asyncio
async def test_core_api_contract_snapshots(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests
    import backend.app.api.routes.ai as ai_routes

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    monkeypatch.setattr(ai_routes, "get_ai_service", lambda: ContractFakeAIService())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        timed_resp = await ac.get("/episodes/tainai3_ep02/timed-events")
        evidence_resp = await ac.get("/episodes/tainai3_ep01/evidence-graph", params={"timeMs": 44000})
        generation_resp = await ac.post(
            "/ai/generation/tasks",
            json={"taskType": "story_continuation_video", "dramaId": "tainai3", "episodeId": "tainai3_ep01"},
        )
        task_id = generation_resp.json()["data"]["taskId"]
        generation_query_resp = await ac.get(f"/ai/generation/tasks/{task_id}")
        nodes_resp = await ac.get("/episodes/tainai3_ep01/interaction-nodes")
        node = nodes_resp.json()["data"]["nodes"][0]
        option = node["options"][0]
        await ac.post(
            "/analytics/events",
            json={
                "events": [
                    {
                        "eventName": "interaction_impression",
                        "screenName": "player",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": node["id"],
                        "progressMs": node["trigger"]["timeMs"],
                        "clientTsMs": 1_780_000_000_000,
                        "properties": {"nodeTitle": node["title"]},
                    },
                    {
                        "eventName": "home_highlight_impression",
                        "screenName": "home",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": "moment_001",
                        "clientTsMs": 1_780_000_000_100,
                        "properties": {"selectionStrategy": "hybrid", "rank": 1, "heatScore": 92},
                    }
                ]
            },
        )
        await ac.post(
            "/interaction/submit",
            json={
                "submitId": "contract_snapshot_submit_001",
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep01",
                "nodeId": node["id"],
                "triggerMs": node["trigger"]["timeMs"],
                "answer": {"optionId": option["id"]},
            },
        )
        dashboard_resp = await ac.get("/dashboard/operations", params={"episode_id": "tainai3_ep01"})

    assert timed_resp.status_code == 200
    assert evidence_resp.status_code == 200
    assert generation_resp.status_code == 200
    assert generation_query_resp.status_code == 200
    assert dashboard_resp.status_code == 200

    _assert_matches_snapshot("timed_events_contract", timed_resp.json()["data"])
    _assert_matches_snapshot("evidence_graph_contract", evidence_resp.json()["data"])
    _assert_matches_snapshot("generation_task_contract", generation_query_resp.json()["data"])
    _assert_matches_snapshot("operations_dashboard_contract", dashboard_resp.json()["data"])
