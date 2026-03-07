"""Formal SG orchestration with VO support."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

from ..adapters.filesystem import build_asset_paths, detect_episode_state_from_filesystem, list_available_images
from ..assets.cover import generate_cover_for_episode
from ..assets.init import _load_used_image_filenames
from ..assets.text import generate_text_srt
from ..audio.ducking import apply_ducking_and_mix
from ..audio.normalize import normalize_vo_audio
from ..audio.probe import probe_audio_duration
from ..config import get_config, load_channel_config
from ..core.channel import get_channel_plugin
from ..core.events import EventType, emit_event
from ..core.logging import StageEvent, log_error, log_info, log_stage_event, log_warning
from ..models import AssetPaths, EpisodeSpec, EpisodeState, StageName, StageResult, Track, get_required_stages
from ..vo import build_vo_timeline, get_channel_profile, load_vo_config, resolve_or_generate_vo_audio, resolve_or_generate_vo_script
from ..vo.models import VOAudioBundle, VOAsset, VOConfig, VOScriptBundle, VOSegmentKind


def _format_timestamp(seconds: float) -> str:
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _load_sg_plugin():
    channel_cfg = load_channel_config("sg")
    plugin = get_channel_plugin("sg", channel_cfg)
    return channel_cfg, plugin


def _load_tracks_from_playlist(paths: AssetPaths) -> list[Track]:
    tracks: list[Track] = []
    if not paths.playlist_csv.exists():
        return tracks
    with paths.playlist_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("Section") or "").strip() != "Track":
                continue
            path = (row.get("Value") or "").strip()
            title = (row.get("Title") or "").strip() or Path(path).stem
            duration = float(row.get("DurationSeconds") or 0.0)
            vocal_class = (row.get("VocalClass") or "").strip() or None
            if path:
                tracks.append(Track(
                    path=Path(path),
                    title=title,
                    duration_sec=duration,
                    vocal_class=vocal_class,  # type: ignore[arg-type]
                ))
    return tracks


def _display_sides(tracks: list[Track]) -> tuple[list[Track], list[Track]]:
    midpoint = max(1, len(tracks) // 2)
    return tracks[:midpoint], tracks[midpoint:]


def _timeline_entries(tracks: list[Track], crossfade_sec: float) -> tuple[list[dict], float]:
    entries: list[dict] = []
    current = 0.0
    for idx, track in enumerate(tracks):
        start = max(0.0, current)
        end = start + track.duration_sec
        entries.append({
            "index": idx + 1,
            "track": track,
            "start_sec": start,
            "end_sec": end,
        })
        if idx < len(tracks) - 1:
            current = end - crossfade_sec
        else:
            current = end
    return entries, max(current, 0.0)


def _write_sg_playlist_csv(paths: AssetPaths, tracks: list[Track], *, crossfade_sec: float) -> float:
    side_a, side_b = _display_sides(tracks)
    timeline_entries, total_duration = _timeline_entries(tracks, crossfade_sec)
    side_lookup = {track.path: "A" for track in side_a}
    side_lookup.update({track.path: "B" for track in side_b})

    paths.playlist_csv.parent.mkdir(parents=True, exist_ok=True)
    with paths.playlist_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "Section",
            "Field",
            "Value",
            "Side",
            "TrackNo",
            "Title",
            "Duration",
            "DurationSeconds",
            "Timeline",
            "Timestamp",
            "Description",
            "VocalClass",
        ])

        for side_label, side_tracks in (("A", side_a), ("B", side_b)):
            total_side_sec = int(sum(track.duration_sec for track in side_tracks))
            writer.writerow(["Summary", "SideTotal", f"{len(side_tracks)} tracks", side_label, "", "", _format_timestamp(total_side_sec), total_side_sec, "", "", "", ""])
            for idx, track in enumerate(side_tracks, start=1):
                writer.writerow([
                    "Track",
                    "Song",
                    str(track.path),
                    side_label,
                    idx,
                    track.title,
                    _format_timestamp(track.duration_sec),
                    int(round(track.duration_sec)),
                    "",
                    "",
                    "",
                    track.vocal_class or "",
                ])

        for entry in timeline_entries:
            track = entry["track"]
            writer.writerow([
                "Timeline",
                "",
                "",
                side_lookup.get(track.path, "A"),
                "",
                "",
                "",
                "",
                "Clean",
                _format_timestamp(entry["start_sec"]),
                track.title,
                track.vocal_class or "",
            ])

    return total_duration


def _write_sg_timeline_csv(paths: AssetPaths, tracks: list[Track], *, crossfade_sec: float) -> None:
    entries, _ = _timeline_entries(tracks, crossfade_sec)
    with paths.timeline_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["start_time", "end_time", "track_path", "track_title"])
        for entry in entries:
            track = entry["track"]
            writer.writerow([
                f"{entry['start_sec']:.3f}",
                f"{entry['end_sec']:.3f}",
                str(track.path),
                track.title,
            ])


def _select_cover_image(spec: EpisodeSpec, paths: AssetPaths) -> tuple[str, str | None]:
    if paths.recipe_json.exists():
        try:
            recipe = json.loads(paths.recipe_json.read_text(encoding="utf-8"))
            image_name = recipe.get("cover_image_filename") or recipe.get("image_filename")
            cover_source = recipe.get("cover_source_filename")
            if image_name:
                episode_local = paths.episode_output_dir / image_name
                if episode_local.exists():
                    return image_name, cover_source
        except Exception:
            pass

    local_candidates = [
        path for path in paths.episode_output_dir.glob("*.png")
        if path.name != paths.cover_png.name and not path.name.endswith("_cover.png")
    ]
    if local_candidates:
        local_candidates.sort()
        return local_candidates[0].name, local_candidates[0].name

    used_images = _load_used_image_filenames(spec.channel_id, spec.episode_id)
    available_images = sorted(list_available_images(), key=lambda item: item.name.lower())
    for image_path in available_images:
        if image_path.name in used_images:
            continue
        target = paths.episode_output_dir / image_path.name
        if not target.exists():
            shutil.copy2(image_path, target)
        return target.name, image_path.name

    raise FileNotFoundError("No available cover image for SG episode")


def _write_sg_recipe_json(
    paths: AssetPaths,
    spec: EpisodeSpec,
    tracks: list[Track],
    total_duration_sec: float,
    *,
    image_filename: str,
    cover_source_filename: str | None,
) -> None:
    side_a, side_b = _display_sides(tracks)
    payload = {
        "episode_id": spec.episode_id,
        "channel_id": spec.channel_id,
        "schedule_date": spec.date or datetime.now().strftime("%Y%m%d"),
        "created_at": datetime.now().isoformat(),
        "stages": [
            StageName.INIT.value,
            StageName.COVER.value,
            StageName.TEXT_BASE.value,
            StageName.MIX.value,
            StageName.VO_SCRIPT.value,
            StageName.VO_GEN.value,
            StageName.VO_MIX.value,
            StageName.TEXT_SRT.value,
            StageName.RENDER.value,
        ],
        "assets": {
            "tracks": [str(track.path) for track in tracks],
            "side_a_count": len(side_a),
            "side_b_count": len(side_b),
            "total_audio_duration_seconds": total_duration_sec,
            "total_audio_duration_formatted": _format_timestamp(total_duration_sec),
        },
        "cover_image_filename": image_filename,
    }
    if cover_source_filename:
        payload["cover_source_filename"] = cover_source_filename
    paths.recipe_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_base_text(paths: AssetPaths) -> dict[str, str]:
    return {
        "title": paths.youtube_title_txt.read_text(encoding="utf-8").strip() if paths.youtube_title_txt.exists() else "",
        "description": paths.youtube_description_txt.read_text(encoding="utf-8").strip() if paths.youtube_description_txt.exists() else "",
        "tags": paths.youtube_tags_txt.read_text(encoding="utf-8").strip() if paths.youtube_tags_txt.exists() else "",
    }


def _load_script_bundle(paths: AssetPaths) -> VOScriptBundle:
    txt_sections = _read_sectioned_asset(paths.vo_script_txt)
    ssml_sections = _read_sectioned_asset(paths.vo_script_ssml)
    meta = {}
    if paths.vo_script_meta_json.exists():
        try:
            meta = json.loads(paths.vo_script_meta_json.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return VOScriptBundle(
        txt_path=paths.vo_script_txt,
        ssml_path=paths.vo_script_ssml,
        meta_path=paths.vo_script_meta_json,
        intro_text=txt_sections.get("intro"),
        outro_text=txt_sections.get("outro"),
        full_text=txt_sections.get("full"),
        intro_ssml=ssml_sections.get("intro"),
        outro_ssml=ssml_sections.get("outro"),
        full_ssml=ssml_sections.get("full"),
        metadata=meta,
    )


def _read_sectioned_asset(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current = None
    lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if line.startswith("[") and line.endswith("]"):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line.strip("[]").strip().lower()
            lines = []
            continue
        lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def _bundle_from_audio_files(paths: AssetPaths, script_bundle: VOScriptBundle) -> VOAudioBundle:
    intro = None
    outro = None
    if paths.vo_intro_mp3.exists():
        intro = VOAsset(
            kind=VOSegmentKind.INTRO,
            path=paths.vo_intro_mp3,
            duration_sec=probe_audio_duration(paths.vo_intro_mp3),
            text=script_bundle.intro_text,
            ssml_text=script_bundle.intro_ssml,
            source_type="materialized",
            status="resolved",
        )
    if paths.vo_outro_mp3.exists():
        outro = VOAsset(
            kind=VOSegmentKind.OUTRO,
            path=paths.vo_outro_mp3,
            duration_sec=probe_audio_duration(paths.vo_outro_mp3),
            text=script_bundle.outro_text,
            ssml_text=script_bundle.outro_ssml,
            source_type="materialized",
            status="resolved",
        )
    return VOAudioBundle(intro=intro, outro=outro, metadata={})


def _copy_music_mix_to_final(paths: AssetPaths) -> None:
    if not paths.music_mix_mp3.exists():
        raise FileNotFoundError(f"Music mix not found: {paths.music_mix_mp3}")
    if paths.music_mix_mp3.resolve() != paths.final_mix_mp3.resolve():
        shutil.copy2(paths.music_mix_mp3, paths.final_mix_mp3)


def _required_vo_stage_enabled(vo_config: VOConfig) -> bool:
    return vo_config.enable_vo


def _stage_success(stage: StageName, started_at: datetime, *key_paths: Path) -> StageResult:
    finished_at = datetime.now()
    return StageResult(
        stage=stage,
        success=True,
        duration_seconds=(finished_at - started_at).total_seconds(),
        key_asset_paths=[path for path in key_paths if path is not None],
        started_at=started_at,
        finished_at=finished_at,
    )


async def stage_init_sg_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    started_at = datetime.now()
    paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
    if paths.playlist_csv.exists() and paths.recipe_json.exists():
        return _stage_success(StageName.INIT, started_at, paths.playlist_csv, paths.recipe_json)

    channel_cfg, plugin = _load_sg_plugin()
    catalog = plugin.scan_library()
    tracks = plugin.select_tracks(spec, catalog)
    if not tracks:
        return StageResult(StageName.INIT, False, 0.0, [], error_message="No SG tracks selected", started_at=started_at, finished_at=datetime.now())

    image_filename, cover_source_filename = _select_cover_image(spec, paths)
    total_duration = _write_sg_playlist_csv(paths, tracks, crossfade_sec=float(channel_cfg.crossfade_sec))
    _write_sg_recipe_json(
        paths,
        spec,
        tracks,
        total_duration,
        image_filename=image_filename,
        cover_source_filename=cover_source_filename,
    )
    return _stage_success(StageName.INIT, started_at, paths.playlist_csv, paths.recipe_json)


async def stage_generate_sg_text_base(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    channel_cfg, plugin = _load_sg_plugin()
    if not spec.target_duration_min:
        spec.target_duration_min = channel_cfg.target_duration_min
    tracks = _load_tracks_from_playlist(paths)
    return await plugin.generate_text_async(spec, paths, tracks)


async def stage_generate_sg_cover(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    return await generate_cover_for_episode(spec, paths)


def stage_build_sg_music_mix(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    started_at = datetime.now()
    channel_cfg, plugin = _load_sg_plugin()
    tracks = _load_tracks_from_playlist(paths)
    if not tracks:
        return StageResult(StageName.MIX, False, 0.0, [], error_message="playlist.csv missing SG tracks", started_at=started_at, finished_at=datetime.now())

    result = plugin.build_mix(tracks, spec, paths)
    if not result.success:
        return result

    _write_sg_timeline_csv(paths, tracks, crossfade_sec=float(channel_cfg.crossfade_sec))
    vo_config = load_vo_config(channel_cfg.extra)
    key_paths = [paths.music_mix_mp3, paths.timeline_csv]
    if not _required_vo_stage_enabled(vo_config):
        _copy_music_mix_to_final(paths)
        key_paths.append(paths.final_mix_mp3)
    finished_at = datetime.now()
    return StageResult(
        stage=StageName.MIX,
        success=True,
        duration_seconds=(finished_at - started_at).total_seconds(),
        key_asset_paths=key_paths,
        started_at=started_at,
        finished_at=finished_at,
    )


def stage_generate_sg_vo_script(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    started_at = datetime.now()
    channel_cfg, _plugin = _load_sg_plugin()
    vo_config = load_vo_config(channel_cfg.extra)
    profile = get_channel_profile(vo_config.channel_profile)
    tracks = _load_tracks_from_playlist(paths)
    bundle = resolve_or_generate_vo_script(spec, paths, _read_base_text(paths), vo_config, profile, tracks=tracks)
    return _stage_success(StageName.VO_SCRIPT, started_at, bundle.txt_path, bundle.ssml_path, bundle.meta_path)


def stage_generate_sg_vo_audio(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    started_at = datetime.now()
    channel_cfg, _plugin = _load_sg_plugin()
    vo_config = load_vo_config(channel_cfg.extra)
    profile = get_channel_profile(vo_config.channel_profile)
    script_bundle = _load_script_bundle(paths)
    bundle = resolve_or_generate_vo_audio(script_bundle, paths, vo_config, profile)

    normalize_meta: dict[str, dict] = {}
    for asset in bundle.active_assets():
        stats = normalize_vo_audio(asset.path, vo_config.lufs_target, vo_config.true_peak_dbtp, output_path=asset.path)
        asset.duration_sec = probe_audio_duration(asset.path)
        normalize_meta[asset.kind.value] = {
            "input_path": str(stats.input_path),
            "output_path": str(stats.output_path),
            "input_i": stats.input_i,
            "output_i": stats.output_i,
            "target_lufs": stats.target_lufs,
            "target_peak": stats.target_peak,
            "metadata": stats.metadata,
        }

    paths.vo_normalize_meta_json.write_text(json.dumps(normalize_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    key_paths = [paths.vo_gen_meta_json, paths.vo_normalize_meta_json]
    key_paths.extend(asset.path for asset in bundle.active_assets() if asset.path)
    return _stage_success(StageName.VO_GEN, started_at, *key_paths)


def stage_apply_sg_vo_mix(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    started_at = datetime.now()
    channel_cfg, _plugin = _load_sg_plugin()
    vo_config = load_vo_config(channel_cfg.extra)
    if not paths.music_mix_mp3.exists():
        return StageResult(
            stage=StageName.VO_MIX,
            success=False,
            duration_seconds=0.0,
            key_asset_paths=[],
            error_message=f"Music mix not found: {paths.music_mix_mp3}",
            started_at=started_at,
            finished_at=datetime.now(),
        )
    script_bundle = _load_script_bundle(paths)
    bundle = _bundle_from_audio_files(paths, script_bundle)
    total_duration_sec = probe_audio_duration(paths.music_mix_mp3)

    entries, timeline_path, srt_path, timeline_meta = build_vo_timeline(
        paths.vo_intro_mp3 if paths.vo_intro_mp3.exists() else None,
        paths.vo_outro_mp3 if paths.vo_outro_mp3.exists() else None,
        total_duration_sec,
        vo_config,
        paths=paths,
        script_bundle=script_bundle,
    )

    asset_lookup = {asset.kind: asset for asset in bundle.active_assets()}
    ordered_assets = [asset_lookup[entry.kind] for entry in entries if entry.kind in asset_lookup]
    final_mix, ducking_map, ducking_meta = apply_ducking_and_mix(
        paths.music_mix_mp3,
        ordered_assets,
        entries,
        vo_config,
        output_path=paths.final_mix_mp3,
        ducking_map_path=paths.audio_ducking_map,
        meta_json_path=paths.ducking_meta_json,
    )

    merged_meta = {
        "timeline": timeline_meta,
        "ducking": ducking_meta,
        "entry_count": len(entries),
        "episode_id": spec.episode_id,
    }
    if paths.vo_gen_meta_json.exists():
        try:
            current = json.loads(paths.vo_gen_meta_json.read_text(encoding="utf-8"))
            current["vo_mix"] = merged_meta
            paths.vo_gen_meta_json.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return _stage_success(StageName.VO_MIX, started_at, final_mix, ducking_map, timeline_path, srt_path, paths.ducking_meta_json)


async def stage_generate_sg_text_srt(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    return await generate_text_srt(spec, paths)


def stage_render_sg_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    channel_cfg, plugin = _load_sg_plugin()
    if not spec.target_duration_min:
        spec.target_duration_min = channel_cfg.target_duration_min
    return plugin.render_video(spec, paths)


SG_STAGE_HANDLERS: dict[StageName, Callable[[EpisodeSpec, AssetPaths], StageResult | Awaitable[StageResult]]] = {
    StageName.INIT: stage_init_sg_episode,
    StageName.TEXT_BASE: stage_generate_sg_text_base,
    StageName.COVER: stage_generate_sg_cover,
    StageName.MIX: stage_build_sg_music_mix,
    StageName.VO_SCRIPT: stage_generate_sg_vo_script,
    StageName.VO_GEN: stage_generate_sg_vo_audio,
    StageName.VO_MIX: stage_apply_sg_vo_mix,
    StageName.TEXT_SRT: stage_generate_sg_text_srt,
    StageName.RENDER: stage_render_sg_episode,
}


async def _run_stage_handler(handler, spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    result = handler(spec, paths)
    if hasattr(result, "__await__"):
        return await result  # type: ignore[return-value]
    return result


async def run_sg_pipeline_with_vo(spec: EpisodeSpec, force: bool = False) -> EpisodeState:
    config = get_config()
    paths = build_asset_paths(spec, config)
    channel_cfg, _plugin = _load_sg_plugin()
    if not spec.target_duration_min:
        spec.target_duration_min = channel_cfg.target_duration_min

    state = detect_episode_state_from_filesystem(spec, paths)
    vo_config = load_vo_config(channel_cfg.extra)
    stages = [
        StageName.INIT,
        StageName.TEXT_BASE,
        StageName.COVER,
        StageName.MIX,
    ]
    if vo_config.enable_vo:
        stages.extend([StageName.VO_SCRIPT, StageName.VO_GEN, StageName.VO_MIX])
    stages.extend([StageName.TEXT_SRT, StageName.RENDER])

    emit_event(EventType.EPISODE_STARTED, {"channel_id": spec.channel_id, "episode_id": spec.episode_id})

    for stage_name in stages:
        if state.stage_completed.get(stage_name, False) and not force:
            continue
        state.current_stage = stage_name
        state.updated_at = datetime.now()
        emit_event(EventType.STAGE_STARTED, {
            "channel_id": spec.channel_id,
            "episode_id": spec.episode_id,
            "stage": stage_name.value,
        })
        log_stage_event(StageEvent(
            channel_id=spec.channel_id,
            episode_id=spec.episode_id,
            stage=stage_name,
            status="running",
        ))
        try:
            result = await _run_stage_handler(SG_STAGE_HANDLERS[stage_name], spec, paths)
        except Exception as exc:  # noqa: BLE001
            log_error(f"[sg/pipeline] Stage {stage_name.value} raised exception: {exc}")
            state.error_message = str(exc)
            state.stage_completed[stage_name] = False
            emit_event(EventType.STAGE_FAILED, {
                "channel_id": spec.channel_id,
                "episode_id": spec.episode_id,
                "stage": stage_name.value,
                "error": str(exc),
            })
            break

        state.stage_completed[stage_name] = result.success
        if not result.success:
            state.error_message = result.error_message
            emit_event(EventType.STAGE_FAILED, {
                "channel_id": spec.channel_id,
                "episode_id": spec.episode_id,
                "stage": stage_name.value,
                "error": result.error_message,
            })
            log_stage_event(StageEvent(
                channel_id=spec.channel_id,
                episode_id=spec.episode_id,
                stage=stage_name,
                status="failed",
                message=result.error_message,
            ))
            break

        emit_event(EventType.STAGE_FINISHED, {
            "channel_id": spec.channel_id,
            "episode_id": spec.episode_id,
            "stage": stage_name.value,
            "success": result.success,
            "duration_seconds": result.duration_seconds,
        })
        log_stage_event(StageEvent(
            channel_id=spec.channel_id,
            episode_id=spec.episode_id,
            stage=stage_name,
            status="done",
            extra={"duration_seconds": result.duration_seconds},
        ))
        state = detect_episode_state_from_filesystem(spec, paths)

    state = detect_episode_state_from_filesystem(spec, paths)
    if state.is_core_complete():
        emit_event(EventType.EPISODE_FINISHED, {
            "channel_id": spec.channel_id,
            "episode_id": spec.episode_id,
            "success": True,
            "required_stages": [stage.value for stage in get_required_stages(spec)],
        })
    else:
        emit_event(EventType.EPISODE_FAILED, {
            "channel_id": spec.channel_id,
            "episode_id": spec.episode_id,
            "success": False,
            "error": state.error_message,
        })
    return state
