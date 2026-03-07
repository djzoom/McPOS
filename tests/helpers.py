from __future__ import annotations

import subprocess
from pathlib import Path

from mcpos.config import McPOSConfig

_PNG_1X1 = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C489"
    "0000000D49444154789C6360000000020001E221BC330000000049454E44AE426082"
)


def make_test_config(tmp_path: Path) -> McPOSConfig:
    repo_root = tmp_path
    images_pool_root = repo_root / "images_pool"
    assets_root = repo_root / "assets"
    return McPOSConfig(
        repo_root=repo_root,
        channels_root=repo_root / "channels",
        images_pool_root=images_pool_root,
        images_pool_available=images_pool_root / "available",
        images_pool_used=images_pool_root / "used",
        assets_root=assets_root,
        fonts_dir=assets_root / "fonts",
        design_dir=assets_root / "design",
        logs_dir=repo_root / "mcpos" / "logs",
        youtube_client_secrets_file=repo_root / "config" / "google" / "client_secrets.json",
        youtube_token_file=repo_root / "config" / "google" / "youtube_token.json",
    )


def write_sg_config(
    config: McPOSConfig,
    sg_paths: dict[str, Path],
    *,
    enable_vo: bool = False,
    vo_mode: str = "hybrid",
    existing_asset_prefer: bool = True,
    vo_existing_asset_dir: Path | None = None,
) -> Path:
    cfg_path = sg_paths["sg_root"] / "config" / "config.yaml"
    existing_dir = vo_existing_asset_dir or sg_paths["vo_dir"]
    content = f"""
channel_id: sg
name: \"Sleep in Grace\"
library_root: \"{sg_paths['library_root']}\"
assets_root: \"{sg_paths['assets_root']}\"
catalog_csv: \"{sg_paths['catalog_root'] / 'classification_results.csv'}\"
target_bpm: null
target_duration_min: 6
crossfade_sec: 0.5
vocal_mix_ratio: 0.05
instrumental_preferred: true
timezone: \"UTC\"
publish_time_local: \"06:00\"
daily_quota_budget: 3000
enable_vo: {str(enable_vo).lower()}
vo_mode: {vo_mode}
vo_intro_enabled: true
vo_outro_enabled: true
vo_ducking_db: -8.0
vo_fade_sec: 0.5
vo_lufs_target: -14.0
vo_true_peak_dbtp: -1.0
vo_channel_profile: sg_prayer
vo_language: en
vo_existing_asset_dir: \"{existing_dir}\"
vo_existing_asset_prefer: {str(existing_asset_prefer).lower()}
vo_voice_ref_audio_path: \"{config.repo_root / 'ref_voice.mp3'}\"
vo_voice_ref_text_path: \"{config.repo_root / 'ref_voice.txt'}\"
vo_outro_margin_sec: 0.0
vo_existing_legacy_intro_max_sec: 2
vo_existing_legacy_outro_max_sec: 2
vo_elevenlabs_voice_id: null
vo_elevenlabs_model_id: \"eleven_multilingual_v2\"
""".strip()
    cfg_path.write_text(content + "\n", encoding="utf-8")
    (config.repo_root / "ref_voice.txt").write_text("This is a reference voice.", encoding="utf-8")
    return cfg_path


def make_tone_mp3(path: Path, *, duration: float = 1.0, frequency: float = 220.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={frequency}:sample_rate=44100:duration={duration}",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "192k",
        str(path),
    ]
    subprocess.run(cmd, check=True)
    return path


def write_seed_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_PNG_1X1)
    return path
