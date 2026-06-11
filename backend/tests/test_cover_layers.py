from backend.app.cover_layers import build_cover_layers


def test_build_cover_layers_adds_default_portrait_for_primary_drama():
    layers = build_cover_layers(
        {
            "drama_id": "tainai3",
            "latest_episode_no": 5,
            "cover_layers": {
                "identity_label": "身份反转",
                "heat_label": "178.8万人观看",
                "share_hint": "生成同款打卡图",
            },
        },
        "http://test",
        primary_drama_id="tainai3",
    )

    assert layers == {
        "portrait_url": "http://test/media/video-understanding-frames/tainai3_ep01/poster_portrait.jpg",
        "identity_label": "身份反转",
        "heat_label": "178.8万人观看",
        "latest_label": "更新至第5集",
        "share_hint": "生成同款打卡图",
    }


def test_build_cover_layers_keeps_registry_portrait_and_fallback_copy():
    layers = build_cover_layers(
        {
            "drama_id": "new_drama",
            "latest_episode_no": 67,
            "cover_layers": {"portrait_url": "https://cdn.example.test/cover.jpg"},
        },
        "http://test/",
        primary_drama_id="tainai3",
    )

    assert layers["portrait_url"] == "https://cdn.example.test/cover.jpg"
    assert layers["identity_label"]
    assert layers["heat_label"]
    assert layers["latest_label"] == "更新至第67集"
    assert layers["share_hint"]


def test_build_cover_layers_keeps_explicit_latest_label():
    layers = build_cover_layers(
        {
            "drama_id": "new_drama",
            "latest_episode_no": 12,
            "cover_layers": {
                "portrait_url": "https://cdn.example.test/cover.jpg",
                "latest_label": "更新至第12集 · 前5集可看",
            },
        },
        "http://test/",
        primary_drama_id="tainai3",
    )

    assert layers["latest_label"] == "更新至第12集 · 前5集可看"
