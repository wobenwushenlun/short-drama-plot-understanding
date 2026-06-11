import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_drama_registry_loads_builtin_and_extra_configs(tmp_path, monkeypatch):
    from backend.app.drama_registry import load_drama_registry

    extra_dir = tmp_path / "dramas"
    extra_dir.mkdir()
    content_root = tmp_path / "new_drama_assets"
    content_root.mkdir()
    (extra_dir / "new_drama_001.json").write_text(
        json.dumps(
            {
                "dramaId": "new_drama_001",
                "title": "新短剧标题",
                "contentRoot": str(content_root),
                "episodeCount": 2,
                "episodeIdPrefix": "new_drama_001_ep",
                "cover": "https://cdn.example.test/new.jpg",
                "tags": ["逆袭", "反转"],
                "danmakuEvidencePath": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(extra_dir))

    registry = load_drama_registry()

    assert registry.get("tainai3").title.startswith("十八岁太奶奶")
    assert registry.get("new_drama_001").episode_count == 2
    assert registry.get("new_drama_001").episode_ids == [
        "new_drama_001_ep01",
        "new_drama_001_ep02",
    ]
    assert registry.find_by_episode_id("new_drama_001_ep02").drama_id == "new_drama_001"
    drama_ids = {item.drama_id for item in registry.list_all()}
    assert {"new_drama_001", "tainai3"}.issubset(drama_ids)


def test_drama_registry_rejects_invalid_config(tmp_path, monkeypatch):
    from backend.app.drama_registry import load_drama_registry

    extra_dir = tmp_path / "dramas"
    extra_dir.mkdir()
    (extra_dir / "bad.json").write_text(
        json.dumps(
            {
                "dramaId": "bad drama id",
                "title": "",
                "contentRoot": "",
                "episodeCount": 0,
                "episodeIdPrefix": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(extra_dir))

    registry = load_drama_registry()

    assert "bad drama id" not in {item.drama_id for item in registry.list_all()}
    assert registry.load_errors
    assert "bad.json" in registry.load_errors[0]["path"]


def test_register_drama_cli_writes_loadable_config(tmp_path, monkeypatch):
    from backend.app.drama_registry import load_drama_registry

    registry_dir = tmp_path / "registry"
    content_root = tmp_path / "new_assets"
    content_root.mkdir()

    completed = subprocess.run(
        [
            sys.executable,
            "backend/scripts/register_drama.py",
            "--registry-dir",
            str(registry_dir),
            "--drama-id",
            "new_drama_2026",
            "--title",
            "新短剧标题",
            "--content-root",
            str(content_root),
            "--episode-count",
            "3",
            "--episode-id-prefix",
            "new_drama_2026_ep",
            "--episode-file-pattern",
            "第{episode_no}集.mp4",
            "--cover",
            "https://cdn.example.test/cover.jpg",
            "--tags",
            "逆袭,反转",
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 0, completed.stderr
    config_path = registry_dir / "new_drama_2026.json"
    assert config_path.exists()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["dramaId"] == "new_drama_2026"
    assert saved["episodeFilePattern"] == "第{episode_no}集.mp4"
    assert saved["tags"] == ["逆袭", "反转"]

    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(registry_dir))
    registry = load_drama_registry()

    config = registry.get("new_drama_2026")
    assert config.title == "新短剧标题"
    assert config.episode_ids == [
        "new_drama_2026_ep01",
        "new_drama_2026_ep02",
        "new_drama_2026_ep03",
    ]
    assert registry.find_by_episode_id("new_drama_2026_ep03").drama_id == "new_drama_2026"


def test_drama_registry_loads_display_start_and_user_copy(tmp_path, monkeypatch):
    from backend.app.drama_registry import load_drama_registry

    extra_dir = tmp_path / "dramas"
    extra_dir.mkdir()
    content_root = tmp_path / "beipai_assets"
    content_root.mkdir()
    (extra_dir / "beipai_xunbao.json").write_text(
        json.dumps(
            {
                "dramaId": "beipai_xunbao",
                "title": "北派寻宝笔记",
                "contentRoot": str(content_root),
                "episodeCount": 5,
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
    monkeypatch.setenv("AIGC_DRAMA_CONFIG_DIR", str(extra_dir))

    config = load_drama_registry().get("beipai_xunbao")

    assert config.episode_number_start == 63
    assert config.latest_episode_no == 67
    assert config.source_episode_no(1) == 63
    assert config.episode_file_pattern == "第{source_episode_no}集.mp4"
    assert config.description.startswith("寻宝小队")
    assert config.interaction_hint.startswith("适合围绕线索")
    assert config.cover_layers["identity_label"] == "寻宝悬疑"
    assert config.episode_summary_for(1).startswith("第63集")
    assert config.episode_summary_for(2).startswith("第64集")


def test_register_drama_cli_requires_force_to_overwrite(tmp_path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    config_path = registry_dir / "repeat_drama.json"
    config_path.write_text('{"dramaId": "repeat_drama", "title": "旧标题"}', encoding="utf-8")

    base_command = [
        sys.executable,
        "backend/scripts/register_drama.py",
        "--registry-dir",
        str(registry_dir),
        "--drama-id",
        "repeat_drama",
        "--title",
        "新标题",
        "--content-root",
        str(tmp_path / "assets"),
        "--episode-count",
        "1",
        "--episode-id-prefix",
        "repeat_ep",
    ]
    failed = subprocess.run(
        base_command,
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert failed.returncode != 0
    assert "already exists" in failed.stderr
    assert json.loads(config_path.read_text(encoding="utf-8"))["title"] == "旧标题"

    overwritten = subprocess.run(
        [*base_command, "--force"],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert overwritten.returncode == 0, overwritten.stderr
    assert json.loads(config_path.read_text(encoding="utf-8"))["title"] == "新标题"
