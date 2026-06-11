from pathlib import Path

from backend.app.asr_service import ASRService, load_asr_credentials


def test_load_asr_credentials_from_placeholder_file(tmp_path: Path):
    config_path = tmp_path / "asr_config.txt"
    config_path.write_text(
        "APIKEY：test-key\nRESOURCE_ID：volc.bigasr.auc_turbo\nLOCAL_ENGINE：whisper_cpp\n",
        encoding="utf-8",
    )

    credentials = load_asr_credentials(config_path)

    assert credentials.api_key == "test-key"
    assert credentials.resource_id == "volc.bigasr.auc_turbo"
    assert credentials.local_engine == "whisper_cpp"


def test_asr_service_stays_disabled_without_runtime_flag(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AIGC_ASR_ENABLED", raising=False)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"placeholder")

    result = ASRService().recognize_file(audio_path)

    assert result["status"] == "asr_disabled"
    assert result["transcript"] == ""


def test_asr_service_reads_sidecar_transcript_without_cloud_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AIGC_ASR_ENABLED", raising=False)
    audio_dir = tmp_path / "tainai3_ep01"
    audio_dir.mkdir()
    audio_path = audio_dir / "audio_16k_mono.wav"
    audio_path.write_bytes(b"placeholder")
    (audio_dir / "transcript.srt").write_text(
        "1\n00:00:01,000 --> 00:00:03,000\n你们倒反天罡是吧\n",
        encoding="utf-8",
    )

    result = ASRService().recognize_file(audio_path)

    assert result["status"] == "ok"
    assert result["source"] == "sidecar:transcript.srt"
    assert result["transcript"] == "你们倒反天罡是吧"
