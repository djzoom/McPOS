#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import mcpos.config as config_module
import mcpos.pipelines.sg_vo_pipeline as sg_pipeline_module
from mcpos.core.pipeline import run_episode
from mcpos.core.channel import ChannelConfig
from mcpos.models import EpisodeSpec


def _derive_date(episode_id: str) -> str:
    if "_" in episode_id:
        return episode_id.rsplit("_", 1)[-1]
    return episode_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug-run the SG VO pipeline with temporary VO overrides.")
    parser.add_argument("--episode-id", required=True, help="Episode id, e.g. sg_20260307")
    parser.add_argument("--date", help="Schedule date override, YYYYMMDD")
    parser.add_argument("--mode", choices=["existing_asset", "qwen3", "elevenlabs", "hybrid"], default="hybrid")
    parser.add_argument("--enable-vo", dest="enable_vo", action="store_true", help="Enable the VO pipeline")
    parser.add_argument("--disable-vo", dest="enable_vo", action="store_false", help="Disable the VO pipeline")
    parser.set_defaults(enable_vo=True)
    parser.add_argument("--existing-asset-dir", type=Path, help="Override SG vo_existing_asset_dir")
    parser.add_argument("--existing-asset-prefer", action="store_true", default=None, help="Prefer existing VO assets first")
    parser.add_argument("--no-existing-asset-prefer", dest="existing_asset_prefer", action="store_false", help="Do not prefer existing VO assets")
    parser.add_argument("--ref-audio", type=Path, help="Override Qwen3 reference audio")
    parser.add_argument("--ref-text", type=Path, help="Override Qwen3 reference text")
    parser.add_argument("--target-duration-min", type=int, help="Override target duration minutes for this run")
    args = parser.parse_args()

    real_load_channel_config = config_module.load_channel_config

    def patched_load_channel_config(channel_id: str, config=None) -> ChannelConfig:
        cfg = real_load_channel_config(channel_id, config)
        if channel_id != "sg":
            return cfg
        extra = dict(cfg.extra)
        extra["enable_vo"] = bool(args.enable_vo)
        extra["vo_mode"] = args.mode
        if args.existing_asset_dir:
            extra["vo_existing_asset_dir"] = str(args.existing_asset_dir.expanduser())
        if args.existing_asset_prefer is not None:
            extra["vo_existing_asset_prefer"] = bool(args.existing_asset_prefer)
        if args.ref_audio:
            extra["vo_voice_ref_audio_path"] = str(args.ref_audio.expanduser())
        if args.ref_text:
            extra["vo_voice_ref_text_path"] = str(args.ref_text.expanduser())
        return ChannelConfig(
            channel_id=cfg.channel_id,
            channel_name=cfg.channel_name,
            library_root=cfg.library_root,
            assets_root=cfg.assets_root,
            youtube_channel_id=cfg.youtube_channel_id,
            youtube_playlist_id=cfg.youtube_playlist_id,
            credentials_dir=cfg.credentials_dir,
            target_bpm=cfg.target_bpm,
            target_duration_min=args.target_duration_min or cfg.target_duration_min,
            crossfade_sec=cfg.crossfade_sec,
            timezone=cfg.timezone,
            publish_time_local=cfg.publish_time_local,
            daily_quota_budget=cfg.daily_quota_budget,
            extra=extra,
        )

    config_module.load_channel_config = patched_load_channel_config
    sg_pipeline_module.load_channel_config = patched_load_channel_config

    spec = EpisodeSpec(
        channel_id="sg",
        episode_id=args.episode_id,
        date=args.date or _derive_date(args.episode_id),
        target_duration_min=args.target_duration_min,
    )

    try:
        state = asyncio.run(run_episode(spec))
    finally:
        config_module.load_channel_config = real_load_channel_config
        sg_pipeline_module.load_channel_config = real_load_channel_config

    print(f"episode_id: {spec.episode_id}")
    print(f"channel_id: {spec.channel_id}")
    print(f"required_stages: {[stage.value for stage in (state.required_stages or [])]}")
    print(f"current_stage: {state.current_stage.value if state.current_stage else 'none'}")
    print(f"core_complete: {state.is_core_complete()}")
    print(f"upload_status: {state.upload_status}")
    print(f"error_message: {state.error_message or ''}")
    return 0 if state.is_core_complete() else 1


if __name__ == "__main__":
    raise SystemExit(main())
