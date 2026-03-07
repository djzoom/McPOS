from __future__ import annotations

from mcpos.models import AssetPaths
from mcpos.vo.models import VOConfig, VOScriptBundle
from mcpos.vo.timeline import build_vo_timeline
from tests.helpers import make_tone_mp3


def test_build_vo_timeline_writes_csv_and_srt(isolated_mcpos):
    paths = AssetPaths.from_output_dir(isolated_mcpos.repo_root / "episode" / "sg_20260309")
    intro = make_tone_mp3(paths.vo_intro_mp3, duration=1.1, frequency=300.0)
    outro = make_tone_mp3(paths.vo_outro_mp3, duration=1.3, frequency=420.0)
    bundle = VOScriptBundle(
        txt_path=paths.vo_script_txt,
        ssml_path=paths.vo_script_ssml,
        meta_path=paths.vo_script_meta_json,
        intro_text="Welcome to rest.",
        outro_text="Carry the stillness with you.",
        intro_ssml="Welcome <break time=\"0.5s\" /> to rest.",
        outro_ssml="Carry the stillness with you.",
    )
    vo_config = VOConfig(enable_vo=True, fade_sec=0.5)

    entries, csv_path, srt_path, meta = build_vo_timeline(
        intro,
        outro,
        10.0,
        vo_config,
        paths=paths,
        script_bundle=bundle,
    )

    assert len(entries) == 2
    assert entries[0].segment_id == "intro"
    assert entries[0].start_sec == 0.0
    assert entries[1].segment_id == "outro"
    assert 8.5 <= entries[1].start_sec <= 9.0
    assert csv_path.exists()
    assert srt_path.exists()
    assert "Welcome" in srt_path.read_text(encoding="utf-8")
    assert meta["entry_count"] == 2


def test_build_vo_timeline_drops_outro_when_program_too_short(isolated_mcpos):
    paths = AssetPaths.from_output_dir(isolated_mcpos.repo_root / "episode" / "sg_20260310")
    intro = make_tone_mp3(paths.vo_intro_mp3, duration=1.0, frequency=260.0)
    outro = make_tone_mp3(paths.vo_outro_mp3, duration=1.0, frequency=460.0)
    bundle = VOScriptBundle(
        txt_path=paths.vo_script_txt,
        ssml_path=paths.vo_script_ssml,
        meta_path=paths.vo_script_meta_json,
        intro_text="Settle your breathing.",
        outro_text="Stay in peace.",
        intro_ssml="Settle your breathing.",
        outro_ssml="Stay in peace.",
    )

    entries, _csv_path, _srt_path, meta = build_vo_timeline(
        intro,
        outro,
        1.5,
        VOConfig(enable_vo=True, fade_sec=0.5),
        paths=paths,
        script_bundle=bundle,
    )

    assert len(entries) == 1
    assert entries[0].segment_id == "intro"
    assert any("Dropped outro" in note for note in meta["notes"])
