import json
import pytest
from pathlib import Path
from httpx import ASGITransport, AsyncClient


class FakeVideoUnderstandingService:
    def __init__(self):
        self.calls: list[tuple[dict[str, object], str]] = []

    def analyze_episode(self, payload: dict[str, object], request_base_url: str):
        self.calls.append((payload, request_base_url))
        return {
            "capability": "video.understanding",
            "status": "ok",
            "cached": False,
            "model": {"provider": "fake", "model_name": "fake"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "result": {
                "episode_id": payload.get("episodeId", "tainai3_ep01"),
                "summary": "fake video understanding",
                "segments": [],
                "characters": [],
                "interaction_candidates": [],
                "evidence": [],
                "production_notes": [],
            },
        }


@pytest.mark.asyncio
async def test_video_understanding_endpoints_delegate_to_service(monkeypatch):
    from backend.app.main import app
    import backend.app.api.routes.video_ai as video_ai_routes

    fake_service = FakeVideoUnderstandingService()
    monkeypatch.setattr(video_ai_routes, "get_video_understanding_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        analyze_resp = await ac.post("/ai/video/analyze", json={"episodeId": "tainai3_ep01"})
        detail_resp = await ac.get("/ai/video/episodes/tainai3_ep01/understanding")

    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["data"]["result"]["summary"] == "fake video understanding"
    assert detail_resp.status_code == 200
    assert detail_resp.json()["data"]["result"]["episode_id"] == "tainai3_ep01"
    assert [call[0]["episodeId"] for call in fake_service.calls] == ["tainai3_ep01", "tainai3_ep01"]


def test_video_understanding_persists_evidence_json(tmp_path):
    from backend.app.video_understanding_service import VideoUnderstandingService

    service = VideoUnderstandingService(result_cache_dir=tmp_path)
    envelope = {
        "capability": "video.understanding",
        "status": "ok",
        "cached": False,
        "model": {"provider": "local", "model_name": "fallback"},
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "latency_ms": 12,
        "result": {
            "episode_id": "tainai3_ep01",
            "summary": "持久化测试",
            "segments": [],
            "characters": [],
            "interaction_candidates": [],
            "evidence": [],
            "production_notes": [],
        },
    }

    evidence_path = service._write_persistent_evidence(
        episode_id="tainai3_ep01",
        prompt_context={
            "episode": {"episodeId": "tainai3_ep01"},
            "video": {"fileName": "第1集.mp4"},
            "interactionNodes": [],
        },
        envelope=envelope,
        frame_items=[{"timeMs": 1000, "path": "frame.jpg", "dataUrl": "data:image/jpeg;base64,abc"}],
        audio_asset={"status": "ok", "path": "audio.wav", "format": "wav", "transcript": "台词", "source": "sidecar"},
        subtitle_asset={"status": "no_embedded_subtitle", "path": "", "text": "", "source": "ffmpeg"},
        ocr_asset={"status": "ok", "source": "sidecar_ocr", "cues": [{"time_ms": 1000, "text": "人物介绍"}]},
    )
    cached = service._read_persistent_evidence("tainai3_ep01")

    episode_cache_dir = tmp_path / "tainai3" / "tainai3_ep01"
    assert (episode_cache_dir / "understanding.json").exists()
    assert evidence_path.endswith("understanding.json")
    assert cached is not None
    assert cached["cached"] is True
    assert cached["latency_ms"] == 0
    assert cached["result"]["summary"] == "持久化测试"
    assert cached["result"]["evidence_manifest"]["source"] == "persistent_json"
    assert cached["artifact"]["source"] == "persistent_json"
    assert (episode_cache_dir / "latest_success.json").exists()
    assert (episode_cache_dir / "latest_attempt.json").exists()


def test_video_understanding_persistent_evidence_is_namespaced_by_drama(tmp_path):
    from backend.app.video_understanding_service import VideoUnderstandingService

    service = VideoUnderstandingService(result_cache_dir=tmp_path)
    envelope = {
        "capability": "video.understanding",
        "status": "ok",
        "cached": False,
        "model": {"provider": "local", "model_name": "fallback"},
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "latency_ms": 12,
        "result": {
            "episode_id": "new_drama_001_ep01",
            "summary": "新短剧持久化测试",
            "segments": [],
            "characters": [],
            "interaction_candidates": [],
            "evidence": [],
            "production_notes": [],
        },
    }

    evidence_path = service._write_persistent_evidence(
        drama_id="new_drama_001",
        episode_id="new_drama_001_ep01",
        prompt_context={
            "drama": {"dramaId": "new_drama_001"},
            "episode": {"episodeId": "new_drama_001_ep01"},
            "video": {"fileName": "episode.mp4"},
            "interactionNodes": [],
        },
        envelope=envelope,
        frame_items=[],
        audio_asset={"status": "ok", "path": "", "format": "", "transcript": "", "source": "none"},
        subtitle_asset={"status": "disabled", "path": "", "text": "", "source": "none"},
        ocr_asset={"status": "disabled", "source": "none", "cues": []},
    )
    cached = service._read_persistent_evidence("new_drama_001_ep01", drama_id="new_drama_001")

    assert (tmp_path / "new_drama_001" / "new_drama_001_ep01" / "understanding.json").exists()
    assert not (tmp_path / "new_drama_001_ep01" / "understanding.json").exists()
    assert Path(evidence_path).parts[-3:] == ("new_drama_001", "new_drama_001_ep01", "understanding.json")
    assert cached is not None
    assert cached["result"]["summary"] == "新短剧持久化测试"
    assert cached["result"]["evidence_manifest"]["source"] == "persistent_json"


def test_video_understanding_asset_dirs_are_namespaced_by_drama(tmp_path):
    from backend.app.video_understanding_service import VideoUnderstandingService

    service = VideoUnderstandingService(
        frame_cache_dir=tmp_path / "frames",
        audio_cache_dir=tmp_path / "audio",
        subtitle_cache_dir=tmp_path / "subtitles",
    )

    assert service._asset_episode_dir(service.frame_cache_dir, "new_drama_001", "ep01") == (
        tmp_path / "frames" / "new_drama_001" / "ep01"
    )
    assert service._asset_episode_dir(service.audio_cache_dir, "new_drama_001", "ep01") == (
        tmp_path / "audio" / "new_drama_001" / "ep01"
    )
    assert service._asset_episode_dir(service.subtitle_cache_dir, "new_drama_001", "ep01") == (
        tmp_path / "subtitles" / "new_drama_001" / "ep01"
    )


def test_video_understanding_keeps_success_file_when_new_run_degrades(tmp_path):
    from backend.app.video_understanding_service import VideoUnderstandingService

    service = VideoUnderstandingService(result_cache_dir=tmp_path)
    context = {
        "episode": {"episodeId": "tainai3_ep01"},
        "video": {"fileName": "episode.mp4"},
        "interactionNodes": [],
    }
    success = {
        "status": "ok",
        "artifact": {"version": 1},
        "result": {"summary": "稳定成功结果"},
    }
    degraded = {
        "status": "degraded",
        "artifact": {"version": 1, "restored_from_last_success": True},
        "result": {"summary": "本次降级结果"},
    }
    common_assets = {
        "frame_items": [],
        "audio_asset": {"status": "ok", "path": "", "format": "", "transcript": "", "source": "none"},
        "subtitle_asset": {"status": "disabled", "path": "", "text": "", "source": "none"},
        "ocr_asset": {"status": "disabled", "source": "none", "cues": []},
    }

    service._write_persistent_evidence(
        episode_id="tainai3_ep01",
        prompt_context=context,
        envelope=success,
        **common_assets,
    )
    service._write_persistent_evidence(
        episode_id="tainai3_ep01",
        prompt_context=context,
        envelope=degraded,
        **common_assets,
    )
    cached = service._read_persistent_evidence("tainai3_ep01")

    assert cached is not None
    assert cached["result"]["summary"] == "稳定成功结果"
    assert cached["result"]["evidence_manifest"]["source"] == "persistent_json"
    assert cached["artifact"]["source"] == "persistent_json"
    episode_cache_dir = tmp_path / "tainai3" / "tainai3_ep01"
    assert (episode_cache_dir / "versions" / "understanding_v001.json").exists()
    assert list((episode_cache_dir / "attempts").glob("understanding_degraded_*.json"))
    assert (episode_cache_dir / "latest_success.json").exists()
    assert (episode_cache_dir / "latest_attempt.json").exists()


def test_ocr_service_reads_sidecar_text(tmp_path):
    from backend.app.ocr_service import OCRService

    episode_dir = tmp_path / "tainai3_ep01"
    episode_dir.mkdir()
    frame_path = episode_dir / "frame_v2_01_44000.jpg"
    frame_path.write_bytes(b"fake")
    frame_path.with_suffix(".txt").write_text("科学院首席院士 容遇", encoding="utf-8")

    result = OCRService().analyze_frames([{"timeMs": 44_000, "path": str(frame_path)}])

    assert result["status"] == "ok"
    assert result["source"] == "sidecar_ocr"
    assert result["cues"][0]["text"] == "科学院首席院士 容遇"


def test_video_understanding_fallback_uses_transcript_and_ocr():
    from backend.app.video_understanding_service import VideoUnderstandingService

    service = VideoUnderstandingService()
    context = {
        "drama": {
            "title": "测试短剧",
            "characters": [{"name": "太奶奶"}],
        },
        "episode": {
            "episodeId": "tainai3_ep01",
            "title": "第1集",
            "summary": "主角开始反击。",
            "durationMs": 100_000,
        },
        "video": {"fileName": "第1集.mp4", "durationMs": 100_000, "toolStatus": "ok"},
        "frames": [{"timeMs": 1_000}],
        "mediaText": {
            "audio": {
                "status": "ok",
                "transcript": "容玉终于开口了，这次反击很爽。",
                "correctedTranscript": "容遇终于开口了，这次反击很爽。",
                "speakerTranscript": "容遇：终于开口了，这次反击很爽。",
                "speakerTurns": [
                    {
                        "speaker_id": "speaker_1",
                        "speaker_name": "容遇",
                        "start_ms": 0,
                        "end_ms": 2000,
                        "text": "终于开口了，这次反击很爽。",
                        "reason": "测试用说话人分段",
                    }
                ],
                "speakerRoleMap": [
                    {"speaker_id": "speaker_1", "role_name": "容遇", "reason": "测试绑定"}
                ],
                "source": "whisper_cpp",
            },
            "ocr": {
                "status": "ok",
                "cues": [{"time_ms": 1_000, "text": "科学院首席院士 容遇"}],
            },
            "subtitles": {"status": "no_embedded_subtitle", "textPreview": "", "source": "ffmpeg"},
        },
        "fusion": {"notes": ["角色表：太奶奶、容遇"]},
        "interactionNodes": [],
    }

    result = service._fallback_understanding(context)

    assert "容遇终于开口" in result["summary"]
    assert result["story_summary"] == result["summary"]
    assert "ASR" not in result["summary"]
    assert "OCR" not in result["summary"]
    assert result["audio_text"]["corrected_transcript"].startswith("容遇")
    assert result["audio_text"]["speaker_transcript"].startswith("容遇：")
    assert result["audio_text"]["speaker_turns"][0]["speaker_name"] == "容遇"
    assert result["screen_text_cues"][0]["text"] == "科学院首席院士 容遇"
    assert result["high_energy_lines"][0]["text"].startswith("容遇：")
    assert "反击" in result["high_energy_lines"][0]["text"]


def test_video_understanding_retries_with_minimal_schema_when_model_returns_bad_json(tmp_path):
    from backend.app.ai_service import AIService, ArkCredentials
    from backend.app.video_understanding_service import VideoUnderstandingService

    service = VideoUnderstandingService()
    ai_service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )
    calls: list[dict[str, object]] = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {"choices": [{"message": {"content": '{"story_summary":"坏 JSON",'}}]}
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "story_summary": "重试后生成的剧情简介",
                                "segments": [{"start_ms": 0, "end_ms": 30000, "summary": "开场冲突"}],
                                "high_energy_lines": ["情绪爆发"],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    ai_service._call_chat_completion_best_effort = fake_call
    context = {
        "drama": {"title": "测试剧", "characters": []},
        "episode": {
            "episodeId": "test_ep01",
            "title": "第1集",
            "summary": "注册表简介",
            "durationMs": 120000,
        },
        "video": {"fileName": "episode.mp4", "durationMs": 120000, "toolStatus": "ok"},
        "frames": [],
        "mediaText": {
            "audio": {"status": "disabled", "transcript": "", "correctedTranscript": "", "speakerTurns": []},
            "ocr": {"status": "disabled", "cues": []},
            "subtitles": {"status": "disabled", "textPreview": "", "source": "none"},
        },
        "fusion": {"notes": []},
        "interactionNodes": [],
    }

    result, usage, quality_status = service._run_remote_understanding(
        ai_service,
        context,
        [{"role": "user", "content": "完整 schema"}],
    )

    assert result["story_summary"] == "重试后生成的剧情简介"
    assert quality_status == "ok_retried_json"
    assert usage["total_tokens"] == 15
    assert len(calls) == 2
    assert calls[0]["max_tokens"] == 1100
    assert calls[1]["max_tokens"] < calls[0]["max_tokens"]
    assert "minimal" in calls[1]["capability"]


def test_keyframe_selection_uses_audio_energy_and_interaction_trigger():
    from backend.app.video_understanding_service import _select_keyframe_candidates

    selected = _select_keyframe_candidates(
        duration_seconds=180.0,
        max_frames=3,
        interaction_nodes=[
            {"title": "互动节点", "trigger": {"timeMs": 120_000}},
        ],
        utterances=[
            {"start_ms": 30_000, "end_ms": 32_000, "text": "证据就在这里！真相已经揭开！"},
        ],
    )

    sources = {item["source"] for item in selected}
    assert "audio_energy" in sources
    assert "interaction_trigger" in sources


def test_asr_service_preserves_speaker_metadata():
    from backend.app.asr_service import _normalize_utterances

    utterances = _normalize_utterances(
        [
            {
                "start_time": 1000,
                "end_time": 2500,
                "text": "你终于回来了。",
                "speaker_id": "SPEAKER_00",
                "speakerName": "容遇",
            }
        ]
    )

    assert utterances[0]["speaker_id"] == "SPEAKER_00"
    assert utterances[0]["speaker_label"] == "容遇"
    assert utterances[0]["text"] == "你终于回来了。"


def test_speaker_role_matching_normalizes_alias_and_distinguishes_family_members():
    from backend.app.video_understanding_service import (
        _build_character_profiles,
        _build_role_vocabulary,
        _build_speaker_turns,
    )

    profiles = _build_character_profiles(
        [
            {
                "character_id": "char_grandma",
                "name": "太奶奶",
                "canonical_name": "容遇",
                "aliases": ["太奶奶"],
                "role_type": "lead",
            },
            {
                "character_id": "char_family",
                "name": "家族少爷",
                "canonical_name": "家族少爷",
                "aliases": ["少爷", "少爷们", "大少爷", "二少爷"],
                "role_type": "family_group",
            },
        ]
    )
    turns = _build_speaker_turns(
        transcript="",
        utterances=[
            {"speaker_id": "SPEAKER_00", "speaker_label": "太奶奶", "text": "我回来了。"},
            {"speaker_id": "SPEAKER_01", "speaker_label": "大少爷", "text": "我来处理。"},
            {"speaker_id": "SPEAKER_02", "speaker_label": "少爷", "text": "我们到了。"},
        ],
        role_vocabulary=_build_role_vocabulary(profiles),
        character_profiles=profiles,
        ocr_cues=[],
    )
    turns_by_speaker = {item["speaker_id"]: item for item in turns}

    assert turns_by_speaker["SPEAKER_00"]["speaker_name"] == "容遇"
    assert turns_by_speaker["SPEAKER_00"]["speaker_alias"] == "太奶奶"
    assert turns_by_speaker["SPEAKER_01"]["speaker_name"] == "大少爷"
    assert turns_by_speaker["SPEAKER_01"]["speaker_role"] == "家族少爷"
    assert turns_by_speaker["SPEAKER_02"]["speaker_name"].startswith("家族少爷")


def test_unmatched_generic_speaker_is_marked_as_crowd():
    from backend.app.video_understanding_service import _build_character_profiles, _infer_speaker_role_map

    profiles = _build_character_profiles(
        [{"name": "太奶奶", "canonical_name": "容遇", "aliases": ["太奶奶"], "role_type": "lead"}]
    )
    mappings = _infer_speaker_role_map(
        [
            {"speaker_id": "SPEAKER_00", "speaker_label": "太奶奶", "text": "我回来了。"},
            {"speaker_id": "SPEAKER_01", "text": "快看季家少爷们来了，那不是季家大少爷吗？"},
        ],
        profiles,
        [],
    )
    mapping_by_speaker = {item["speaker_id"]: item for item in mappings}

    assert mapping_by_speaker["SPEAKER_00"]["canonical_role_name"] == "容遇"
    assert mapping_by_speaker["SPEAKER_01"]["role_type"] == "crowd"
    assert mapping_by_speaker["SPEAKER_01"]["role_name"] == "围观群众1"
    assert mapping_by_speaker["SPEAKER_01"]["mentioned_role_name"] == "家族少爷"


def test_specific_family_alias_can_be_promoted_to_member_identity():
    from backend.app.video_understanding_service import _build_character_profiles, _infer_speaker_role_map

    profiles = _build_character_profiles(
        [{"name": "家族少爷", "canonical_name": "家族少爷", "aliases": ["少爷", "大少爷", "二少爷"], "role_type": "family_group"}]
    )
    mappings = _infer_speaker_role_map(
        [
            {"speaker_id": "SPEAKER_00", "speaker_label": "太奶奶", "text": "我回来了。"},
            {"speaker_id": "SPEAKER_01", "text": "大少爷来了，二少爷也到了。"},
        ],
        profiles,
        [],
    )
    mapping_by_speaker = {item["speaker_id"]: item for item in mappings}

    assert mapping_by_speaker["SPEAKER_01"]["role_type"] == "family_member"
    assert mapping_by_speaker["SPEAKER_01"]["role_name"] in {"大少爷", "二少爷"}
    assert mapping_by_speaker["SPEAKER_01"]["confidence"] >= 0.5


def test_crowd_speaker_turn_does_not_expose_mentioned_alias_as_identity():
    from backend.app.video_understanding_service import _build_character_profiles, _build_role_vocabulary, _build_speaker_turns

    profiles = _build_character_profiles([{"name": "太奶奶", "canonical_name": "容遇", "aliases": ["太奶奶"], "role_type": "lead"}])
    turns = _build_speaker_turns(
        transcript="",
        utterances=[{"speaker_id": "SPEAKER_01", "text": "快看容遇来了！"}],
        role_vocabulary=_build_role_vocabulary(profiles),
        character_profiles=profiles,
        ocr_cues=[],
    )

    assert turns[0]["speaker_name"] == "围观群众1"
    assert turns[0]["speaker_role_type"] == "crowd"
    assert "speaker_alias" not in turns[0]
