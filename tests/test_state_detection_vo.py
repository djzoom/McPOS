from __future__ import annotations

from mcpos.adapters.filesystem import build_asset_paths, detect_episode_state_from_filesystem
from mcpos.models import EpisodeSpec, StageName
from tests.helpers import write_sg_config


def test_detect_episode_state_for_sg_vo_flow(isolated_mcpos, sg_workspace):
    write_sg_config(isolated_mcpos, sg_workspace, enable_vo=True, vo_mode="hybrid")

    spec = EpisodeSpec(channel_id="sg", episode_id="sg_20260311", date="20260311")
    paths = build_asset_paths(spec, isolated_mcpos)
    paths.episode_output_dir.mkdir(parents=True, exist_ok=True)

    paths.playlist_csv.write_text("playlist", encoding="utf-8")
    paths.recipe_json.write_text("{}", encoding="utf-8")
    paths.youtube_title_txt.write_text("Title", encoding="utf-8")
    paths.youtube_description_txt.write_text("Description", encoding="utf-8")
    paths.youtube_tags_txt.write_text("tag", encoding="utf-8")
    paths.cover_png.write_bytes(b"png")
    paths.music_mix_mp3.write_bytes(b"mix")
    paths.timeline_csv.write_text("timeline", encoding="utf-8")

    state = detect_episode_state_from_filesystem(spec, paths)
    assert StageName.VO_SCRIPT in state.required_stages
    assert state.current_stage == StageName.VO_SCRIPT

    paths.vo_script_txt.write_text("[intro]\nHello", encoding="utf-8")
    paths.vo_script_ssml.write_text("[intro]\nHello", encoding="utf-8")
    paths.vo_script_meta_json.write_text("{}", encoding="utf-8")
    paths.vo_gen_meta_json.write_text('{"segments": {"intro": {"status": "generated"}}}', encoding="utf-8")
    paths.final_mix_mp3.write_bytes(b"final")
    paths.vo_timeline_csv.write_text("timeline", encoding="utf-8")
    paths.audio_ducking_map.write_text("ducking", encoding="utf-8")
    paths.youtube_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello", encoding="utf-8")
    paths.youtube_mp4.write_bytes(b"mp4")
    paths.render_complete_flag.touch()

    state = detect_episode_state_from_filesystem(spec, paths)
    assert state.stage_completed[StageName.READY] is True
    assert state.current_stage == StageName.READY


def test_detect_episode_state_for_kat_remains_legacy(isolated_mcpos):
    spec = EpisodeSpec(channel_id="kat", episode_id="kat_20260311", date="20260311")
    paths = build_asset_paths(spec, isolated_mcpos)
    paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
    paths.playlist_csv.write_text("playlist", encoding="utf-8")
    paths.recipe_json.write_text("{}", encoding="utf-8")
    paths.youtube_title_txt.write_text("Title", encoding="utf-8")
    paths.youtube_description_txt.write_text("Description", encoding="utf-8")
    paths.youtube_tags_txt.write_text("tag", encoding="utf-8")
    paths.cover_png.write_bytes(b"png")
    paths.final_mix_mp3.write_bytes(b"mix")
    paths.timeline_csv.write_text("timeline", encoding="utf-8")

    state = detect_episode_state_from_filesystem(spec, paths)
    assert StageName.VO_SCRIPT not in state.required_stages
    assert state.current_stage == StageName.TEXT_SRT
