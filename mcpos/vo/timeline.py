"""VO timeline and SRT generation."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from .models import VOConfig, VOSegmentKind, VOScriptBundle, VOTimelineEntry
from .ssml import parse_ssml_timeline_tokens, strip_ssml
from ..audio.probe import probe_audio_duration
from ..models import AssetPaths


def _format_srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3600 * 1000)
    minutes, rem = divmod(rem, 60 * 1000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _text_cues_for_entry(entry: VOTimelineEntry) -> list[tuple[float, float, str]]:
    tokens = parse_ssml_timeline_tokens(entry.ssml_text or entry.text)
    if not tokens:
        if entry.text:
            return [(entry.start_sec, entry.end_sec, entry.text)]
        return []

    total_break = sum(float(token["seconds"]) for token in tokens if token["type"] == "break")
    text_tokens = [token for token in tokens if token["type"] == "text"]
    total_words = sum(max(1, len(str(token["text"]).split())) for token in text_tokens) or 1
    available_speech = max(0.2, (entry.end_sec - entry.start_sec) - total_break)

    cues: list[tuple[float, float, str]] = []
    cursor = entry.start_sec
    for token in tokens:
        if token["type"] == "break":
            cursor += float(token["seconds"])
            continue
        text = str(token["text"]).strip()
        word_count = max(1, len(text.split()))
        duration = available_speech * (word_count / total_words)
        end = min(entry.end_sec, cursor + duration)
        cues.append((cursor, end, text))
        cursor = end
    return cues


def build_vo_timeline(
    intro_path: Optional[Path],
    outro_path: Optional[Path],
    total_duration_sec: float,
    vo_config: VOConfig,
    *,
    paths: AssetPaths | None = None,
    script_bundle: Optional[VOScriptBundle] = None,
) -> tuple[list[VOTimelineEntry], Path, Path, dict]:
    """Build intro/outro VO placement and corresponding CSV/SRT assets."""

    if paths is None:
        raise ValueError("paths must be provided for build_vo_timeline")

    csv_path = paths.vo_timeline_csv
    srt_path = paths.vo_srt
    entries: list[VOTimelineEntry] = []
    notes: list[str] = []

    intro_duration = probe_audio_duration(intro_path) if intro_path and intro_path.exists() else 0.0
    outro_duration = probe_audio_duration(outro_path) if outro_path and outro_path.exists() else 0.0

    if intro_path and intro_duration > 0.0:
        entries.append(VOTimelineEntry(
            segment_id="intro",
            kind=VOSegmentKind.INTRO,
            audio_path=intro_path,
            start_sec=0.0,
            end_sec=intro_duration,
            duck_start_sec=0.0,
            duck_end_sec=intro_duration + vo_config.fade_sec,
            text=script_bundle.intro_text if script_bundle else "",
            ssml_text=script_bundle.intro_ssml if script_bundle else "",
        ))

    if outro_path and outro_duration > 0.0:
        start_sec = max(0.0, total_duration_sec - outro_duration - vo_config.outro_margin_sec)
        intro_end = entries[0].end_sec if entries else 0.0
        if start_sec < intro_end:
            start_sec = intro_end
        if start_sec + outro_duration > total_duration_sec and total_duration_sec > 0.0:
            if total_duration_sec - intro_end >= max(3.0, outro_duration * 0.35):
                start_sec = max(intro_end, total_duration_sec - outro_duration)
            else:
                notes.append("Dropped outro placement because the program is too short.")
                outro_duration = 0.0
        if outro_duration > 0.0:
            entries.append(VOTimelineEntry(
                segment_id="outro",
                kind=VOSegmentKind.OUTRO,
                audio_path=outro_path,
                start_sec=start_sec,
                end_sec=start_sec + outro_duration,
                duck_start_sec=max(0.0, start_sec - vo_config.fade_sec),
                duck_end_sec=min(total_duration_sec, start_sec + outro_duration + vo_config.fade_sec) if total_duration_sec > 0 else start_sec + outro_duration + vo_config.fade_sec,
                text=script_bundle.outro_text if script_bundle else "",
                ssml_text=script_bundle.outro_ssml if script_bundle else "",
            ))

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["segment_id", "kind", "audio_path", "start_sec", "end_sec", "duck_start_sec", "duck_end_sec"])
        for entry in entries:
            writer.writerow([
                entry.segment_id,
                entry.kind.value,
                str(entry.audio_path),
                f"{entry.start_sec:.3f}",
                f"{entry.end_sec:.3f}",
                f"{entry.duck_start_sec:.3f}",
                f"{entry.duck_end_sec:.3f}",
            ])

    srt_lines: list[str] = []
    cue_idx = 1
    for entry in entries:
        for start, end, text in _text_cues_for_entry(entry):
            if not text.strip():
                continue
            srt_lines.extend([
                str(cue_idx),
                f"{_format_srt_time(start)} --> {_format_srt_time(end)}",
                strip_ssml(text),
                "",
            ])
            cue_idx += 1
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    meta = {
        "total_duration_sec": total_duration_sec,
        "entry_count": len(entries),
        "notes": notes,
        "csv_path": str(csv_path),
        "srt_path": str(srt_path),
    }
    return entries, csv_path, srt_path, meta
