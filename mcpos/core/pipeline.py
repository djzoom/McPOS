"""
McPOS 核心流程

实现 run_episode、run_day、run_month 等主流程函数。
"""

from __future__ import annotations

from typing import List, Callable, Optional
from datetime import datetime
import calendar
import json

from ..models import EpisodeSpec, EpisodeState, StageName, StageResult
from ..config import get_config
from ..adapters.filesystem import (
    build_asset_paths,
    detect_episode_state_from_filesystem,
    list_available_images,
)
from .events import emit_event, EventType
from .logging import log_info, log_error, log_warning, StageEvent, log_stage_event
from ..assets import (
    init_episode,
    generate_text_base_assets,
    generate_cover_for_episode,
    run_remix_for_episode,
    generate_text_srt,
    run_render_for_episode,
)
from ..pipelines.sg_vo_pipeline import run_sg_pipeline_with_vo


async def run_episode(spec: EpisodeSpec) -> EpisodeState:
    """
    处理一期节目的完整生命周期。
    
    McPOS v1 按依赖顺序执行六个阶段:
    INIT → TEXT_BASE → COVER → MIX → TEXT_SRT → RENDER
    
    TEXT_BASE 和 COVER 都只依赖 playlist.csv, 理论上可以并行,
    这里先保持简单的线性顺序。
    """
    if spec.channel_id == "sg":
        return await run_sg_pipeline_with_vo(spec)

    config = get_config()
    
    # 构建 AssetPaths
    asset_paths = build_asset_paths(spec, config)
    
    # 从文件系统检测状态（不使用 ASR）
    state = detect_episode_state_from_filesystem(spec, asset_paths)
    
    stages = [
        (StageName.INIT, init_episode),
        (StageName.TEXT_BASE, generate_text_base_assets),
        (StageName.COVER, generate_cover_for_episode),
        (StageName.MIX, run_remix_for_episode),
        (StageName.TEXT_SRT, generate_text_srt),
        (StageName.RENDER, run_render_for_episode),
        # Upload / verify 是未来的 Stage, 不在 v1 中执行
    ]
    
    emit_event(EventType.EPISODE_STARTED, {
        "channel_id": spec.channel_id,
        "episode_id": spec.episode_id,
    })
    
    for stage_name, stage_func in stages:
        if state.stage_completed.get(stage_name, False):
            continue
        
        state.current_stage = stage_name
        state.updated_at = datetime.now()
        
        # 阶段开始: 事件 + 结构化日志
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
            result: StageResult = await stage_func(spec, asset_paths)
            
            state.stage_completed[stage_name] = result.success
            if not result.success:
                state.error_message = result.error_message
            
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
                status="done" if result.success else "failed",
                message=result.error_message,
                extra={
                    "duration_seconds": result.duration_seconds,
                },
            ))
            
            if not result.success:
                # 失败则终止后续 Stage
                break
                
        except Exception as e:  # noqa: BLE001
            msg = f"Stage {stage_name.value} raised exception: {e}"
            log_error(f"[pipeline] {msg}")
            
            state.stage_completed[stage_name] = False
            state.error_message = str(e)
            
            emit_event(EventType.STAGE_FAILED, {
                "channel_id": spec.channel_id,
                "episode_id": spec.episode_id,
                "stage": stage_name.value,
                "error": str(e),
            })
            log_stage_event(StageEvent(
                channel_id=spec.channel_id,
                episode_id=spec.episode_id,
                stage=stage_name,
                status="failed",
                message=str(e),
            ))
            break
        
        # 每个阶段结束后, 再基于文件系统重新检测一次状态
        state = detect_episode_state_from_filesystem(spec, asset_paths)
    
    if state.is_core_complete():
        emit_event(EventType.EPISODE_FINISHED, {
            "channel_id": spec.channel_id,
            "episode_id": spec.episode_id,
            "success": True,
        })
    else:
        emit_event(EventType.EPISODE_FAILED, {
            "channel_id": spec.channel_id,
            "episode_id": spec.episode_id,
            "success": False,
            "error": state.error_message,
        })
    
    return state


def get_dates_for_month(year: int, month: int, start_date: int = 1) -> List[str]:
    """获取指定月份的所有日期（YYYYMMDD格式）"""
    _, last_day = calendar.monthrange(year, month)
    return [
        f"{year:04d}{month:02d}{day:02d}"
        for day in range(start_date, last_day + 1)
    ]


def _episode_has_reserved_image(paths) -> bool:
    if not paths.recipe_json.exists():
        return False
    try:
        recipe = json.loads(paths.recipe_json.read_text(encoding="utf-8"))
    except Exception as e:
        log_warning(f"[pipeline] Failed to read recipe.json for image check: {e}")
        return False
    image_filename = recipe.get("cover_image_filename") or recipe.get("image_filename")
    return bool(image_filename)


def _ensure_image_capacity(specs: List[EpisodeSpec], skip_completed: bool) -> None:
    """
    批量制作前预检图库容量。
    只统计需要新选图的期数（recipe.json 无封面图记录）。
    """
    config = get_config()
    available_count = len(list_available_images())
    needed = 0

    for spec in specs:
        paths = build_asset_paths(spec, config)
        if skip_completed:
            state = detect_episode_state_from_filesystem(spec, paths)
            if state.is_core_complete():
                continue
        if _episode_has_reserved_image(paths):
            continue
        needed += 1

    if needed > available_count:
        raise RuntimeError(
            f"需要{needed}张图才能继续制作，当前可用{available_count}张。"
        )


async def run_episode_batch(
    channel_id: str,
    dates: List[str],
    *,
    skip_completed: bool = True,
    max_concurrent: int = 1,
    progress_callback: Optional[Callable[[dict, int, int], None]] = None,
) -> List[dict]:
    """
    批量处理指定日期列表的节目（串行）。
    返回结果列表，包含每期的状态与错误信息。
    """
    if max_concurrent != 1:
        raise ValueError("Batch production supports serial only (max_concurrent must be 1).")

    specs = [
        EpisodeSpec(
            channel_id=channel_id,
            date=date_str,
            episode_id=f"{channel_id}_{date_str}",
        )
        for date_str in dates
    ]

    # 预检图库容量（避免跑到中途才失败）
    if specs:
        _ensure_image_capacity(specs, skip_completed=skip_completed)

    results: List[dict] = []
    config = get_config()

    total = len(specs)
    for idx, spec in enumerate(specs, 1):
        paths = build_asset_paths(spec, config)

        if skip_completed:
            state = detect_episode_state_from_filesystem(spec, paths)
            if state.is_core_complete():
                result = {
                    "episode_id": spec.episode_id,
                    "date": spec.date,
                    "status": "skipped",
                    "reason": "already_complete",
                    "state": state,
                }
                results.append(result)
                if progress_callback:
                    progress_callback(result, idx, total)
                continue

        start_time = datetime.now()
        try:
            state = await run_episode(spec)
            duration = (datetime.now() - start_time).total_seconds()
            if state.is_core_complete():
                result = {
                    "episode_id": spec.episode_id,
                    "date": spec.date,
                    "status": "success",
                    "duration_seconds": duration,
                    "state": state,
                }
                results.append(result)
                if progress_callback:
                    progress_callback(result, idx, total)
            else:
                result = {
                    "episode_id": spec.episode_id,
                    "date": spec.date,
                    "status": "failed",
                    "duration_seconds": duration,
                    "error": state.error_message,
                    "state": state,
                }
                results.append(result)
                if progress_callback:
                    progress_callback(result, idx, total)
        except Exception as e:  # noqa: BLE001
            duration = (datetime.now() - start_time).total_seconds()
            log_error(f"[pipeline] run_episode_batch error for {spec.episode_id}: {e}")
            result = {
                "episode_id": spec.episode_id,
                "date": spec.date,
                "status": "error",
                "duration_seconds": duration,
                "error": str(e),
            }
            results.append(result)
            if progress_callback:
                progress_callback(result, idx, total)

    return results


async def run_day(channel_id: str, date: str) -> List[EpisodeState]:
    """
    处理某一天的所有节目。
    
    从 scheduler 获取该天的 EpisodeSpec 列表，然后逐个调用 run_episode。
    """
    dates = [date]
    emit_event(EventType.RUN_STARTED, {
        "scope": "day",
        "channel_id": channel_id,
        "date": date,
        "episode_count": len(dates),
    })

    batch_results = await run_episode_batch(
        channel_id=channel_id,
        dates=dates,
        skip_completed=True,
        max_concurrent=1,
    )

    states: List[EpisodeState] = [
        r["state"] for r in batch_results if r.get("state") is not None
    ]

    emit_event(EventType.RUN_FINISHED, {
        "scope": "day",
        "channel_id": channel_id,
        "date": date,
        "completed": len([r for r in states if r.is_core_complete()]),
        "failed": len([r for r in states if r.error_message]),
    })

    return states


async def run_month(channel_id: str, year: int, month: int) -> List[EpisodeState]:
    """
    处理某个月的所有节目。
    
    从 scheduler 获取该月的 EpisodeSpec 列表，然后逐个调用 run_episode。
    """
    dates = get_dates_for_month(year, month, start_date=1)

    emit_event(EventType.RUN_STARTED, {
        "scope": "month",
        "channel_id": channel_id,
        "year": year,
        "month": month,
        "episode_count": len(dates),
    })

    batch_results = await run_episode_batch(
        channel_id=channel_id,
        dates=dates,
        skip_completed=True,
        max_concurrent=1,
    )

    states: List[EpisodeState] = [
        r["state"] for r in batch_results if r.get("state") is not None
    ]

    emit_event(EventType.RUN_FINISHED, {
        "scope": "month",
        "channel_id": channel_id,
        "year": year,
        "month": month,
        "completed": len([r for r in states if r.is_core_complete()]),
        "failed": len([r for r in states if r.error_message]),
    })

    return states
