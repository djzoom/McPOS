from __future__ import annotations

from pathlib import Path

from mcpos.audio.ducking import apply_ducking_and_mix
from mcpos.audio.probe import probe_audio_duration
from mcpos.vo.models import VOAsset, VOConfig, VOSegmentKind, VOTimelineEntry
import mcpos.audio.ducking as ducking_module
from tests.helpers import make_tone_mp3


def test_apply_ducking_and_mix_writes_outputs(isolated_mcpos):
    music_path = make_tone_mp3(isolated_mcpos.repo_root / "music.mp3", duration=4.0, frequency=220.0)
    vo_path = make_tone_mp3(isolated_mcpos.repo_root / "vo_intro.mp3", duration=1.0, frequency=480.0)
    output_path = isolated_mcpos.repo_root / "final_mix.mp3"
    map_path = isolated_mcpos.repo_root / "ducking_map.csv"
    meta_path = isolated_mcpos.repo_root / "ducking_meta.json"

    asset = VOAsset(kind=VOSegmentKind.INTRO, path=vo_path, duration_sec=probe_audio_duration(vo_path), source_type="test", status="generated")
    entry = VOTimelineEntry(
        segment_id="intro",
        kind=VOSegmentKind.INTRO,
        audio_path=vo_path,
        start_sec=0.0,
        end_sec=1.0,
        duck_start_sec=0.0,
        duck_end_sec=1.5,
        text="Welcome",
        ssml_text="Welcome",
    )

    final_mix, ducking_map, meta = apply_ducking_and_mix(
        music_path,
        [asset],
        [entry],
        VOConfig(enable_vo=True, fade_sec=0.5),
        output_path=output_path,
        ducking_map_path=map_path,
        meta_json_path=meta_path,
    )

    assert final_mix.exists()
    assert ducking_map.exists()
    assert "intro" in ducking_map.read_text(encoding="utf-8")
    assert meta["degraded_to_music_only"] is False


def test_apply_ducking_and_mix_falls_back_to_music_only(monkeypatch, isolated_mcpos):
    music_path = make_tone_mp3(isolated_mcpos.repo_root / "music_fallback.mp3", duration=2.0, frequency=200.0)
    vo_path = make_tone_mp3(isolated_mcpos.repo_root / "vo_fallback.mp3", duration=0.8, frequency=500.0)
    output_path = isolated_mcpos.repo_root / "final_mix_fallback.mp3"
    map_path = isolated_mcpos.repo_root / "ducking_map_fallback.csv"
    meta_path = isolated_mcpos.repo_root / "ducking_meta_fallback.json"

    class FailedRun:
        returncode = 1
        stderr = "ffmpeg failed"
        stdout = ""

    monkeypatch.setattr(ducking_module.subprocess, "run", lambda *args, **kwargs: FailedRun())

    asset = VOAsset(kind=VOSegmentKind.INTRO, path=vo_path, duration_sec=0.8, source_type="test", status="generated")
    entry = VOTimelineEntry(
        segment_id="intro",
        kind=VOSegmentKind.INTRO,
        audio_path=vo_path,
        start_sec=0.0,
        end_sec=0.8,
        duck_start_sec=0.0,
        duck_end_sec=1.0,
        text="Welcome",
        ssml_text="Welcome",
    )

    final_mix, _ducking_map, meta = apply_ducking_and_mix(
        music_path,
        [asset],
        [entry],
        VOConfig(enable_vo=True, fade_sec=0.5),
        output_path=output_path,
        ducking_map_path=map_path,
        meta_json_path=meta_path,
    )

    assert final_mix.exists()
    assert final_mix.read_bytes() == music_path.read_bytes()
    assert meta["degraded_to_music_only"] is True
    assert meta["reason"] == "ducking_failed"
