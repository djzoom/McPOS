from __future__ import annotations

import json

from mcpos.audio.probe import probe_audio_duration
from mcpos.models import AssetPaths
from mcpos.vo.models import VOAsset, VOConfig, VOChannelProfile, VOMode, VOSegmentKind, VOScriptBundle
from mcpos.vo.profiles import get_channel_profile
from mcpos.vo.resolver import resolve_existing_vo_asset, resolve_or_generate_vo_audio
import mcpos.vo.resolver as resolver_module
from tests.helpers import make_tone_mp3


def test_resolve_existing_vo_asset_excerpt(sg_workspace, isolated_mcpos):
    vo_dir = sg_workspace["vo_dir"]
    legacy_mp3 = vo_dir / "legacy_prayer.mp3"
    legacy_txt = vo_dir / "legacy_prayer.txt"
    make_tone_mp3(legacy_mp3, duration=4.0, frequency=330.0)
    legacy_txt.write_text("Breathe slowly and let the room grow quiet.", encoding="utf-8")

    paths = AssetPaths.from_output_dir(isolated_mcpos.repo_root / "episode" / "sg_20260307")
    vo_config = VOConfig(
        enable_vo=True,
        mode=VOMode.EXISTING_ASSET,
        existing_asset_dir=vo_dir,
        legacy_intro_max_sec=1.2,
        legacy_outro_max_sec=1.0,
    )

    outro_asset = resolve_existing_vo_asset(VOSegmentKind.OUTRO, vo_config, paths.vo_outro_mp3)

    assert outro_asset is not None
    assert outro_asset.path == paths.vo_outro_mp3
    assert outro_asset.path.exists()
    assert outro_asset.source_type == "existing_asset_excerpt"
    assert 0.7 <= (outro_asset.duration_sec or 0.0) <= 1.3


def test_resolve_or_generate_vo_audio_qwen3_mode(monkeypatch, isolated_mcpos):
    paths = AssetPaths.from_output_dir(isolated_mcpos.repo_root / "episode" / "sg_20260308")
    paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
    script_bundle = VOScriptBundle(
        txt_path=paths.vo_script_txt,
        ssml_path=paths.vo_script_ssml,
        meta_path=paths.vo_script_meta_json,
        intro_text="Welcome into a quiet place of rest.",
        outro_text="Carry this peace with you through the night.",
        intro_ssml="Welcome into a quiet place of rest.",
        outro_ssml="Carry this peace with you through the night.",
    )
    vo_config = VOConfig(
        enable_vo=True,
        mode=VOMode.QWEN3,
        existing_asset_prefer=False,
        existing_asset_dir=isolated_mcpos.repo_root / "missing_vo_assets",
    )
    profile: VOChannelProfile = get_channel_profile("sg_prayer")
    calls: list[tuple[str, str]] = []

    def fake_synthesize(source, kind, bundle, output_path, config):
        calls.append((source, kind.value))
        make_tone_mp3(output_path, duration=0.9 if kind == VOSegmentKind.INTRO else 0.8, frequency=550.0)
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

    bundle = resolve_or_generate_vo_audio(script_bundle, paths, vo_config, profile)
    meta = json.loads(paths.vo_gen_meta_json.read_text(encoding="utf-8"))

    assert bundle.intro is not None and bundle.intro.path and bundle.intro.path.exists()
    assert bundle.outro is not None and bundle.outro.path and bundle.outro.path.exists()
    assert calls[0][0] == "qwen3"
    assert meta["segments"]["intro"]["source_type"] == "qwen3"
    assert meta["degraded_to_music_only"] is False
