from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest

from mcpos.adapters.filesystem import build_asset_paths
from mcpos.audio.probe import probe_audio_duration
from mcpos.models import EpisodeSpec, StageName, StageResult, Track
from mcpos.pipelines.sg_vo_pipeline import run_sg_pipeline_with_vo
from mcpos.vo.models import VOAsset, VOSegmentKind
import mcpos.pipelines.sg_vo_pipeline as sg_pipeline_module
import mcpos.vo.resolver as resolver_module
from tests.helpers import make_tone_mp3, write_sg_config


class FakeSGPlugin:
    def __init__(self, library_tracks, crossfade_sec: float) -> None:
        self._library_tracks = library_tracks
        self.config = type("Cfg", (), {"crossfade_sec": crossfade_sec, "target_duration_min": 6})()

    def scan_library(self):
        return list(self._library_tracks)

    def select_tracks(self, spec, catalog):
        return list(catalog)

    def build_mix(self, tracks, spec, paths):
        started_at = datetime.now()
        make_tone_mp3(paths.music_mix_mp3, duration=5.0, frequency=180.0)
        return StageResult(
            stage=StageName.MIX,
            success=True,
            duration_seconds=0.0,
            key_asset_paths=[paths.music_mix_mp3],
            started_at=started_at,
            finished_at=datetime.now(),
        )

    async def generate_text_async(self, spec, paths, tracks):
        started_at = datetime.now()
        paths.youtube_title_txt.write_text("Sleep in Grace | Test Episode", encoding="utf-8")
        paths.youtube_description_txt.write_text("Gentle ambient rest for the night.", encoding="utf-8")
        paths.youtube_tags_txt.write_text("sleep\nambient\nprayer", encoding="utf-8")
        return StageResult(
            stage=StageName.TEXT_BASE,
            success=True,
            duration_seconds=0.0,
            key_asset_paths=[paths.youtube_title_txt, paths.youtube_description_txt, paths.youtube_tags_txt],
            started_at=started_at,
            finished_at=datetime.now(),
        )

    def render_video(self, spec, paths):
        started_at = datetime.now()
        paths.youtube_mp4.write_bytes(b"mp4")
        paths.render_complete_flag.touch()
        return StageResult(
            stage=StageName.RENDER,
            success=True,
            duration_seconds=0.0,
            key_asset_paths=[paths.youtube_mp4, paths.render_complete_flag],
            started_at=started_at,
            finished_at=datetime.now(),
        )


async def _fake_cover(spec, paths):
    started_at = datetime.now()
    paths.cover_png.write_bytes(b"png")
    return StageResult(
        stage=StageName.COVER,
        success=True,
        duration_seconds=0.0,
        key_asset_paths=[paths.cover_png],
        started_at=started_at,
        finished_at=datetime.now(),
    )


async def _fake_text_srt(spec, paths):
    started_at = datetime.now()
    paths.youtube_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nTrack", encoding="utf-8")
    return StageResult(
        stage=StageName.TEXT_SRT,
        success=True,
        duration_seconds=0.0,
        key_asset_paths=[paths.youtube_srt],
        started_at=started_at,
        finished_at=datetime.now(),
    )


@pytest.fixture
def sg_plugin_fixture(isolated_mcpos, sg_workspace, monkeypatch):
    library_root = sg_workspace["library_root"]
    tracks = [
        Track(path=make_tone_mp3(library_root / "track_1.mp3", duration=2.2, frequency=210.0), title="Quiet River", duration_sec=2.2, vocal_class="instrumental"),
        Track(path=make_tone_mp3(library_root / "track_2.mp3", duration=2.4, frequency=230.0), title="Night Shelter", duration_sec=2.4, vocal_class="instrumental"),
    ]
    fake_plugin = FakeSGPlugin(tracks, crossfade_sec=0.5)
    monkeypatch.setattr(sg_pipeline_module, "get_channel_plugin", lambda channel_id, config: fake_plugin)
    monkeypatch.setattr(sg_pipeline_module, "generate_cover_for_episode", _fake_cover)
    monkeypatch.setattr(sg_pipeline_module, "generate_text_srt", _fake_text_srt)
    return fake_plugin


def test_sg_pipeline_music_only_compat(monkeypatch, isolated_mcpos, sg_workspace, sg_plugin_fixture):
    write_sg_config(isolated_mcpos, sg_workspace, enable_vo=False, vo_mode="hybrid")

    spec = EpisodeSpec(channel_id="sg", episode_id="sg_20260312", date="20260312")
    state = asyncio.run(run_sg_pipeline_with_vo(spec, force=True))
    paths = build_asset_paths(spec, isolated_mcpos)

    assert state.is_core_complete()
    assert paths.music_mix_mp3.exists()
    assert paths.final_mix_mp3.exists()
    assert not paths.vo_timeline_csv.exists()


@pytest.mark.parametrize(
    ("mode", "existing_asset_prefer"),
    [
        ("existing_asset", True),
        ("qwen3", False),
        ("hybrid", False),
    ],
)
def test_sg_pipeline_vo_modes(monkeypatch, isolated_mcpos, sg_workspace, sg_plugin_fixture, mode, existing_asset_prefer):
    vo_dir = sg_workspace["vo_dir"]
    write_sg_config(
        isolated_mcpos,
        sg_workspace,
        enable_vo=True,
        vo_mode=mode,
        existing_asset_prefer=existing_asset_prefer,
        vo_existing_asset_dir=vo_dir,
    )

    if mode == "existing_asset":
        make_tone_mp3(vo_dir / "sg_intro_seed.mp3", duration=0.8, frequency=520.0)
        make_tone_mp3(vo_dir / "sg_outro_seed.mp3", duration=0.9, frequency=620.0)
        (vo_dir / "sg_seed.txt").write_text("Welcome and rest in peace through the night.", encoding="utf-8")
    else:
        for item in vo_dir.glob("*"):
            if item.is_file():
                item.unlink()

    synth_calls: list[str] = []

    def fake_synthesize(source, kind, bundle, output_path, vo_config):
        synth_calls.append(source)
        freq = 700.0 if kind == VOSegmentKind.INTRO else 760.0
        make_tone_mp3(output_path, duration=0.7 if kind == VOSegmentKind.INTRO else 0.8, frequency=freq)
        return VOAsset(
            kind=kind,
            path=output_path,
            duration_sec=probe_audio_duration(output_path),
            text=bundle.text_for(kind),
            ssml_text=bundle.ssml_for(kind),
            source_type=source,
            status="generated",
            metadata={"engine": source},
        )

    monkeypatch.setattr(resolver_module, "_synthesize_with_engine", fake_synthesize)

    spec = EpisodeSpec(channel_id="sg", episode_id=f"sg_{mode}_20260313", date="20260313")
    state = asyncio.run(run_sg_pipeline_with_vo(spec, force=True))
    paths = build_asset_paths(spec, isolated_mcpos)
    vo_meta = json.loads(paths.vo_gen_meta_json.read_text(encoding="utf-8"))

    assert state.is_core_complete()
    assert paths.music_mix_mp3.exists()
    assert paths.final_mix_mp3.exists()
    assert paths.vo_timeline_csv.exists()
    assert paths.vo_srt.exists()
    assert paths.audio_ducking_map.exists()
    assert vo_meta["mode"] == mode
    if mode == "existing_asset":
        assert synth_calls == []
        assert vo_meta["segments"]["intro"]["source_type"] == "existing_asset_direct"
    elif mode == "qwen3":
        assert synth_calls[0] == "qwen3"
        assert vo_meta["segments"]["intro"]["source_type"] == "qwen3"
    else:
        assert synth_calls[0] == "elevenlabs_api"
