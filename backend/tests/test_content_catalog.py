import json

import pytest
from httpx import ASGITransport, AsyncClient


def _seed_video_understanding_summaries(root, summaries):
    for episode_no, summary in summaries.items():
        episode_dir = root / f"tainai3_ep{episode_no:02d}"
        episode_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "envelope": {
                "result": {
                    "summary": summary,
                    "story_summary": summary,
                }
            }
        }
        (episode_dir / "latest_success.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


def _seed_story_summary_cache(root, drama_description, episode_summaries):
    story_dir = root / "tainai3"
    story_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "prompt_version": "content.story_summary/p2-grounded-platform-copy",
        "status": "ok",
        "generated_at_ms": 1900000000000,
        "latency_ms": 1234,
        "model": {"model_name": "doubao-seed-test"},
        "result": {
            "drama_description": drama_description,
            "episodes": [
                {
                    "episode_id": f"tainai3_ep{episode_no:02d}",
                    "summary": summary,
                }
                for episode_no, summary in episode_summaries.items()
            ],
        },
    }
    (story_dir / "story_summaries.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _seed_registry_story_summary_cache(root, drama_id, episode_prefix, drama_description, episode_summaries):
    story_dir = root / drama_id
    story_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "prompt_version": "content.story_summary/p2-grounded-platform-copy",
        "status": "ok",
        "generated_at_ms": 1900000000000,
        "latency_ms": 2345,
        "model": {"model_name": "doubao-seed-new-drama"},
        "result": {
            "drama_description": drama_description,
            "episodes": [
                {
                    "episode_id": f"{episode_prefix}{episode_no:02d}",
                    "summary": summary,
                }
                for episode_no, summary in episode_summaries.items()
            ],
        },
    }
    (story_dir / "story_summaries.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_story_summary_cache_preserves_richer_platform_copy(monkeypatch, tmp_path):
    import backend.app.content_catalog as content_catalog

    drama_description = (
        "这是一部围绕家族身份反转展开的短剧，女主以看似年轻的身份重新回到家族中心，"
        "面对晚辈误解、内部权力拉扯和外部危机，她没有急着摊牌，而是一步步用判断力和气场稳住局面。"
        "故事的爽点不只是身份揭露，更在于她如何借每一次试探反制质疑，把被动处境转成主动掌控。"
        "前五集持续铺垫家族关系、旧事线索和关键冲突，让观众在猜身份、看反转、等打脸之间形成连续追看动力。"
        "简介需要像短剧详情页文案一样交代人物处境、核心矛盾、情绪期待和后续悬念，而不是一句话概括剧情。"
        "当女主不断用细节证明自己与家族旧事有关时，晚辈们的怀疑、旁人的试探和家族利益的暗流也同步升级。"
        "这类文案在页面上要能支撑用户点击播放，所以必须保留足够的剧情张力和角色关系，不应被过早截断。"
    )
    episode_summary = (
        "女主刚进入家族就被质疑来历，几位晚辈态度各异，场面从试探变成正面对峙。"
        "她没有直接说明身份，而是抓住对方话里的破绽稳住节奏，也让后续身份反转有了更强悬念。"
        "本集重点是建立人物关系和第一轮冲突，让观众知道她处在被怀疑的位置，同时期待下一步如何反制。"
    )
    _seed_story_summary_cache(tmp_path, drama_description, {episode_no: episode_summary for episode_no in range(1, 6)})
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)

    cached = content_catalog._read_story_summary_cache("tainai3")

    assert len(cached["drama_description"]) > 300
    assert cached["drama_description"].endswith("。")
    assert len(cached["episodes"]["tainai3_ep01"]) > 90
    assert "speaker" not in cached["drama_description"].lower()
    assert "ASR" not in cached["drama_description"]


def test_story_summary_cache_expands_too_short_model_copy(monkeypatch, tmp_path):
    import backend.app.content_catalog as content_catalog

    _seed_registry_story_summary_cache(
        tmp_path,
        "beipai_xunbao",
        "beipai_xunbao_ep",
        "主角一行围绕北派寻宝和古玩线索追查秘密，各方利益交错，危机不断升级。",
        {
            episode_no: "线索出现后，主角一行继续判断真假，局势变得更加紧张。"
            for episode_no in range(1, 6)
        },
    )
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)

    cached = content_catalog._read_story_summary_cache("beipai_xunbao")

    assert len(cached["drama_description"]) >= content_catalog.STORY_SUMMARY_DRAMA_MIN_CHARS
    assert all(
        len(summary) >= content_catalog.STORY_SUMMARY_EPISODE_MIN_CHARS
        for summary in cached["episodes"].values()
    )
    assert "speaker" not in cached["drama_description"].lower()
    assert "ASR" not in cached["drama_description"]


def test_episode_summary_expansion_uses_natural_copy_without_meta_template():
    import backend.app.content_catalog as content_catalog

    summary = content_catalog._ensure_episode_summary_minimum(
        summary="女主做好饭菜拨通电话，和早已积怨的丈夫在离婚节点正面碰撞。",
        drama_id="xingde_xiangyu_lihunshi",
        episode_id="xingde_xiangyu_lihunshi_ep01",
        drama_description=(
            "原本积怨已久的夫妻走到离婚关口，积压多年的过往误会、现实里的重重压力接连爆发，"
            "二人在一次次紧绷对峙中不断撞见新的变数，情感纠葛越缠越深。"
        ),
    )

    assert len(summary) >= content_catalog.STORY_SUMMARY_EPISODE_MIN_CHARS
    assert "本集放在整部剧" not in summary
    assert "的主线中" not in summary
    assert "…" not in summary
    assert "后续冲突升级与反转选择" not in summary
    assert summary.startswith("女主做好饭菜拨通电话")
    assert summary.endswith("。")


@pytest.mark.asyncio
async def test_content_catalog_serves_registry_drama_without_touching_builtin(monkeypatch, tmp_path):
    from backend.app.main import app

    config_dir = tmp_path / "dramas"
    config_dir.mkdir()
    content_root = tmp_path / "new_drama_assets"
    content_root.mkdir()
    (content_root / "第1集.mp4").write_bytes(b"fake-video-1")
    (content_root / "第2集.mp4").write_bytes(b"fake-video-2")
    (config_dir / "new_drama_001.json").write_text(
        json.dumps(
            {
                "dramaId": "new_drama_001",
                "title": "新短剧标题",
                "contentRoot": str(content_root),
                "episodeCount": 2,
                "episodeIdPrefix": "new_drama_001_ep",
                "cover": "https://cdn.example.test/new.jpg",
                "coverStyle": "identity_reveal_poster",
                "coverBadge": "新剧预热",
                "coverHook": "一眼进入身份反转名场面",
                "coverPalette": {
                    "primary": "#24110D",
                    "secondary": "#8A4F22",
                    "accent": "#F8D36D",
                },
                "tags": ["逆袭", "反转"],
                "danmakuEvidencePath": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(config_dir))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        home_resp = await ac.get("/home/recommend")
        detail_resp = await ac.get("/dramas/new_drama_001")
        episodes_resp = await ac.get("/dramas/new_drama_001/episodes")
        play_resp = await ac.get("/episodes/new_drama_001_ep01/play")
        media_resp = await ac.get("/media/episodes/new_drama_001_ep01")
        builtin_resp = await ac.get("/dramas/tainai3")

    assert home_resp.status_code == 200
    home_ids = [item["drama_id"] for item in home_resp.json()["data"]["items"]]
    assert "tainai3" in home_ids
    assert "new_drama_001" in home_ids
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["drama_id"] == "new_drama_001"
    assert detail["title"] == "新短剧标题"
    assert detail["cover_style"] == "identity_reveal_poster"
    assert detail["cover_badge"] == "新剧预热"
    assert detail["cover_hook"] == "一眼进入身份反转名场面"
    assert detail["cover_palette"] == {
        "primary": "#24110D",
        "secondary": "#8A4F22",
        "accent": "#F8D36D",
    }
    assert detail["latest_episode_no"] == 2
    home_item = next(item for item in home_resp.json()["data"]["items"] if item["drama_id"] == "new_drama_001")
    assert home_item["cover_style"] == detail["cover_style"]
    assert home_item["cover_badge"] == detail["cover_badge"]
    assert home_item["cover_hook"] == detail["cover_hook"]
    assert home_item["cover_palette"] == detail["cover_palette"]
    assert episodes_resp.status_code == 200
    episodes = episodes_resp.json()["data"]["episodes"]
    assert [item["episode_id"] for item in episodes] == ["new_drama_001_ep01", "new_drama_001_ep02"]
    assert episodes[0]["play_url"].endswith("/media/episodes/new_drama_001_ep01")
    assert play_resp.status_code == 200
    assert play_resp.json()["data"]["episode_id"] == "new_drama_001_ep01"
    assert media_resp.status_code == 200
    assert media_resp.content == b"fake-video-1"
    assert builtin_resp.status_code == 200
    assert builtin_resp.json()["data"]["drama_id"] == "tainai3"


@pytest.mark.asyncio
async def test_registry_drama_maps_logical_episode_to_source_file(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    config_dir = tmp_path / "dramas"
    config_dir.mkdir()
    content_root = tmp_path / "beipai_assets"
    content_root.mkdir()
    (content_root / "第63集.mp4").write_bytes(b"beipai-63")
    (content_root / "第64集.mp4").write_bytes(b"beipai-64")
    (config_dir / "beipai_xunbao.json").write_text(
        json.dumps(
            {
                "dramaId": "beipai_xunbao",
                "title": "北派寻宝笔记",
                "contentRoot": str(content_root),
                "episodeCount": 2,
                "episodeIdPrefix": "beipai_xunbao_ep",
                "episodeNumberStart": 63,
                "episodeFilePattern": "第{source_episode_no}集.mp4",
                "description": "寻宝小队深入北派秘局，在古玩线索和人心试探中步步接近真相。",
                "interactionHint": "适合围绕线索判断和阵营选择设计互动。",
                "coverLayers": {
                    "identity_label": "寻宝悬疑",
                    "heat_label": "88.6万人观看",
                    "share_hint": "",
                },
                "episodeSummaries": {
                    "63": "第63集｜寻宝线索重新汇合，主角一行在试探中判断下一步方向。",
                    "64": "第64集｜新的古玩信息浮出水面，真假线索让局势继续紧绷。",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path / "video_understanding_results")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        detail_resp = await ac.get("/dramas/beipai_xunbao")
        episodes_resp = await ac.get("/dramas/beipai_xunbao/episodes")
        play_resp = await ac.get("/episodes/beipai_xunbao_ep01/play")
        media_resp = await ac.get("/media/episodes/beipai_xunbao_ep01")
        status_resp = await ac.get("/dramas/registry/status")

    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["latest_episode_no"] == 64
    assert detail["description"].startswith("寻宝小队")
    assert detail["cover_layers"]["identity_label"] == "寻宝悬疑"
    assert episodes_resp.status_code == 200
    episodes = episodes_resp.json()["data"]["episodes"]
    assert [item["episode_id"] for item in episodes] == ["beipai_xunbao_ep01", "beipai_xunbao_ep02"]
    assert [item["episode_no"] for item in episodes] == [63, 64]
    assert episodes[0]["title"] == "第63集"
    assert episodes[0]["summary"].startswith("第63集")
    assert play_resp.status_code == 200
    assert play_resp.json()["data"]["episode_no"] == 63
    assert media_resp.status_code == 200
    assert media_resp.content == b"beipai-63"
    status_item = next(item for item in status_resp.json()["data"]["items"] if item["drama_id"] == "beipai_xunbao")
    assert status_item["ready"] is True


@pytest.mark.asyncio
async def test_registry_drama_exposes_full_interaction_feature_set(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        play_resp = await ac.get("/episodes/jiali_jiawai_ep01/play")
        events_resp = await ac.get("/episodes/jiali_jiawai_ep01/timed-events")
        moments_resp = await ac.get("/dramas/jiali_jiawai/shareable-moments")
        moment = None
        if moments_resp.status_code == 200 and moments_resp.json()["data"]["items"]:
            moment = moments_resp.json()["data"]["items"][0]
        save_resp = await ac.post("/moments/save", json={**(moment or {}), "clientTsMs": 1_900_000_000_000})
        saved_resp = await ac.get("/moments/saved", params={"drama_id": "jiali_jiawai"})
        demo_resp = await ac.get("/demo/route", params={"drama_id": "jiali_jiawai"})
        mode_resp = await ac.get("/demo/mode", params={"drama_id": "jiali_jiawai"})

    assert play_resp.status_code == 200
    assert play_resp.json()["data"]["duration_ms"] > 0
    assert events_resp.status_code == 200
    events = events_resp.json()["data"]["events"]
    assert events
    assert events_resp.json()["data"]["drama"]["dramaId"] == "jiali_jiawai"
    assert moments_resp.status_code == 200
    assert moment is not None
    assert moment["dramaId"] == "jiali_jiawai"
    assert moment["episodeId"].startswith("jiali_jiawai_ep")
    assert moment["startMs"] < moment["endMs"]
    assert save_resp.status_code == 200
    assert save_resp.json()["data"]["dramaId"] == "jiali_jiawai"
    assert saved_resp.json()["data"]["items"][0]["dramaId"] == "jiali_jiawai"
    assert demo_resp.status_code == 200
    assert demo_resp.json()["data"]["dramaId"] == "jiali_jiawai"
    assert demo_resp.json()["data"]["entry"]["episodeId"].startswith("jiali_jiawai_ep")
    assert mode_resp.status_code == 200
    assert mode_resp.json()["data"]["dramaId"] == "jiali_jiawai"


@pytest.mark.asyncio
async def test_beipai_registry_drama_uses_source_episode_numbers_for_full_features():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        episodes_resp = await ac.get("/dramas/beipai_xunbao/episodes")
        play_resp = await ac.get("/episodes/beipai_xunbao_ep01/play")
        events_resp = await ac.get("/episodes/beipai_xunbao_ep01/timed-events")
        moments_resp = await ac.get("/dramas/beipai_xunbao/shareable-moments")
        demo_resp = await ac.get("/demo/route", params={"drama_id": "beipai_xunbao"})

    assert episodes_resp.status_code == 200
    episodes = episodes_resp.json()["data"]["episodes"]
    assert [item["episode_no"] for item in episodes] == [63, 64, 65, 66, 67]
    assert [item["episode_id"] for item in episodes][:2] == ["beipai_xunbao_ep01", "beipai_xunbao_ep02"]
    assert episodes[0]["title"] == "第63集"
    assert play_resp.status_code == 200
    assert play_resp.json()["data"]["episode_no"] == 63
    assert play_resp.json()["data"]["duration_ms"] == 297365
    assert events_resp.status_code == 200
    assert events_resp.json()["data"]["eventCount"] >= 3
    assert moments_resp.status_code == 200
    assert moments_resp.json()["data"]["items"][0]["episodeNo"] == 63
    assert demo_resp.status_code == 200
    assert demo_resp.json()["data"]["routeId"] == "beipai_xunbao_defense_demo_v1"


@pytest.mark.asyncio
async def test_registry_dramas_expose_cover_assets():
    from backend.app.main import app

    expected_assets = {
        "beipai_xunbao": "北派寻宝笔记.png",
        "jiali_jiawai": "家里家外.png",
        "xingde_xiangyu_lihunshi": "幸得相遇离婚时.png",
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        home_resp = await ac.get("/home/recommend")
        detail_responses = {
            drama_id: await ac.get(f"/dramas/{drama_id}") for drama_id in expected_assets
        }
        media_responses = {
            drama_id: await ac.get(f"/media/drama-covers/{asset_name}")
            for drama_id, asset_name in expected_assets.items()
        }

    assert home_resp.status_code == 200
    home_items = {item["drama_id"]: item for item in home_resp.json()["data"]["items"]}
    for drama_id, asset_name in expected_assets.items():
        detail_resp = detail_responses[drama_id]
        media_resp = media_responses[drama_id]
        assert detail_resp.status_code == 200
        detail = detail_resp.json()["data"]
        expected_url = f"http://test/media/drama-covers/{asset_name}"
        assert detail["cover_url"] == expected_url
        assert detail["cover_layers"]["portrait_url"] == expected_url
        assert home_items[drama_id]["cover_url"] == expected_url
        assert home_items[drama_id]["cover_layers"]["portrait_url"] == expected_url
        assert media_resp.status_code == 200
        assert media_resp.headers["content-type"] == "image/png"
        assert media_resp.content.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_drama_registry_status_reports_missing_media_and_load_errors(monkeypatch, tmp_path):
    from backend.app.main import app

    config_dir = tmp_path / "dramas"
    config_dir.mkdir()
    content_root = tmp_path / "registry_assets"
    content_root.mkdir()
    (content_root / "episode_1.mp4").write_bytes(b"fake-video")
    (config_dir / "registry_smoke.json").write_text(
        json.dumps(
            {
                "dramaId": "registry_smoke",
                "title": "注册表冒烟短剧",
                "contentRoot": str(content_root),
                "episodeCount": 2,
                "episodeIdPrefix": "registry_smoke_ep",
                "episodeFilePattern": "episode_{episode_no}.mp4",
                "cover": "",
                "tags": ["smoke"],
                "danmakuEvidencePath": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (config_dir / "bad.json").write_text(
        json.dumps({"dramaId": "bad drama id", "title": "bad"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(config_dir))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/dramas/registry/status")

    assert resp.status_code == 200
    data = resp.json()["data"]
    smoke = next(item for item in data["items"] if item["drama_id"] == "registry_smoke")
    assert smoke["ready"] is False
    assert smoke["media_ready_count"] == 1
    assert smoke["missing_episode_files"] == [
        {
            "episode_id": "registry_smoke_ep02",
            "episode_no": 2,
            "logical_episode_no": 2,
            "file_name": "episode_2.mp4",
        }
    ]
    assert data["ready_count"] < data["total_count"]
    assert data["load_errors"][0]["file_name"] == "bad.json"


@pytest.mark.asyncio
async def test_registry_drama_media_returns_404_when_file_missing(monkeypatch, tmp_path):
    from backend.app.main import app

    config_dir = tmp_path / "dramas"
    config_dir.mkdir()
    content_root = tmp_path / "new_drama_assets"
    content_root.mkdir()
    (config_dir / "new_drama_002.json").write_text(
        json.dumps(
            {
                "dramaId": "new_drama_002",
                "title": "缺素材短剧",
                "contentRoot": str(content_root),
                "episodeCount": 1,
                "episodeIdPrefix": "new_drama_002_ep",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(config_dir))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        play_resp = await ac.get("/episodes/new_drama_002_ep01/play")
        media_resp = await ac.get("/media/episodes/new_drama_002_ep01")

    assert play_resp.status_code == 200
    assert media_resp.status_code == 404
    assert media_resp.json()["message"] == "episode media not found"


@pytest.mark.asyncio
async def test_episode_evidence_graph_links_interactions_to_multimodal_evidence(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    understanding_dir = tmp_path / "tainai3_ep01"
    understanding_dir.mkdir(parents=True, exist_ok=True)
    understanding_payload = {
        "envelope": {
            "result": {
                "summary": "容遇进入纪家后被质疑身份，但她用气场压住局面。",
                "audio_text": {
                    "transcript": "你到底是谁？",
                    "speaker_turns": [
                        {"start_ms": 43000, "end_ms": 47000, "speaker": "晚辈", "text": "你到底是谁？"},
                    ],
                },
                "screen_text_cues": [
                    {"time_ms": 44000, "text": "容遇"},
                ],
                "interaction_candidates": [
                    {
                        "time_ms": 44000,
                        "type": "REACTION_PULSE",
                        "question": "容遇登场，你第一反应？",
                        "reason": "人物登场与身份质疑同时出现。",
                        "options": ["气场压住", "继续看"],
                    }
                ],
            }
        },
        "assets": {
            "frames": [
                {
                    "timeMs": 44000,
                    "path": "tmp/video_understanding_frames/tainai3_ep01/frame_044.jpg",
                    "samplingReason": "容遇登场",
                }
            ]
        },
    }
    (understanding_dir / "understanding.json").write_text(
        json.dumps(understanding_payload, ensure_ascii=False),
        encoding="utf-8",
    )
    danmaku_path = tmp_path / "danmaku.json"
    danmaku_path.write_text(
        json.dumps(
            {
                "episodes": {
                    "tainai3_ep01": {
                        "candidates": [
                            {
                                "candidateId": "danmaku_ep01_044",
                                "timeMs": 44000,
                                "reason": "聚合弹幕热区与人物登场共振。",
                                "evidenceRefs": [
                                    "danmaku_bucket:tainai3_ep01:044",
                                    "reviewed_frame:tainai3_ep01:044",
                                ],
                                "confidence": 0.91,
                                "reviewStatus": "accepted",
                            }
                        ]
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", danmaku_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/episodes/tainai3_ep01/evidence-graph", params={"timeMs": 44000})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["episodeId"] == "tainai3_ep01"
    assert data["focusTimeMs"] == 44000
    assert data["nodeCount"] >= 1
    assert data["evidenceCount"] >= 4
    assert data["relationCount"] >= 1
    assert data["nodes"][0]["whyText"]
    assert data["nodes"][0]["confidence"] > 0
    assert data["storyFacets"]["characters"]
    assert "身份" in data["storyFacets"]["conflicts"][0]
    assert data["explanations"][0]["nodeId"] == data["nodes"][0]["nodeId"]
    assert data["explanations"][0]["storyTags"]
    assert data["explanations"][0]["audienceResonance"]
    evidence_kinds = {item["kind"] for item in data["evidence"]}
    assert {"frame", "asr_segment", "ocr_cue", "danmaku_bucket"}.issubset(evidence_kinds)
    relation = data["relations"][0]
    assert relation["fromNodeId"]
    assert relation["toEvidenceRef"]


@pytest.mark.asyncio
async def test_home_recommend_returns_video_understanding_drama(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    _seed_video_understanding_summaries(
        tmp_path,
        {
            1: "第1集｜容遇来到七十年后的纪家，被晚辈质疑身份。",
            2: "第2集｜纪家众人继续试探，容遇开始正面反击。",
            3: "第3集｜身份线索继续发酵，纪家成员态度出现动摇。",
            4: "第4集｜冲突升级为正面对线，容遇逐渐掌控局势。",
            5: "第5集｜人物关系和身份线索汇合，更大危机被吊起。",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/home/recommend")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert {"tainai3", "jiali_jiawai", "xingde_xiangyu_lihunshi", "beipai_xunbao"}.issubset(
        {item["drama_id"] for item in items}
    )
    assert items[0]["drama_id"] == "tainai3"
    assert items[0]["cover_style"] == "family_reversal_poster"
    assert items[0]["cover_badge"]
    assert items[0]["cover_hook"]
    assert items[0]["cover_palette"]["accent"].startswith("#")
    assert items[0]["cover_layers"]["identity_label"] == "身份反转"
    assert items[0]["cover_layers"]["heat_label"].endswith("人想看")
    assert items[0]["cover_layers"]["portrait_url"].startswith("http://test/")
    assert "打卡" in items[0]["cover_layers"]["share_hint"]
    assert items[0]["play_url"].startswith("http://test/")
    assert items[0]["content_source"] in {"backend", "cache"}
    assert items[0]["description"].startswith("1955年，容遇教授")
    assert "容遇来到七十年后的纪家" not in items[0]["description"]
    assert "第1集｜" not in items[0]["description"]
    assert "ASR" not in items[0]["description"]
    assert items[0]["interaction_hint"].startswith("剧情简介已预生成并缓存")


@pytest.mark.asyncio
async def test_home_highlight_feed_returns_playable_moment_stream(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", tmp_path / "missing.json")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/home/highlight-feed?size=3")
        spread_resp = await ac.get("/home/highlight-feed?size=5&strategy=episode_spread_v1")

    assert resp.status_code == 200
    body = resp.json()["data"]
    items = body["items"]
    assert body["feedType"] == "high_energy_moment"
    assert body["selectionStrategy"] == "heat_score_desc_v1"
    assert len(items) == 3
    assert items[0]["heatScore"] >= items[1]["heatScore"] >= items[2]["heatScore"]
    assert all(item["selectionStrategy"] == body["selectionStrategy"] for item in items)
    assert items[0]["playUrl"].startswith("http://test/")
    assert items[0]["episodeId"].startswith("tainai3_ep")
    spread = spread_resp.json()["data"]
    assert spread["selectionStrategy"] == "episode_spread_v1"
    assert len({item["episodeNo"] for item in spread["items"]}) == 5


@pytest.mark.asyncio
async def test_home_highlight_feed_supports_ab_strategy_family(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", tmp_path / "missing.json")

    transport = ASGITransport(app=app)
    strategies = ["interaction_first", "danmaku_first", "ai_evidence_first", "hybrid"]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        responses = {
            strategy: await ac.get(f"/home/highlight-feed?size=4&strategy={strategy}")
            for strategy in strategies
        }

    for strategy, resp in responses.items():
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["selectionStrategy"] == strategy
        assert data["abTest"]["enabled"] is True
        assert data["abTest"]["strategy"] == strategy
        assert data["items"]
        assert all(item["selectionStrategy"] == strategy for item in data["items"])
        evaluation = data["strategyEvaluation"]
        assert evaluation["selectionStrategy"] == strategy
        assert evaluation["strategyLabel"]
        assert evaluation["sampleSize"] == len(data["items"])
        assert evaluation["averageHeatScore"] >= 0
        assert evaluation["evidenceMix"]
        assert "CTR" in evaluation["metricPlan"][0]


@pytest.mark.asyncio
async def test_demo_route_links_existing_capabilities_and_survives_runtime_reset(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        first_resp = await ac.get("/demo/route")
        reset_runtime_store_for_tests()
        second_resp = await ac.get("/demo/route")

    assert first_resp.status_code == 200
    data = first_resp.json()["data"]
    assert data["routeId"] == "tainai3_defense_demo_v1"
    assert data["entry"]["episodeId"].startswith("tainai3_ep")
    assert data["entry"]["startMs"] >= 0
    assert data["checks"]["usesFakeData"] is False
    assert data["checks"]["restartSafe"] is True
    assert [step["stepId"] for step in data["steps"]] == [
        "home_highlight_feed",
        "player_highlight",
        "xray_evidence",
        "interaction_click",
        "aigc_generation",
        "operations_dashboard",
    ]
    assert data["steps"][2]["evidenceCount"] >= 1
    assert data["steps"][4]["api"] == "/ai/generation/tasks"
    assert second_resp.status_code == 200
    assert second_resp.json()["data"]["entry"]["episodeId"] == data["entry"]["episodeId"]


@pytest.mark.asyncio
async def test_demo_mode_status_exposes_fixed_route_and_sources(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/demo/mode?drama_id=tainai3")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["enabled"] is True
    assert data["routeId"] == "tainai3_defense_demo_v1"
    assert data["fixedStrategy"] == "heat_score_desc_v1"
    assert data["entry"]["episodeId"].startswith("tainai3_ep")
    assert data["contentSource"] in {"backend", "cache", "local_fallback"}
    assert data["fallbacks"]["homeFallbackAvailable"] is True
    assert data["fallbacks"]["lastSuccessArtifactAvailable"] in {True, False}
    assert [step["stepId"] for step in data["quickSteps"]] == [
        "home_highlight_feed",
        "player_highlight",
        "xray_evidence",
        "interaction_click",
        "aigc_generation",
        "operations_dashboard",
    ]


@pytest.mark.asyncio
async def test_drama_detail_and_episodes_use_video_understanding(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    _seed_video_understanding_summaries(
        tmp_path,
        {
            1: "第1集｜容遇来到七十年后的纪家，被晚辈质疑身份。",
            2: "第2集｜纪家众人继续试探，容遇开始正面反击。",
            3: "第3集｜身份线索继续发酵，纪家成员态度出现动摇。",
            4: "第4集｜冲突升级为正面对线，容遇逐渐掌控局势。",
            5: "第5集｜人物关系和身份线索汇合，更大危机被吊起。",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        drama_resp = await ac.get("/dramas/tainai3")
        episodes_resp = await ac.get("/dramas/tainai3/episodes")

    assert drama_resp.status_code == 200
    assert episodes_resp.status_code == 200

    drama_body = drama_resp.json()
    episodes_body = episodes_resp.json()
    assert drama_body["data"]["title"].startswith("十八岁太奶奶")
    assert drama_body["data"]["description"].startswith("1955年，容遇教授")
    assert "容遇来到七十年后的纪家" not in drama_body["data"]["description"]
    assert "第1集｜" not in drama_body["data"]["description"]
    assert "关键帧" not in drama_body["data"]["description"]
    assert drama_body["data"]["interaction_hint"].startswith("剧情简介已预生成并缓存")
    assert len(episodes_body["data"]["episodes"]) == 5
    assert episodes_body["data"]["episodes"][0]["episode_id"] == "tainai3_ep01"
    assert episodes_body["data"]["episodes"][4]["episode_id"] == "tainai3_ep05"
    assert episodes_body["data"]["episodes"][0]["summary"].startswith("容遇来到七十年后的纪家")
    assert episodes_body["data"]["episodes"][4]["summary"].startswith("人物关系和身份线索汇合")
    assert len(episodes_body["data"]["episodes"][0]["summary"]) >= content_catalog.STORY_SUMMARY_EPISODE_MIN_CHARS
    assert "第1集｜" not in episodes_body["data"]["episodes"][0]["summary"]


@pytest.mark.asyncio
async def test_story_summary_cache_overrides_drama_and_episode_copy(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    _seed_video_understanding_summaries(
        tmp_path,
        {
            1: "第1集｜容遇来到七十年后的纪家，被晚辈质疑身份。",
            2: "第2集｜纪家众人继续试探，容遇开始正面反击。",
        },
    )
    _seed_story_summary_cache(
        tmp_path,
        "1955年，容遇意外穿到七十年后的同名少女身上。她以十八岁外表闯入纪家，在误会、亲情和危机中一步步夺回主动权。",
        {
            1: "第1集｜容遇醒来后发现自己身处七十年后的纪家，年轻外表引发质疑，她先压住混乱场面。",
            2: "第2集｜纪家人的试探继续升级，容遇不急着摊牌，而是用行动让局面出现反转。",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        drama_resp = await ac.get("/dramas/tainai3")
        episodes_resp = await ac.get("/dramas/tainai3/episodes")

    assert drama_resp.status_code == 200
    assert episodes_resp.status_code == 200
    assert drama_resp.json()["data"]["description"].startswith("1955年，容遇意外穿到七十年后")
    assert "第1集｜" not in drama_resp.json()["data"]["description"]
    assert drama_resp.json()["data"]["interaction_hint"].startswith("剧情简介已预生成并缓存")
    episodes = episodes_resp.json()["data"]["episodes"]
    assert not episodes[0]["summary"].startswith("第1集")
    assert not episodes[1]["summary"].startswith("第2集")
    assert episodes[0]["summary"].startswith("容遇醒来后发现")
    assert episodes[1]["summary"].startswith("纪家人的试探继续升级")
    assert len(episodes[0]["summary"]) >= content_catalog.STORY_SUMMARY_EPISODE_MIN_CHARS
    assert len(episodes[1]["summary"]) >= content_catalog.STORY_SUMMARY_EPISODE_MIN_CHARS
    assert "speaker" not in episodes[0]["summary"].lower()
    assert "ASR" not in episodes[0]["summary"]


@pytest.mark.asyncio
async def test_story_summary_cache_status_and_refresh_keep_success_on_degrade(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "0")
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    _seed_story_summary_cache(
        tmp_path,
        "1955年，容遇意外穿到七十年后的同名少女身上。她以十八岁外表闯入纪家，在误会、亲情和危机中一步步夺回主动权。",
        {
            1: "第1集｜容遇醒来后发现自己身处七十年后的纪家，年轻外表引发质疑，她先压住混乱场面。",
            2: "第2集｜纪家人的试探继续升级，容遇不急着摊牌，而是用行动让局面出现反转。",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        status_resp = await ac.get("/story-summary/cache", params={"drama_id": "tainai3"})
        refresh_resp = await ac.post("/story-summary/cache/refresh", json={"dramaId": "tainai3"})

    assert status_resp.status_code == 200
    status_data = status_resp.json()["data"]
    assert status_data["status"] == "ok"
    assert status_data["source"] == "latest_success"
    assert status_data["model_name"] == "doubao-seed-test"
    assert status_data["latency_ms"] == 1234
    assert "speaker" not in status_data["drama_description"]
    assert "ASR" not in status_data["drama_description"]

    assert refresh_resp.status_code == 200
    refreshed = refresh_resp.json()["data"]
    assert refreshed["source"] == "latest_success"
    assert refreshed["drama_description"].startswith("1955年，容遇意外穿到七十年后")
    assert refreshed["latest_attempt"]["source"] == "latest_attempt"
    assert refreshed["latest_attempt"]["status"] in {"degraded", "ok"}
    assert "speaker" not in refreshed["drama_description"]


@pytest.mark.asyncio
async def test_story_summary_cache_status_uses_registry_drama_id(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    config_dir = tmp_path / "dramas"
    config_dir.mkdir()
    content_root = tmp_path / "new_drama_assets"
    content_root.mkdir()
    (config_dir / "new_drama_001.json").write_text(
        json.dumps(
            {
                "dramaId": "new_drama_001",
                "title": "新短剧",
                "contentRoot": str(content_root),
                "episodeCount": 2,
                "episodeIdPrefix": "new_drama_001_ep",
                "cover": "",
                "tags": ["反转"],
                "danmakuEvidencePath": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    _seed_registry_story_summary_cache(
        tmp_path,
        "new_drama_001",
        "new_drama_001_ep",
        "新短剧围绕身份误会和家族冲突展开，主角在质疑中一步步夺回主动权。",
        {
            1: "第1集：主角意外卷入家族风波，在陌生环境里先稳住局面。",
            2: "第2集：质疑升级，主角用行动反击，新的身份线索浮出水面。",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        status_resp = await ac.get("/story-summary/cache", params={"drama_id": "new_drama_001"})

    assert status_resp.status_code == 200
    data = status_resp.json()["data"]
    assert data["drama_id"] == "new_drama_001"
    assert data["source"] == "latest_success"
    assert data["model_name"] == "doubao-seed-new-drama"
    assert data["episodes"][0]["episode_id"] == "new_drama_001_ep01"
    assert data["episodes"][1]["summary"].startswith("第2集")


@pytest.mark.asyncio
async def test_registry_drama_detail_uses_own_story_summary_cache(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    config_dir = tmp_path / "dramas"
    config_dir.mkdir()
    content_root = tmp_path / "new_drama_assets"
    content_root.mkdir()
    (config_dir / "new_drama_001.json").write_text(
        json.dumps(
            {
                "dramaId": "new_drama_001",
                "title": "新短剧",
                "contentRoot": str(content_root),
                "episodeCount": 2,
                "episodeIdPrefix": "new_drama_001_ep",
                "description": "注册表原始简介不应优先展示",
                "episodeSummaries": {
                    "1": "注册表第一集简介不应优先展示",
                    "2": "注册表第二集简介不应优先展示",
                },
                "cover": "",
                "tags": ["反转"],
                "danmakuEvidencePath": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    _seed_registry_story_summary_cache(
        tmp_path,
        "new_drama_001",
        "new_drama_001_ep",
        "缓存生成的整剧简介，围绕人物冲突和反转主线展开。",
        {
            1: "缓存生成的第一集剧情简介，人物冲突正式爆发。",
            2: "缓存生成的第二集剧情简介，新线索推动局面反转。",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        drama_resp = await ac.get("/dramas/new_drama_001")
        episodes_resp = await ac.get("/dramas/new_drama_001/episodes")

    assert drama_resp.status_code == 200
    assert episodes_resp.status_code == 200
    assert drama_resp.json()["data"]["description"].startswith("缓存生成的整剧简介")
    assert drama_resp.json()["data"]["interaction_hint"].startswith("剧情简介已预生成并缓存")
    episodes = episodes_resp.json()["data"]["episodes"]
    assert episodes[0]["summary"].startswith("缓存生成的第一集剧情简介")
    assert episodes[1]["summary"].startswith("缓存生成的第二集剧情简介")


@pytest.mark.asyncio
async def test_requests_do_not_trigger_video_understanding_generation(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog
    import backend.app.video_understanding_service as video_understanding_service

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)

    def _fail_get_service():
        raise AssertionError("request path should not trigger video understanding generation")

    monkeypatch.setattr(video_understanding_service, "get_video_understanding_service", _fail_get_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        drama_resp = await ac.get("/dramas/tainai3")
        episodes_resp = await ac.get("/dramas/tainai3/episodes")
        home_resp = await ac.get("/home/recommend")

    assert drama_resp.status_code == 200
    assert episodes_resp.status_code == 200
    assert home_resp.status_code == 200
    assert drama_resp.json()["data"]["title"].startswith("十八岁太奶奶")
    assert len(episodes_resp.json()["data"]["episodes"]) == 5
    assert any(item["drama_id"] == "tainai3" for item in home_resp.json()["data"]["items"])
    assert home_resp.json()["data"]["items"][0]["content_source"] == "backend"


def test_technical_video_summary_is_not_used_as_visible_copy(monkeypatch, tmp_path):
    import json
    import backend.app.content_catalog as content_catalog

    episode_dir = tmp_path / "tainai3_ep01"
    episode_dir.mkdir(parents=True)
    (episode_dir / "latest_success.json").write_text(
        json.dumps(
            {
                "envelope": {
                    "result": {
                        "summary": "已基于 ASR/OCR/关键帧完成融合理解：容遇登场。",
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)

    episode = content_catalog.get_episode_by_id("tainai3_ep01")

    assert episode is not None
    assert len(episode["summary"]) >= content_catalog.STORY_SUMMARY_EPISODE_MIN_CHARS
    assert "1955年容遇教授意外身故" in episode["summary"]
    assert "第1集｜" not in episode["summary"]
    assert "ASR" not in episode["summary"]


def test_old_video_summary_without_story_field_is_ignored(monkeypatch, tmp_path):
    import json
    import backend.app.content_catalog as content_catalog

    episode_dir = tmp_path / "tainai3_ep01"
    episode_dir.mkdir(parents=True)
    (episode_dir / "latest_success.json").write_text(
        json.dumps(
            {
                "prompt_version": "video.understanding/p1-fusion",
                "envelope": {
                    "result": {
                        "summary": "容遇登场压住局面，人物身份线索开始铺开。",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)

    episode = content_catalog.get_episode_by_id("tainai3_ep01")

    assert episode is not None
    assert len(episode["summary"]) >= content_catalog.STORY_SUMMARY_EPISODE_MIN_CHARS
    assert "1955年容遇教授意外身故" in episode["summary"]
    assert "第1集｜" not in episode["summary"]
    assert episode["summary"] != "容遇登场压住局面，人物身份线索开始铺开。"


@pytest.mark.asyncio
async def test_episode_play_returns_play_url():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/episodes/tainai3_ep01/play")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["episode_id"] == "tainai3_ep01"
    assert body["data"]["episode_no"] == 1
    assert body["data"]["title"].startswith("第1集")
    assert body["data"]["play_url"].endswith("/media/episodes/tainai3_ep01")
    assert body["data"]["hls_url"].endswith("/media/hls/tainai3_ep01/index.m3u8")
    assert body["data"]["preferred_play_url"]
    assert body["data"]["hls_available"] in {True, False}


@pytest.mark.asyncio
async def test_episode_hls_asset_serves_playlist(tmp_path, monkeypatch):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    episode_dir = tmp_path / "tainai3_ep01"
    episode_dir.mkdir(parents=True)
    (episode_dir / "index.m3u8").write_text("#EXTM3U\n#EXT-X-ENDLIST\n", encoding="utf-8")
    monkeypatch.setattr(content_catalog, "DEFAULT_HLS_ROOT", tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/media/hls/tainai3_ep01/index.m3u8")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/vnd.apple.mpegurl")
    assert "#EXTM3U" in resp.text


@pytest.mark.asyncio
async def test_episode_media_head_returns_video_metadata():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.head("/media/episodes/tainai3_ep01")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("video/mp4")
    assert int(resp.headers["content-length"]) > 0
    assert resp.headers["accept-ranges"] == "bytes"
    assert resp.headers["cache-control"] == "public, max-age=3600"


@pytest.mark.asyncio
async def test_episode_media_supports_range_requests():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/media/episodes/tainai3_ep01",
            headers={"Range": "bytes=0-1023"},
        )

    assert resp.status_code == 206
    assert resp.headers["accept-ranges"] == "bytes"
    assert resp.headers["content-range"].startswith("bytes 0-1023/")
    assert resp.headers["cache-control"] == "public, max-age=3600"
    assert len(resp.content) == 1024


@pytest.mark.asyncio
async def test_episode_media_full_get_streams_video():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async with ac.stream("GET", "/media/episodes/tainai3_ep01") as resp:
            assert resp.status_code == 200
            assert resp.headers["accept-ranges"] == "bytes"
            first_chunk = b""
            async for chunk in resp.aiter_bytes():
                first_chunk = chunk
                break

    assert len(first_chunk) > 0


@pytest.mark.asyncio
async def test_interaction_submit_returns_feedback():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/interaction/submit",
            json={
                "submitId": "submit_test_001",
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep01",
                "nodeId": "n_045_tainai3_ep01_danmaku",
                "triggerMs": 45_000,
                "answer": {"optionId": "choice_1"},
                "clientTsMs": 1_900_000_000_000,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["recordId"].startswith("ir_")
    assert body["data"]["feedback"]["mode"] == "template"
    assert body["data"]["reward"]["growthValue"] == 5


@pytest.mark.asyncio
async def test_shareable_moments_can_be_listed_and_saved(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        list_resp = await ac.get("/dramas/tainai3/shareable-moments")
        moment = list_resp.json()["data"]["items"][0]
        save_resp = await ac.post(
            "/moments/save",
            json={
                **moment,
                "clientTsMs": 1_900_000_000_000,
            },
        )
        saved_resp = await ac.get("/moments/saved", params={"drama_id": "tainai3"})

    assert list_resp.status_code == 200
    assert moment["momentId"].startswith("moment_")
    assert moment["startMs"] < moment["endMs"]
    assert moment["sourceNodeId"]
    assert moment["heatScore"] > 0
    assert save_resp.status_code == 200
    assert save_resp.json()["data"]["momentId"] == moment["momentId"]
    saved_items = saved_resp.json()["data"]["items"]
    assert saved_items[0]["momentId"] == moment["momentId"]
    assert saved_items[0]["playUrl"].endswith(f"/media/episodes/{moment['episodeId']}")

    reset_runtime_store_for_tests()


@pytest.mark.asyncio
async def test_ai_reaction_interaction_submit_continues_playback():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/interaction/submit",
            json={
                "submitId": "submit_test_002",
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep01",
                "nodeId": "n_123_profile_text_reaction",
                "triggerMs": 123_000,
                "answer": {"optionId": "legend"},
                "clientTsMs": 1_900_000_000_000,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["nextAction"]["type"] == "CONTINUE"
    assert body["data"]["aggregate"]["legend"] > 0


@pytest.mark.asyncio
async def test_each_episode_has_independent_interaction_nodes():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ep01_resp = await ac.get("/episodes/tainai3_ep01/interaction-nodes")
        ep02_resp = await ac.get("/episodes/tainai3_ep02/interaction-nodes")
        ep04_resp = await ac.get("/episodes/tainai3_ep04/interaction-nodes")

    ep01_nodes = ep01_resp.json()["data"]["nodes"]
    ep02_nodes = ep02_resp.json()["data"]["nodes"]
    ep04_nodes = ep04_resp.json()["data"]["nodes"]
    ep02_timeline = ep02_resp.json()["data"]["timeline_items"]
    ep02_nodes_by_id = {node["id"]: node for node in ep02_nodes}
    assert {node["id"] for node in ep01_nodes} != {node["id"] for node in ep02_nodes}
    assert "n_118_ep02_counter_attack" in ep02_nodes_by_id
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["display"]["style"] == "加速包"
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["componentType"] == "AIGC_CARD"
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["display"]["componentType"] == "AIGC_CARD"
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["analyticsKey"].startswith("interaction_component.tainai3_ep02.")
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["placement"] == "CENTER"
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["safeArea"]["avoidProgressBar"] is True
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["maxLines"] == 2
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["aiInsert"]["generatedAsset"]["provider"]["name"] == "template_ffmpeg"
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["aiInsert"]["generatedAsset"]["title"] == "反击加速包"
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["options"][0]["branch"]["playbackMode"] == "REPLACE_MAIN"
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["options"][0]["branch"]["segmentId"] == ep02_nodes_by_id["n_118_ep02_counter_attack"]["aiInsert"]["generatedAsset"]["assetId"]
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["options"][0]["branch"]["returnSeekMs"] == ep02_nodes_by_id["n_118_ep02_counter_attack"]["trigger"]["timeMs"]
    assert ep02_nodes_by_id["n_118_ep02_counter_attack"]["options"][0]["branch"]["mediaUrl"].endswith("/media/aigc-inserts/tainai3_ep02/n_118_ep02_counter_attack.mp4")
    assert len(ep02_nodes) >= 4
    assert any("danmaku" in node["id"] for node in ep02_nodes)
    ep04_aigc_node = next(node for node in ep04_nodes if node.get("aiInsert"))
    assert ep04_aigc_node["aiInsert"]["type"] == "AIGC_MOMENTUM_CLIP"
    assert ep02_resp.json()["data"]["timelineSchemaVersion"] == "1.0"
    assert ep02_timeline[0]["track"] == "interaction_track"
    assert ep02_timeline[0]["triggerPolicy"]["timeMs"] == ep02_nodes[0]["trigger"]["timeMs"]
    assert ep02_timeline[0]["action"]["type"] == "SHOW_INTERACTION"
    assert ep02_timeline[0]["displayStyle"]["componentType"] in {"DANMAKU_STICKER", "AIGC_CARD", "CHOICE_CARD", "EVIDENCE_CARD", "REACTION_STICKER"}
    assert ep02_timeline[0]["displayStyle"]["placement"]
    assert ep02_timeline[0]["displayStyle"]["safeArea"]
    assert ep02_timeline[0]["analyticsKey"].startswith("interaction_component.tainai3_ep02.")
    assert ep02_timeline[0]["payload"]["id"] == ep02_nodes[0]["id"]


@pytest.mark.asyncio
async def test_timed_events_endpoint_returns_stable_standard_timeline():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        first_resp = await ac.get("/episodes/tainai3_ep02/timed-events")
        second_resp = await ac.get("/episodes/tainai3_ep02/timed-events")
        legacy_resp = await ac.get("/episodes/tainai3_ep02/interaction-nodes")

    assert first_resp.status_code == 200
    assert legacy_resp.status_code == 200
    data = first_resp.json()["data"]
    second = second_resp.json()["data"]
    legacy = legacy_resp.json()["data"]
    assert data["timelineSchemaVersion"] == "1.1"
    assert data["eventCount"] == len(data["events"]) == len(data["nodes"])
    first_event = data["events"][0]
    assert first_event["episodeId"] == "tainai3_ep02"
    assert first_event["componentType"]
    assert first_event["visualStyle"]
    assert first_event["generationSource"] in {"manual", "reviewed_model", "model", "rule"}
    assert len(first_event["payloadHash"]) == 16
    assert first_event["payloadHash"] == second["events"][0]["payloadHash"]
    assert isinstance(first_event["safeArea"], dict)
    assert first_event["maxLines"] >= 1
    assert isinstance(first_event["payload"], dict)
    assert first_event["payload"]["componentType"] == first_event["componentType"]
    assert legacy["timelineSchemaVersion"] == "1.0"


@pytest.mark.asyncio
async def test_interaction_candidate_review_updates_publish_queue(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", tmp_path / "missing.json")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        candidates_resp = await ac.get("/episodes/tainai3_ep01/interaction-candidates")
        candidate = candidates_resp.json()["data"]["items"][0]
        advice = candidate["orchestrationAdvice"]
        review_resp = await ac.post(
            f"/interaction-candidates/{candidate['candidateId']}/review",
            json={
                "episodeId": "tainai3_ep01",
                "reviewStatus": "rejected",
                "reviewNote": "测试拒绝",
            },
        )
        reviewed_resp = await ac.get("/episodes/tainai3_ep01/interaction-candidates")
        events_resp = await ac.get("/episodes/tainai3_ep01/timed-events")

    assert candidates_resp.status_code == 200
    assert advice["recommendedComponentType"]
    assert advice["placement"]
    assert advice["safeArea"]["avoidBottomControls"] is True
    assert advice["publishEligible"] is True
    assert isinstance(advice["evidenceSummary"], str)
    assert review_resp.status_code == 200
    assert review_resp.json()["data"]["reviewStatus"] == "rejected"
    assert reviewed_resp.json()["data"]["items"][0]["reviewStatus"] == "rejected"
    assert reviewed_resp.json()["data"]["items"][0]["orchestrationAdvice"]["publishEligible"] is False
    assert events_resp.json()["data"]["eventCount"] == len(events_resp.json()["data"]["nodes"]) == 2


@pytest.mark.asyncio
async def test_danmaku_emotion_report_uses_aggregate_evidence_without_raw_rows(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    evidence_path = tmp_path / "danmaku_hotspots.json"
    evidence_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "source": "danmaku_aggregate_review",
                "privacy": {
                    "rawContentExported": False,
                    "rawRowsExported": False,
                    "wordAggregationOnly": True,
                },
                "episodes": {
                    "tainai3_ep01": {
                        "candidates": [
                            {
                                "candidateId": "danmaku_ep01_090",
                                "timeMs": 90000,
                                "type": "REACTION_PULSE",
                                "question": "当家人排面登场，你想给什么反应？",
                                "reason": "01:30-01:40 聚合弹幕 120 条、点赞 350；画面复核为豪车与当家人登场。",
                                "options": ["排面拉满", "终于来了"],
                                "evidenceRefs": ["danmaku_bucket:tainai3_ep01:090"],
                                "confidence": 0.91,
                                "reviewStatus": "accepted",
                            }
                        ],
                        "publishedNodes": [],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", evidence_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/episodes/tainai3_ep01/danmaku-emotion-report")

    data = response.json()["data"]
    dumped = json.dumps(data, ensure_ascii=False)
    assert response.status_code == 200
    assert data["privacy"]["rawContentExported"] is False
    assert data["privacy"]["rawRowsExported"] is False
    assert data["items"][0]["keywords"]
    assert data["items"][0]["emotion"] == "燃爽期待"
    assert data["items"][0]["likeIntensity"] == 350
    assert data["items"][0]["suggestedComponentType"] == "DANMAKU_STICKER"
    forbidden_columns = [
        "弹幕" + "内容",
        "发弹幕时刻" + "相对于视频起始时间偏移量",
        "累计" + "点赞数",
        "剧" + "名称",
        "group" + "_title",
    ]
    for forbidden in forbidden_columns:
        assert forbidden not in dumped


def test_interaction_generation_pipeline_reads_video_evidence(monkeypatch, tmp_path):
    import json
    import backend.app.content_catalog as content_catalog

    evidence_dir = tmp_path / "tainai3_ep01"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "understanding.json").write_text(
        json.dumps(
            {
                "assets": {"frames": [{"timeMs": 44_000, "path": "frame.jpg"}]},
                "envelope": {
                    "result": {
                        "audio_text": {"transcript": "证据出现了"},
                        "screen_text_cues": [{"time_ms": 44_000, "text": "身份揭晓"}],
                        "interaction_candidates": [
                            {
                                "time_ms": 44_000,
                                "type": "REACTION_PULSE",
                                "question": "证据出现时你会怎么选？",
                                "reason": "ASR 与 OCR 同时命中",
                                "options": ["追问", "沉默"],
                            }
                        ],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", tmp_path / "missing.json")

    payload = content_catalog.build_interaction_nodes("http://test/", "tainai3_ep01")

    assert payload is not None
    pipeline = payload["generationPipeline"]
    assert pipeline["sourceStatus"] == "evidence_ready"
    assert pipeline["evidenceSources"] == ["ASR", "OCR", "KEYFRAME"]
    assert pipeline["candidateNodeCount"] == 1
    assert payload["candidateNodes"][0]["question"] == "证据出现时你会怎么选？"
    assert payload["nodes"][0]["generation"]["reviewStatus"] == "edited"
    assert payload["nodes"][0]["generation"]["generationSource"] == "reviewed_model"
    assert payload["nodes"][0]["generation"]["confidence"] > 0
    assert payload["nodes"][0]["generation"]["evidenceRefs"] == [
        "frame:tainai3_ep01:01",
        "ocr_cue:tainai3_ep01:01",
    ]


def test_danmaku_reviewed_hotspot_publishes_traceable_node(monkeypatch, tmp_path):
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path / "missing")

    payload = content_catalog.build_interaction_nodes("http://test/", "tainai3_ep01")

    assert payload is not None
    pipeline = payload["generationPipeline"]
    assert "DANMAKU_AGGREGATE" in pipeline["evidenceSources"]
    node = next(item for item in payload["nodes"] if "danmaku" in item["id"])
    assert node["trigger"]["timeMs"] >= 0
    assert node["generation"]["generationSource"] == "reviewed_model"
    assert node["generation"]["reviewStatus"] == "accepted"
    assert node["generation"]["confidence"] > 0.6
    assert node["generation"]["evidenceRefs"]
    assert node["generation"]["evidenceRefs"][0].startswith("danmaku_bucket:tainai3_ep01:")


@pytest.mark.asyncio
async def test_aigc_insert_submit_returns_branch_segment():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/interaction/submit",
            json={
                "submitId": "submit_test_branch",
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep02",
                "nodeId": "n_118_ep02_counter_attack",
                "triggerMs": 118_000,
                "answer": {"optionId": "boost"},
                "clientTsMs": 1_900_000_000_000,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["nextAction"]["type"] == "BRANCH_SEGMENT"
    segment = body["data"]["nextAction"]["segment"]
    assert segment["playbackMode"] == "REPLACE_MAIN"
    assert segment["mediaUrl"].endswith("/media/aigc-inserts/tainai3_ep02/n_118_ep02_counter_attack.mp4")
    assert segment["returnSeekMs"] == 118_000


@pytest.mark.asyncio
async def test_interaction_records_endpoint_returns_recent_items():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/interaction/records", params={"episode_id": "tainai3_ep01"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    items = body["data"]["items"]
    assert any(item["episode_id"] == "tainai3_ep01" for item in items)


@pytest.mark.asyncio
async def test_interaction_insights_returns_heatmap_and_crowd_feedback():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/interaction/submit",
            json={
                "submitId": "submit_test_heatmap",
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep02",
                "nodeId": "n_038_ep02_crowd_mock",
                "triggerMs": 38_000,
                "answer": {"optionId": "barrage_go"},
                "clientTsMs": 1_900_000_000_000,
            },
        )
        resp = await ac.get("/episodes/tainai3_ep02/interaction-insights")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["episodeId"] == "tainai3_ep02"
    assert data["nodeCount"] >= 4
    assert data["peakNodeId"]
    assert "群体反馈" in data["crowdSummary"] or "互动反馈" in data["crowdSummary"]
    target_node = next(item for item in data["nodes"] if item["nodeId"] == "n_038_ep02_crowd_mock")
    assert target_node["triggerMs"] == 38_000
    assert target_node["heatScore"] > 0
    assert target_node["options"][0]["percent"] > 0
