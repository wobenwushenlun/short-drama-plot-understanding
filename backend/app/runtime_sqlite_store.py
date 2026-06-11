from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.app.operations_dashboard import (
    build_agnes_generation_report as build_agnes_generation_report_payload,
    build_highlight_strategy_report as build_highlight_strategy_report_payload,
)
from backend.app.operations_dashboard import build_operations_dashboard_payload
from backend.app.user_profile_domain import (
    build_profile_reason,
    build_profile_tag_distribution,
    derive_profile_tags,
)


DEFAULT_RUNTIME_DB_PATH = Path("tmp/aigc_runtime.sqlite3")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _build_scope_filter(episode_id: str | None = None, drama_id: str | None = None) -> tuple[str, tuple[Any, ...]]:
    conditions: list[str] = []
    parameters: list[Any] = []
    if episode_id:
        conditions.append("episode_id = ?")
        parameters.append(episode_id)
    if drama_id:
        conditions.append("drama_id = ?")
        parameters.append(drama_id)
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    return where_clause, tuple(parameters)


def resolve_runtime_db_path() -> Path:
    raw = os.environ.get("AIGC_RUNTIME_DB_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_RUNTIME_DB_PATH


class RuntimeSQLiteStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db_path), timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema(connection)
        return connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS watch_progress (
                episode_id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL,
                drama_id TEXT NOT NULL,
                progress_ms INTEGER NOT NULL,
                duration_ms INTEGER NOT NULL,
                is_completed INTEGER NOT NULL,
                client_ts_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analytics_events (
                event_id TEXT PRIMARY KEY,
                event_name TEXT NOT NULL,
                screen_name TEXT NOT NULL,
                drama_id TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                progress_ms INTEGER,
                client_ts_ms INTEGER NOT NULL,
                properties_json TEXT NOT NULL,
                received_at_ms INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_analytics_event_episode
            ON analytics_events(event_name, episode_id, node_id);

            CREATE TABLE IF NOT EXISTS interaction_records (
                record_id TEXT PRIMARY KEY,
                submit_id TEXT NOT NULL UNIQUE,
                drama_id TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                node_title TEXT NOT NULL,
                option_id TEXT NOT NULL,
                option_text TEXT NOT NULL,
                trigger_ms INTEGER NOT NULL,
                created_at_ms INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_interaction_episode_created
            ON interaction_records(episode_id, created_at_ms DESC);

            CREATE TABLE IF NOT EXISTS ai_artifact_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                capability TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                drama_id TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                promoted INTEGER NOT NULL,
                success_version INTEGER NOT NULL,
                result_json TEXT NOT NULL,
                model_name TEXT NOT NULL,
                cached INTEGER NOT NULL,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                degrade_reason TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ai_artifact_scope_success
            ON ai_artifact_attempts(capability, scope_key, promoted, success_version DESC);

            CREATE INDEX IF NOT EXISTS idx_ai_artifact_status
            ON ai_artifact_attempts(capability, status, created_at_ms DESC);

            CREATE TABLE IF NOT EXISTS saved_moments (
                moment_id TEXT PRIMARY KEY,
                drama_id TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                title TEXT NOT NULL,
                hook_text TEXT NOT NULL,
                source_node_id TEXT NOT NULL,
                source TEXT NOT NULL,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                heat_score INTEGER NOT NULL,
                created_at_ms INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_saved_moments_drama
            ON saved_moments(drama_id, created_at_ms DESC);

            CREATE TABLE IF NOT EXISTS generation_tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                drama_id TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                status TEXT NOT NULL,
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                media_url TEXT NOT NULL,
                media_type TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                degrade_reason TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_generation_tasks_scope
            ON generation_tasks(task_type, episode_id, status, updated_at_ms DESC);
            """
        )
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(ai_artifact_attempts)").fetchall()
        }
        if "latency_ms" not in columns:
            connection.execute(
                "ALTER TABLE ai_artifact_attempts ADD COLUMN latency_ms INTEGER NOT NULL DEFAULT 0"
            )
        connection.commit()

    def save_watch_progress(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO watch_progress (
                    episode_id, record_id, drama_id, progress_ms, duration_ms,
                    is_completed, client_ts_ms, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id) DO UPDATE SET
                    record_id = excluded.record_id,
                    drama_id = excluded.drama_id,
                    progress_ms = excluded.progress_ms,
                    duration_ms = excluded.duration_ms,
                    is_completed = excluded.is_completed,
                    client_ts_ms = excluded.client_ts_ms,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (
                    record["episode_id"],
                    record["record_id"],
                    record["drama_id"],
                    int(record["progress_ms"]),
                    int(record["duration_ms"]),
                    int(bool(record["is_completed"])),
                    int(record["client_ts_ms"]),
                    int(record["updated_at_ms"]),
                ),
            )
        return record

    def list_watch_history(self, size: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT record_id, drama_id, episode_id, progress_ms, duration_ms,
                       is_completed, client_ts_ms, updated_at_ms
                FROM watch_progress
                ORDER BY updated_at_ms DESC
                LIMIT ?
                """,
                (max(size, 0),),
            ).fetchall()
        return [
            {
                "record_id": row["record_id"],
                "drama_id": row["drama_id"],
                "episode_id": row["episode_id"],
                "progress_ms": row["progress_ms"],
                "duration_ms": row["duration_ms"],
                "is_completed": bool(row["is_completed"]),
                "client_ts_ms": row["client_ts_ms"],
                "updated_at_ms": row["updated_at_ms"],
            }
            for row in rows
        ]

    def save_analytics_events(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO analytics_events (
                    event_id, event_name, screen_name, drama_id, episode_id,
                    node_id, progress_ms, client_ts_ms, properties_json, received_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record["event_id"],
                        record["event_name"],
                        record["screen_name"],
                        record["drama_id"],
                        record["episode_id"],
                        record["node_id"],
                        record.get("progress_ms"),
                        int(record["client_ts_ms"]),
                        json.dumps(record.get("properties") or {}, ensure_ascii=False, separators=(",", ":")),
                        int(record["received_at_ms"]),
                    )
                    for record in records
                ],
            )

    def save_interaction_record(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO interaction_records (
                    record_id, submit_id, drama_id, episode_id, node_id,
                    node_title, option_id, option_text, trigger_ms, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["record_id"],
                    record["submit_id"],
                    record["drama_id"],
                    record["episode_id"],
                    record["node_id"],
                    record["node_title"],
                    record["option_id"],
                    record["option_text"],
                    int(record["trigger_ms"]),
                    int(record["created_at_ms"]),
                ),
            )
            row = connection.execute(
                """
                SELECT record_id, submit_id, drama_id, episode_id, node_id,
                       node_title, option_id, option_text, trigger_ms, created_at_ms
                FROM interaction_records
                WHERE submit_id = ?
                """,
                (record["submit_id"],),
            ).fetchone()
        return dict(row) if row else record

    def save_moment(self, record: dict[str, Any]) -> dict[str, Any]:
        created_at_ms = int(record.get("created_at_ms") or _now_ms())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO saved_moments (
                    moment_id, drama_id, episode_id, title, hook_text,
                    source_node_id, source, start_ms, end_ms, heat_score, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(moment_id) DO UPDATE SET
                    title = excluded.title,
                    hook_text = excluded.hook_text,
                    source = excluded.source,
                    start_ms = excluded.start_ms,
                    end_ms = excluded.end_ms,
                    heat_score = excluded.heat_score,
                    created_at_ms = excluded.created_at_ms
                """,
                (
                    record["moment_id"],
                    record["drama_id"],
                    record["episode_id"],
                    record["title"],
                    record["hook_text"],
                    record.get("source_node_id", ""),
                    record.get("source", ""),
                    int(record["start_ms"]),
                    int(record["end_ms"]),
                    int(record.get("heat_score", 0)),
                    created_at_ms,
                ),
            )
        record["created_at_ms"] = created_at_ms
        return record

    def list_saved_moments(self, drama_id: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT moment_id, drama_id, episode_id, title, hook_text,
                   source_node_id, source, start_ms, end_ms, heat_score, created_at_ms
            FROM saved_moments
        """
        parameters: tuple[Any, ...] = ()
        if drama_id:
            query += " WHERE drama_id = ?"
            parameters = (drama_id,)
        query += " ORDER BY created_at_ms DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def list_interaction_records(self, episode_id: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT record_id, submit_id, drama_id, episode_id, node_id,
                   node_title, option_id, option_text, trigger_ms, created_at_ms
            FROM interaction_records
        """
        parameters: tuple[Any, ...] = ()
        if episode_id:
            query += " WHERE episode_id = ?"
            parameters = (episode_id,)
        query += " ORDER BY created_at_ms DESC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def register_ai_attempt(
        self,
        *,
        capability: str,
        scope_key: str,
        prompt_version: str,
        drama_id: str,
        episode_id: str,
        node_id: str,
        status: str,
        source: str,
        result: dict[str, Any],
        model_name: str,
        cached: bool,
        latency_ms: int,
        degrade_reason: str,
        restore_last_success: bool = True,
    ) -> dict[str, Any]:
        created_at_ms = _now_ms()
        with self._connect() as connection:
            latest_success = connection.execute(
                """
                SELECT success_version, source, result_json, created_at_ms
                FROM ai_artifact_attempts
                WHERE capability = ? AND scope_key = ? AND promoted = 1
                ORDER BY success_version DESC
                LIMIT 1
                """,
                (capability, scope_key),
            ).fetchone()
            promoted = status == "ok" and (not cached or latest_success is None)
            success_version = int(latest_success["success_version"]) if latest_success else 0
            if promoted:
                success_version += 1
            connection.execute(
                """
                INSERT INTO ai_artifact_attempts (
                    capability, scope_key, prompt_version, drama_id, episode_id,
                    node_id, status, source, promoted, success_version,
                    result_json, model_name, cached, latency_ms, degrade_reason, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    capability,
                    scope_key,
                    prompt_version,
                    drama_id,
                    episode_id,
                    node_id,
                    status,
                    source,
                    int(promoted),
                    success_version if status == "ok" else 0,
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                    model_name,
                    int(cached),
                    max(int(latency_ms), 0),
                    degrade_reason,
                    created_at_ms,
                ),
            )
            if promoted:
                latest_success = {
                    "success_version": success_version,
                    "source": source,
                    "result_json": json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                    "created_at_ms": created_at_ms,
                }

        restored = bool(restore_last_success) and status == "degraded" and latest_success is not None
        display_result = (
            json.loads(str(latest_success["result_json"]))
            if restored and latest_success is not None
            else result
        )
        latest_success_version = int(latest_success["success_version"]) if latest_success else 0
        return {
            "result": display_result,
            "artifact": {
                "source": "last_success_artifact" if restored else source,
                "version": latest_success_version if restored else (success_version if status == "ok" else 0),
                "restored_from_last_success": restored,
                "last_success_version": latest_success_version,
                "last_success_source": str(latest_success["source"]) if latest_success else "",
                "last_success_at_ms": int(latest_success["created_at_ms"]) if latest_success else 0,
            },
            }

    def build_user_profile(self, drama_id: str | None = None) -> dict[str, Any]:
        where_scope, scope_params = _build_scope_filter(drama_id=drama_id)
        with self._connect() as connection:
            watch = connection.execute(
                f"""
                SELECT COUNT(*) AS episodes,
                       SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) AS completed
                FROM watch_progress
                {where_scope}
                """,
                scope_params,
            ).fetchone()
            interaction = connection.execute(
                f"""
                SELECT COUNT(*) AS submits
                FROM interaction_records
                {where_scope}
                """,
                scope_params,
            ).fetchone()
            saved = connection.execute(
                f"""
                SELECT COUNT(*) AS moments,
                       COALESCE(SUM(heat_score), 0) AS heat_score
                FROM saved_moments
                {where_scope}
                """,
                scope_params,
            ).fetchone()
            behavior = connection.execute(
                f"""
                SELECT event_name, COUNT(*) AS event_count
                FROM analytics_events
                {where_scope}
                GROUP BY event_name
                """,
                scope_params,
            ).fetchall()
            text_rows = connection.execute(
                f"""
                SELECT node_title, option_text
                FROM interaction_records
                {where_scope}
                """,
                scope_params,
            ).fetchall()
            moment_rows = connection.execute(
                f"""
                SELECT title, hook_text
                FROM saved_moments
                {where_scope}
                """,
                scope_params,
            ).fetchall()
            top_nodes = connection.execute(
                f"""
                SELECT node_id,
                       COUNT(*) AS submits,
                       MAX(node_title) AS node_title
                FROM interaction_records
                {where_scope}
                GROUP BY node_id
                ORDER BY submits DESC, node_id
                LIMIT 3
                """,
                scope_params,
            ).fetchall()
        texts = [
            str(row["node_title"] or "")
            + " "
            + str(row["option_text"] or "")
            for row in text_rows
        ] + [
            str(row["title"] or "") + " " + str(row["hook_text"] or "")
            for row in moment_rows
        ]
        tags = derive_profile_tags(texts)
        tag_distribution = build_profile_tag_distribution(texts)
        if int(saved["moments"] or 0) > 0 and "高能切片偏好" not in tags:
            tags.insert(0, "高能切片偏好")
        if int(interaction["submits"] or 0) > 0 and "互动选择偏好" not in tags:
            tags.append("互动选择偏好")
        if int(watch["completed"] or 0) > 0 and "追更意愿" not in tags:
            tags.append("追更意愿")
        tags = list(dict.fromkeys(tags))
        reason_parts = build_profile_reason(tags, int(saved["moments"] or 0), int(interaction["submits"] or 0))
        return {
            "storage": {"engine": "sqlite", "persistent": True},
            "episodeCount": int(watch["episodes"] or 0),
            "completedCount": int(watch["completed"] or 0),
            "interactionCount": int(interaction["submits"] or 0),
            "savedMomentCount": int(saved["moments"] or 0),
            "savedMomentHeat": int(saved["heat_score"] or 0),
            "eventCount": sum(int(row["event_count"] or 0) for row in behavior),
            "interestTags": tags,
            "interestTagDistribution": tag_distribution,
            "recommendReason": "；".join(reason_parts),
            "topNodes": [
                {
                    "nodeId": row["node_id"],
                    "nodeTitle": row["node_title"],
                    "submits": int(row["submits"] or 0),
                }
                for row in top_nodes
                if row["node_id"]
            ],
        }

    def build_operations_dashboard(
        self,
        episode_id: str | None = None,
        drama_id: str | None = None,
    ) -> dict[str, Any]:
        summary = self.build_runtime_summary(episode_id, drama_id=drama_id)
        profile = self.build_user_profile(drama_id=drama_id)
        trend = self.build_operations_trend(episode_id, drama_id=drama_id)
        highlight_strategies = self.build_highlight_strategy_report(episode_id, drama_id=drama_id)
        agnes_generation = self.build_agnes_generation_report(episode_id, drama_id=drama_id)
        return build_operations_dashboard_payload(
            summary=summary,
            profile=profile,
            trend=trend,
            highlight_strategies=highlight_strategies,
            agnes_generation=agnes_generation,
            generated_at_ms=_now_ms(),
        )

    def build_agnes_generation_report(
        self,
        episode_id: str | None = None,
        drama_id: str | None = None,
    ) -> dict[str, Any]:
        where_scope, scope_params = _build_scope_filter(episode_id=episode_id, drama_id=drama_id)
        scope_and = where_scope.replace(" WHERE ", " AND ", 1)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT event_name, properties_json, client_ts_ms
                FROM analytics_events
                WHERE event_name IN (
                    'agnes_image_generate_start',
                    'agnes_image_generate_success',
                    'agnes_image_generate_degraded',
                    'agnes_video_generate_start',
                    'agnes_video_generate_success',
                    'agnes_video_generate_degraded'
                )
                {scope_and}
                """,
                scope_params,
            ).fetchall()

        events = [
            {
                "eventName": row["event_name"],
                "properties": _parse_properties_json(row["properties_json"]),
                "clientTsMs": int(row["client_ts_ms"] or 0),
            }
            for row in rows
        ]
        return build_agnes_generation_report_payload(events)

    def build_highlight_strategy_report(
        self,
        episode_id: str | None = None,
        drama_id: str | None = None,
    ) -> list[dict[str, Any]]:
        where_scope, scope_params = _build_scope_filter(episode_id=episode_id, drama_id=drama_id)
        scope_and = where_scope.replace(" WHERE ", " AND ", 1)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT event_name, episode_id, properties_json, client_ts_ms
                FROM analytics_events
                WHERE event_name IN (
                    'home_highlight_impression',
                    'home_highlight_click',
                    'home_highlight_jump',
                    'home_highlight_play_complete',
                    'moment_save'
                )
                {scope_and}
                """,
                scope_params,
            ).fetchall()

        events = [
            {
                "eventName": row["event_name"],
                "properties": _parse_properties_json(row["properties_json"]),
                "clientTsMs": int(row["client_ts_ms"] or 0),
            }
            for row in rows
        ]
        return build_highlight_strategy_report_payload(events)

    def build_operations_trend(
        self,
        episode_id: str | None = None,
        days: int = 7,
        drama_id: str | None = None,
    ) -> list[dict[str, Any]]:
        days = max(1, days)
        scope_filter, scope_params = _build_scope_filter(episode_id=episode_id, drama_id=drama_id)
        with self._connect() as connection:
            reference_ms = _now_ms()
            for query in (
                f"SELECT MAX(client_ts_ms) AS latest_ms FROM watch_progress{scope_filter}",
                f"SELECT MAX(client_ts_ms) AS latest_ms FROM analytics_events{scope_filter}",
                f"SELECT MAX(created_at_ms) AS latest_ms FROM interaction_records{scope_filter}",
                f"SELECT MAX(created_at_ms) AS latest_ms FROM ai_artifact_attempts{scope_filter}",
            ):
                row = connection.execute(query, scope_params).fetchone()
                latest_ms = int(row["latest_ms"] or 0) if row and row["latest_ms"] is not None else 0
                if latest_ms > reference_ms:
                    reference_ms = latest_ms

            reference_day = datetime.fromtimestamp(reference_ms / 1000).date()
            start_day = reference_day - timedelta(days=days - 1)
            cutoff_ms = int(datetime.combine(start_day, datetime.min.time()).timestamp() * 1000)

            buckets: dict[str, dict[str, Any]] = {}
            for offset in range(days):
                bucket_day = start_day + timedelta(days=offset)
                day_key = bucket_day.isoformat()
                buckets[day_key] = {
                    "day": day_key,
                    "label": bucket_day.strftime("%m-%d"),
                    "interactionImpressions": 0,
                    "interactionSubmits": 0,
                    "watchEpisodeCount": 0,
                    "watchCompletedCount": 0,
                    "insertPlaybackStarts": 0,
                    "insertPlaybackCompleted": 0,
                    "videoStartAttemptCount": 0,
                    "firstFrameRenderedCount": 0,
                    "exitBeforeStartCount": 0,
                    "rebufferCount": 0,
                    "startupMsSamples": [],
                    "rebufferDurationMsSamples": [],
                    "playbackErrorCount": 0,
                    "fullscreenExitCount": 0,
                    "continueWatchCount": 0,
                    "aiAttemptCount": 0,
                    "aiSuccessCount": 0,
                    "aiDegradedCount": 0,
                    "aiBlockedCount": 0,
                    "aiLatencySamples": [],
                }

            def bucket_for(timestamp_ms: int) -> dict[str, Any] | None:
                day_key = datetime.fromtimestamp(timestamp_ms / 1000).date().isoformat()
                return buckets.get(day_key)

            watch_rows = connection.execute(
                f"""
                SELECT client_ts_ms, is_completed
                FROM watch_progress
                {scope_filter}{' AND' if scope_filter else ' WHERE'} client_ts_ms >= ?
                """,
                scope_params + (cutoff_ms,),
            ).fetchall()
            interaction_rows = connection.execute(
                f"""
                SELECT created_at_ms
                FROM interaction_records
                {scope_filter}{' AND' if scope_filter else ' WHERE'} created_at_ms >= ?
                """,
                scope_params + (cutoff_ms,),
            ).fetchall()
            analytics_rows = connection.execute(
                f"""
                SELECT event_name, client_ts_ms, properties_json
                FROM analytics_events
                {scope_filter}{' AND' if scope_filter else ' WHERE'} client_ts_ms >= ?
                """,
                scope_params + (cutoff_ms,),
            ).fetchall()
            ai_rows = connection.execute(
                f"""
                SELECT status, latency_ms, created_at_ms
                FROM ai_artifact_attempts
                {scope_filter}{' AND' if scope_filter else ' WHERE'} created_at_ms >= ?
                """,
                scope_params + (cutoff_ms,),
            ).fetchall()

        for row in watch_rows:
            bucket = bucket_for(int(row["client_ts_ms"] or 0))
            if bucket is None:
                continue
            bucket["watchEpisodeCount"] += 1
            if int(row["is_completed"] or 0):
                bucket["watchCompletedCount"] += 1

        for row in interaction_rows:
            bucket = bucket_for(int(row["created_at_ms"] or 0))
            if bucket is None:
                continue
            bucket["interactionSubmits"] += 1

        for row in analytics_rows:
            bucket = bucket_for(int(row["client_ts_ms"] or 0))
            if bucket is None:
                continue
            event_name = str(row["event_name"] or "")
            if event_name == "interaction_impression":
                bucket["interactionImpressions"] += 1
            elif event_name == "insert_play_start":
                bucket["insertPlaybackStarts"] += 1
            elif event_name == "insert_play_complete":
                bucket["insertPlaybackCompleted"] += 1
            elif event_name == "video_start_attempt":
                bucket["videoStartAttemptCount"] += 1
            elif event_name == "first_frame_rendered":
                bucket["firstFrameRenderedCount"] += 1
                properties = _parse_properties_json(row["properties_json"])
                startup_ms = _property_int(properties, "startupMs", "startup_ms")
                if startup_ms > 0:
                    bucket["startupMsSamples"].append(startup_ms)
            elif event_name == "exit_before_start":
                bucket["exitBeforeStartCount"] += 1
            elif event_name == "rebuffer_end":
                bucket["rebufferCount"] += 1
                properties = _parse_properties_json(row["properties_json"])
                duration_ms = _property_int(properties, "durationMs", "duration_ms")
                if duration_ms > 0:
                    bucket["rebufferDurationMsSamples"].append(duration_ms)
            elif event_name == "playback_error":
                bucket["playbackErrorCount"] += 1
            elif event_name == "fullscreen_exit":
                bucket["fullscreenExitCount"] += 1
            elif event_name == "continue_watch":
                bucket["continueWatchCount"] += 1

        for row in ai_rows:
            bucket = bucket_for(int(row["created_at_ms"] or 0))
            if bucket is None:
                continue
            bucket["aiAttemptCount"] += 1
            status = str(row["status"] or "")
            if status == "ok":
                bucket["aiSuccessCount"] += 1
            elif status == "degraded":
                bucket["aiDegradedCount"] += 1
            elif status == "blocked":
                bucket["aiBlockedCount"] += 1
            bucket["aiLatencySamples"].append(int(row["latency_ms"] or 0))

        result: list[dict[str, Any]] = []
        for day_key in sorted(buckets):
            bucket = buckets[day_key]
            interaction_impressions = int(bucket["interactionImpressions"])
            interaction_submits = int(bucket["interactionSubmits"])
            watch_episode_count = int(bucket["watchEpisodeCount"])
            watch_completed_count = int(bucket["watchCompletedCount"])
            insert_starts = int(bucket["insertPlaybackStarts"])
            insert_completed = int(bucket["insertPlaybackCompleted"])
            video_start_attempts = int(bucket["videoStartAttemptCount"])
            first_frames = int(bucket["firstFrameRenderedCount"])
            startup_failure_count = int(bucket["playbackErrorCount"]) + int(bucket["exitBeforeStartCount"])
            rebuffer_durations = bucket["rebufferDurationMsSamples"]
            ai_attempt_count = int(bucket["aiAttemptCount"])
            ai_success_count = int(bucket["aiSuccessCount"])
            ai_degraded_count = int(bucket["aiDegradedCount"])
            ai_blocked_count = int(bucket["aiBlockedCount"])
            result.append(
                {
                    "day": bucket["day"],
                    "label": bucket["label"],
                    "interactionImpressions": interaction_impressions,
                    "interactionSubmits": interaction_submits,
                    "interactionCtr": round(interaction_submits / interaction_impressions, 4)
                    if interaction_impressions
                    else 0.0,
                    "watchEpisodeCount": watch_episode_count,
                    "watchCompletedCount": watch_completed_count,
                    "watchCompletionRate": round(watch_completed_count / watch_episode_count, 4)
                    if watch_episode_count
                    else 0.0,
                    "insertPlaybackStarts": insert_starts,
                    "insertPlaybackCompleted": insert_completed,
                    "insertPlaybackCompletionRate": round(insert_completed / insert_starts, 4)
                    if insert_starts
                    else 0.0,
                    "videoStartAttempts": video_start_attempts,
                    "firstFrameRendered": first_frames,
                    "startupSuccessRate": round(first_frames / video_start_attempts, 4)
                    if video_start_attempts
                    else 0.0,
                    "startupFailureRate": round(startup_failure_count / video_start_attempts, 4)
                    if video_start_attempts
                    else 0.0,
                    "exitBeforeStartCount": int(bucket["exitBeforeStartCount"]),
                    "rebufferCount": int(bucket["rebufferCount"]),
                    "rebufferTotalMs": sum(int(value) for value in rebuffer_durations),
                    "startupP95Ms": _percentile95(bucket["startupMsSamples"]),
                    "rebufferP95Ms": _percentile95(rebuffer_durations),
                    "playbackErrorCount": int(bucket["playbackErrorCount"]),
                    "fullscreenExitCount": int(bucket["fullscreenExitCount"]),
                    "continueWatchCount": int(bucket["continueWatchCount"]),
                    "aiAttemptCount": ai_attempt_count,
                    "aiSuccessCount": ai_success_count,
                    "aiDegradedCount": ai_degraded_count,
                    "aiBlockedCount": ai_blocked_count,
                    "aiSuccessRate": round(ai_success_count / ai_attempt_count, 4)
                    if ai_attempt_count
                    else 0.0,
                    "aiDegradedRate": round(ai_degraded_count / ai_attempt_count, 4)
                    if ai_attempt_count
                    else 0.0,
                    "aiP95LatencyMs": _percentile95(bucket["aiLatencySamples"]),
                }
            )
        return result

    def build_runtime_summary(self, episode_id: str | None = None, drama_id: str | None = None) -> dict[str, Any]:
        where_scope, parameters = _build_scope_filter(episode_id=episode_id, drama_id=drama_id)
        scope_and = where_scope.replace(" WHERE ", " AND ", 1)
        with self._connect() as connection:
            watch = connection.execute(
                f"""
                SELECT COUNT(*) AS episodes,
                       SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) AS completed
                FROM watch_progress
                {where_scope}
                """,
                parameters,
            ).fetchone()
            interaction = connection.execute(
                f"""
                SELECT COUNT(*) AS submits
                FROM interaction_records{where_scope}
                """,
                parameters,
            ).fetchone()
            impressions = connection.execute(
                f"""
                SELECT COUNT(*) AS impressions
                FROM analytics_events
                WHERE event_name = 'interaction_impression'
                {scope_and}
                """,
                parameters,
            ).fetchone()
            node_rows = connection.execute(
                f"""
                SELECT node_id,
                       SUM(impressions) AS impressions,
                       SUM(submits) AS submits
                FROM (
                    SELECT node_id, COUNT(*) AS impressions, 0 AS submits
                    FROM analytics_events
                    WHERE event_name = 'interaction_impression'
                    {scope_and}
                    GROUP BY node_id
                    UNION ALL
                    SELECT node_id, 0 AS impressions, COUNT(*) AS submits
                    FROM interaction_records
                    {where_scope}
                    GROUP BY node_id
                )
                GROUP BY node_id
                ORDER BY submits DESC, impressions DESC, node_id
                """,
                parameters + parameters if parameters else (),
            ).fetchall()
            node_title_rows = connection.execute(
                f"""
                SELECT node_id, MAX(node_title) AS node_title
                FROM interaction_records
                {where_scope}
                GROUP BY node_id
                """,
                parameters,
            ).fetchall()
            option_rows = connection.execute(
                f"""
                SELECT node_id, option_id, option_text, COUNT(*) AS selects
                FROM interaction_records
                {where_scope}
                GROUP BY node_id, option_id, option_text
                ORDER BY node_id, selects DESC, option_id
                """,
                parameters,
            ).fetchall()
            behavior_rows = connection.execute(
                f"""
                SELECT event_name, COUNT(*) AS event_count
                FROM analytics_events
                WHERE event_name IN (
                    'insert_play_start', 'insert_play_complete', 'playback_error',
                    'fullscreen_exit', 'continue_watch', 'video_start_attempt',
                    'first_frame_rendered', 'exit_before_start', 'rebuffer_start',
                    'rebuffer_end'
                )
                {scope_and}
                GROUP BY event_name
                """,
                parameters,
            ).fetchall()
            playback_qoe_rows = connection.execute(
                f"""
                SELECT event_name, properties_json
                FROM analytics_events
                WHERE event_name IN ('first_frame_rendered', 'rebuffer_end')
                {scope_and}
                """,
                parameters,
            ).fetchall()
            ai_rows = connection.execute(
                f"""
                SELECT capability,
                       COUNT(*) AS total,
                       SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS success_count,
                       SUM(CASE WHEN status = 'degraded' THEN 1 ELSE 0 END) AS degraded_count,
                       SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked_count,
                       MAX(created_at_ms) AS latest_at_ms
                FROM ai_artifact_attempts
                {where_scope}
                GROUP BY capability
                ORDER BY capability
                """,
                parameters,
            ).fetchall()
            ai_latency_rows = connection.execute(
                f"""
                SELECT capability, latency_ms
                FROM ai_artifact_attempts
                {where_scope}
                ORDER BY capability, latency_ms
                """,
                parameters,
            ).fetchall()
        node_titles = {str(row["node_id"]): str(row["node_title"] or "") for row in node_title_rows}
        submit_count = int(interaction["submits"] or 0)
        impression_count = int(impressions["impressions"] or 0)
        choices_by_node: dict[str, list[dict[str, Any]]] = {}
        for row in option_rows:
            choices_by_node.setdefault(str(row["node_id"]), []).append(
                {
                    "optionId": row["option_id"],
                    "optionText": row["option_text"],
                    "selects": int(row["selects"] or 0),
                }
            )
        behavior_counts = {str(row["event_name"]): int(row["event_count"] or 0) for row in behavior_rows}
        startup_samples: list[int] = []
        rebuffer_duration_samples: list[int] = []
        for row in playback_qoe_rows:
            event_name = str(row["event_name"] or "")
            properties = _parse_properties_json(row["properties_json"])
            if event_name == "first_frame_rendered":
                startup_ms = _property_int(properties, "startupMs", "startup_ms")
                if startup_ms > 0:
                    startup_samples.append(startup_ms)
            elif event_name == "rebuffer_end":
                duration_ms = _property_int(properties, "durationMs", "duration_ms")
                if duration_ms > 0:
                    rebuffer_duration_samples.append(duration_ms)
        latency_by_capability: dict[str, list[int]] = {}
        for row in ai_latency_rows:
            latency_by_capability.setdefault(str(row["capability"]), []).append(int(row["latency_ms"] or 0))
        ai_capabilities = [
            {
                "capability": row["capability"],
                "total": int(row["total"] or 0),
                "successCount": int(row["success_count"] or 0),
                "degradedCount": int(row["degraded_count"] or 0),
                "blockedCount": int(row["blocked_count"] or 0),
                "successRate": round(
                    int(row["success_count"] or 0)
                    / max(int(row["success_count"] or 0) + int(row["degraded_count"] or 0), 1),
                    4,
                ),
                "degradedRate": round(
                    int(row["degraded_count"] or 0)
                    / max(int(row["success_count"] or 0) + int(row["degraded_count"] or 0), 1),
                    4,
                ),
                "p95LatencyMs": _percentile95(latency_by_capability.get(str(row["capability"]), [])),
                "latestAtMs": int(row["latest_at_ms"] or 0),
            }
            for row in ai_rows
        ]
        ai_total = sum(item["total"] for item in ai_capabilities)
        ai_success_count = sum(item["successCount"] for item in ai_capabilities)
        ai_degraded_count = sum(item["degradedCount"] for item in ai_capabilities)
        video_start_attempts = behavior_counts.get("video_start_attempt", 0)
        first_frame_count = behavior_counts.get("first_frame_rendered", 0)
        playback_error_count = behavior_counts.get("playback_error", 0)
        exit_before_start_count = behavior_counts.get("exit_before_start", 0)
        rebuffer_count = behavior_counts.get("rebuffer_end", 0)
        startup_failure_count = playback_error_count + exit_before_start_count
        return {
            "storage": {"engine": "sqlite", "persistent": True},
            "dramaId": drama_id or "",
            "episodeId": episode_id or "",
            "watch": {
                "episodeCount": int(watch["episodes"] or 0),
                "completedCount": int(watch["completed"] or 0),
            },
            "interaction": {
                "impressions": impression_count,
                "submits": submit_count,
                "ctr": round(submit_count / impression_count, 4) if impression_count else 0.0,
                "nodes": [
                    {
                        "nodeId": row["node_id"],
                        "nodeTitle": node_titles.get(str(row["node_id"]), str(row["node_id"])),
                        "impressions": int(row["impressions"] or 0),
                        "submits": int(row["submits"] or 0),
                        "ctr": round(int(row["submits"] or 0) / int(row["impressions"] or 1), 4)
                        if int(row["impressions"] or 0)
                        else 0.0,
                        "choices": choices_by_node.get(str(row["node_id"]), []),
                    }
                    for row in node_rows
                    if row["node_id"]
                ],
            },
            "insertPlayback": {
                "starts": behavior_counts.get("insert_play_start", 0),
                "completed": behavior_counts.get("insert_play_complete", 0),
                "completionRate": round(
                    behavior_counts.get("insert_play_complete", 0)
                    / behavior_counts.get("insert_play_start", 1),
                    4,
                )
                if behavior_counts.get("insert_play_start", 0)
                else 0.0,
            },
            "playback": {
                "errorCount": playback_error_count,
                "fullscreenExitCount": behavior_counts.get("fullscreen_exit", 0),
                "continueWatchCount": behavior_counts.get("continue_watch", 0),
                "videoStartAttempts": video_start_attempts,
                "firstFrameRendered": first_frame_count,
                "startupSuccessRate": round(first_frame_count / video_start_attempts, 4)
                if video_start_attempts
                else 0.0,
                "startupFailureRate": round(startup_failure_count / video_start_attempts, 4)
                if video_start_attempts
                else 0.0,
                "exitBeforeStartCount": exit_before_start_count,
                "rebufferCount": rebuffer_count,
                "rebufferTotalMs": sum(rebuffer_duration_samples),
                "startupP50Ms": _percentile(startup_samples, 0.5),
                "startupP95Ms": _percentile95(startup_samples),
                "rebufferP95Ms": _percentile95(rebuffer_duration_samples),
            },
            "ai": {
                "capabilities": ai_capabilities,
                "total": ai_total,
                "successCount": ai_success_count,
                "degradedCount": ai_degraded_count,
                "blockedCount": sum(item["blockedCount"] for item in ai_capabilities),
                "successRate": round(ai_success_count / max(ai_success_count + ai_degraded_count, 1), 4),
                "degradedRate": round(ai_degraded_count / max(ai_success_count + ai_degraded_count, 1), 4),
                "p95LatencyMs": _percentile95(
                    [latency for values in latency_by_capability.values() for latency in values]
                ),
            },
        }

    def save_generation_task(self, record: dict[str, Any]) -> dict[str, Any]:
        now_ms = int(record.get("updatedAtMs") or _now_ms())
        created_at_ms = int(record.get("createdAtMs") or now_ms)
        normalized = {
            "taskId": str(record.get("taskId") or ""),
            "taskType": str(record.get("taskType") or ""),
            "dramaId": str(record.get("dramaId") or ""),
            "episodeId": str(record.get("episodeId") or ""),
            "status": str(record.get("status") or "queued"),
            "provider": str(record.get("provider") or ""),
            "modelName": str(record.get("modelName") or ""),
            "mediaUrl": str(record.get("mediaUrl") or ""),
            "mediaType": str(record.get("mediaType") or ""),
            "latencyMs": int(record.get("latencyMs") or 0),
            "degradeReason": str(record.get("degradeReason") or ""),
            "result": record.get("result") if isinstance(record.get("result"), dict) else {},
            "createdAtMs": created_at_ms,
            "updatedAtMs": now_ms,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO generation_tasks (
                    task_id, task_type, drama_id, episode_id, status, provider,
                    model_name, media_url, media_type, latency_ms, degrade_reason,
                    result_json, created_at_ms, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status = excluded.status,
                    provider = excluded.provider,
                    model_name = excluded.model_name,
                    media_url = excluded.media_url,
                    media_type = excluded.media_type,
                    latency_ms = excluded.latency_ms,
                    degrade_reason = excluded.degrade_reason,
                    result_json = excluded.result_json,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (
                    normalized["taskId"],
                    normalized["taskType"],
                    normalized["dramaId"],
                    normalized["episodeId"],
                    normalized["status"],
                    normalized["provider"],
                    normalized["modelName"],
                    normalized["mediaUrl"],
                    normalized["mediaType"],
                    normalized["latencyMs"],
                    normalized["degradeReason"],
                    json.dumps(normalized["result"], ensure_ascii=False, separators=(",", ":")),
                    normalized["createdAtMs"],
                    normalized["updatedAtMs"],
                ),
            )
        return normalized

    def get_generation_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT task_id, task_type, drama_id, episode_id, status, provider,
                       model_name, media_url, media_type, latency_ms, degrade_reason,
                       result_json, created_at_ms, updated_at_ms
                FROM generation_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        return _format_generation_task_row(row) if row else None

    def get_latest_success_generation_task(self, task_type: str, episode_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT task_id, task_type, drama_id, episode_id, status, provider,
                       model_name, media_url, media_type, latency_ms, degrade_reason,
                       result_json, created_at_ms, updated_at_ms
                FROM generation_tasks
                WHERE task_type = ? AND episode_id = ? AND status = 'succeeded'
                ORDER BY updated_at_ms DESC
                LIMIT 1
                """,
                (task_type, episode_id),
              ).fetchone()
        return _format_generation_task_row(row) if row else None

    def list_generation_tasks(
        self,
        *,
        drama_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if drama_id:
            clauses.append("drama_id = ?")
            values.append(drama_id)
        if status:
            clauses.append("status = ?")
            values.append(status)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(max(1, min(int(limit), 200)))
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT task_id, task_type, drama_id, episode_id, status, provider,
                       model_name, media_url, media_type, latency_ms, degrade_reason,
                       result_json, created_at_ms, updated_at_ms
                FROM generation_tasks
                {where_sql}
                ORDER BY updated_at_ms DESC
                LIMIT ?
                """,
                values,
            ).fetchall()
        return [_format_generation_task_row(row) for row in rows]

    def delete_generation_tasks_by_statuses(
        self,
        *,
        statuses: set[str],
        drama_id: str | None = None,
    ) -> int:
        normalized_statuses = [status for status in sorted(statuses) if status]
        if not normalized_statuses:
            return 0
        placeholders = ",".join("?" for _ in normalized_statuses)
        clauses = [f"status IN ({placeholders})"]
        values: list[Any] = [*normalized_statuses]
        if drama_id:
            clauses.append("drama_id = ?")
            values.append(drama_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM generation_tasks WHERE {' AND '.join(clauses)}",
                values,
            )
            return max(int(cursor.rowcount or 0), 0)

    def clear_all(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                DELETE FROM watch_progress;
                DELETE FROM analytics_events;
                DELETE FROM interaction_records;
                DELETE FROM ai_artifact_attempts;
                DELETE FROM saved_moments;
                DELETE FROM generation_tasks;
                """
            )


@lru_cache(maxsize=8)
def _get_store_for_path(path_text: str) -> RuntimeSQLiteStore:
    return RuntimeSQLiteStore(Path(path_text))


def get_runtime_store() -> RuntimeSQLiteStore:
    return _get_store_for_path(str(resolve_runtime_db_path()))


def reset_runtime_store_for_tests() -> None:
    _get_store_for_path.cache_clear()


def _parse_properties_json(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _format_generation_task_row(row: sqlite3.Row) -> dict[str, Any]:
    result = _parse_properties_json(row["result_json"])
    return {
        "taskId": str(row["task_id"] or ""),
        "taskType": str(row["task_type"] or ""),
        "dramaId": str(row["drama_id"] or ""),
        "episodeId": str(row["episode_id"] or ""),
        "status": str(row["status"] or ""),
        "provider": str(row["provider"] or ""),
        "modelName": str(row["model_name"] or ""),
        "mediaUrl": str(row["media_url"] or ""),
        "mediaType": str(row["media_type"] or ""),
        "latencyMs": int(row["latency_ms"] or 0),
        "degradeReason": str(row["degrade_reason"] or ""),
        "result": result,
        "createdAtMs": int(row["created_at_ms"] or 0),
        "updatedAtMs": int(row["updated_at_ms"] or 0),
    }


def _property_int(properties: dict[str, Any], *names: str) -> int:
    for name in names:
        value = properties.get(name)
        try:
            return max(int(float(value)), 0)
        except (TypeError, ValueError):
            continue
    return 0


def _percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    ordered = sorted(int(value) for value in values)
    index = int(round((len(ordered) - 1) * ratio))
    return ordered[max(0, min(index, len(ordered) - 1))]


def _percentile95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(int((len(ordered) * 0.95) + 0.999999) - 1, 0)
    return int(ordered[min(index, len(ordered) - 1)])
