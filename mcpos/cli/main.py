"""
McPOS 命令行接口

使用 typer 实现命令行入口，提供 mcpos run-* 等命令。
"""

import typer
from pathlib import Path
from typing import Optional

app = typer.Typer(help="McPOS - 节目生产操作系统")


@app.command()
def init_episode(
    channel_id: str = typer.Argument(..., help="频道 ID，如 kat"),
    episode_id: str = typer.Argument(..., help="节目 ID，如 kat_20241201"),
):
    """
    初始化单期节目：生成 playlist.csv 和 recipe.json
    """
    import asyncio
    from ..models import EpisodeSpec
    from ..config import get_config
    from ..adapters.filesystem import build_asset_paths
    from ..assets.init import init_episode as _init_episode
    
    # 从 episode_id 解析 date（简单实现）
    date = episode_id.split("_")[-1] if "_" in episode_id else episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=episode_id,
    )
    
    config = get_config()
    paths = build_asset_paths(spec, config)
    
    typer.echo(f"初始化 {episode_id} (channel: {channel_id})...")
    typer.echo(f"输出目录: {paths.episode_output_dir}")
    
    result = asyncio.run(_init_episode(spec, paths))
    
    if result.success:
        typer.echo(f"✅ 初始化完成: {episode_id}")
        typer.echo(f"   playlist.csv: {paths.playlist_csv.exists()}")
        typer.echo(f"   recipe.json: {paths.recipe_json.exists()}")
    else:
        typer.echo(f"❌ 初始化失败: {episode_id}")
        if result.error_message:
            typer.echo(f"   错误: {result.error_message}")


@app.command()
def run_episode(
    channel_id: str = typer.Argument(..., help="频道 ID，如 kat 或 rbr"),
    episode_id: str = typer.Argument(..., help="节目 ID，如 kat_20241201"),
):
    """
    处理单期节目
    """
    import asyncio
    from ..models import EpisodeSpec
    from ..core.pipeline import run_episode as _run_episode
    
    # 从 episode_id 解析 date（简单实现）
    # TODO: 更智能的解析逻辑
    date = episode_id.split("_")[-1] if "_" in episode_id else episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=episode_id,
    )
    
    result = asyncio.run(_run_episode(spec))
    
    if all(result.stage_completed.values()):
        typer.echo(f"✅ 完成: {episode_id}")
    else:
        typer.echo(f"❌ 失败: {episode_id}")
        if result.error_message:
            typer.echo(f"   错误: {result.error_message}")


@app.command()
def run_day(
    channel_id: str = typer.Argument(..., help="频道 ID"),
    date: str = typer.Argument(..., help="日期，格式 YYYYMMDD"),
):
    """
    处理某一天的所有节目
    """
    import asyncio
    from ..core.pipeline import run_day as _run_day
    
    results = asyncio.run(_run_day(channel_id, date))
    
    completed = sum(1 for r in results if all(r.stage_completed.values()))
    typer.echo(f"完成 {completed}/{len(results)} 期")


@app.command()
def run_month(
    channel_id: str = typer.Argument(..., help="频道 ID"),
    year: int = typer.Argument(..., help="年份"),
    month: int = typer.Argument(..., help="月份 (1-12)"),
):
    """
    处理某个月的所有节目
    """
    import asyncio
    from ..core.pipeline import run_month as _run_month
    
    results = asyncio.run(_run_month(channel_id, year, month))
    
    completed = sum(1 for r in results if all(r.stage_completed.values()))
    failed = sum(1 for r in results if r.error_message)
    
    typer.echo(f"完成 {completed}/{len(results)} 期")
    if failed > 0:
        typer.echo(f"失败 {failed} 期")


@app.command()
def check_status(
    channel_id: Optional[str] = typer.Option(None, help="频道 ID（可选）"),
    year: Optional[int] = typer.Option(None, help="年份（必须与 month 同时提供）"),
    month: Optional[int] = typer.Option(None, help="月份（必须与 year 同时提供）"),
):
    """
    检查节目完成状态
    
    注意：year 和 month 必须同时提供才能查询完成情况。
    """
    from ..core.state import get_episode_completion_rate
    
    if not (year and month):
        typer.echo("❌ 请同时提供 year 和 month 才能检查完成情况")
        typer.echo("   示例: mcpos check-status --year 2024 --month 12")
        raise typer.Abort()
    
    rates = get_episode_completion_rate(channel_id or "kat", year, month)
    typer.echo(f"{year}年{month}月完成情况:")
    for stage, rate in rates.items():
        typer.echo(f"  {stage}: {rate:.1%}")


@app.command()
def reset_episode(
    channel_id: str = typer.Argument(..., help="频道 ID，如 kat"),
    episode_id: str = typer.Argument(..., help="节目 ID，如 kat_20241201"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="确认删除，跳过提示"),
):
    """
    重置期数：删除所有输出文件，恢复图、曲使用状态
    
    注意：
    - 删除该期数的所有输出文件
    - 恢复图片使用状态（从 used 移回 available）
    - 不会将图、曲移至 used（因为 reset 意味着取消，不是真正使用）
    - 只有检查上传排播后，才会记录使用情况并移动图到 used
    """
    from ..models import EpisodeSpec
    from ..adapters.filesystem import reset_episode_assets
    
    if not confirm:
        typer.echo(f"⚠️  警告：将删除 {episode_id} 的所有输出文件并恢复图、曲使用状态")
        if not typer.confirm("确认继续？"):
            typer.echo("已取消")
            raise typer.Abort()
    
    # 从 episode_id 解析 date（简单实现）
    date = episode_id.split("_")[-1] if "_" in episode_id else episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=episode_id,
    )
    
    typer.echo(f"重置 {episode_id} (channel: {channel_id})...")
    
    result = reset_episode_assets(spec)
    
    if result["errors"]:
        typer.echo(f"❌ 重置完成，但有错误:")
        for error in result["errors"]:
            typer.echo(f"   {error}")
    else:
        typer.echo(f"✅ 重置完成: {episode_id}")
        typer.echo(f"   删除文件数: {len(result['deleted_files'])}")
        if result["restored_image"]:
            typer.echo(f"   已恢复图片到 available")
        else:
            typer.echo(f"   图片未在 used 中（可能已恢复或不存在）")


@app.command()
def reset_last_ep(
    channel_id: str = typer.Argument(..., help="频道 ID，如 kat"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="确认删除，跳过提示"),
):
    """
    重置最后一期：删除时间最晚的一期节目的所有输出文件，恢复图、曲使用状态
    
    注意：
    - 自动查找时间最晚的期数（根据输出目录的修改时间）
    - 删除该期数的所有输出文件
    - 恢复图片使用状态（从 used 移回 available）
    - 不会将图、曲移至 used（因为 reset 意味着取消，不是真正使用）
    """
    from ..models import EpisodeSpec
    from ..adapters.filesystem import reset_episode_assets, find_latest_episode
    
    # 查找时间最晚的期数
    latest_episode_id = find_latest_episode(channel_id)
    
    if not latest_episode_id:
        typer.echo(f"❌ 未找到任何期数 (channel: {channel_id})")
        raise typer.Abort()
    
    if not confirm:
        typer.echo(f"⚠️  警告：将删除最后一期 {latest_episode_id} 的所有输出文件并恢复图、曲使用状态")
        if not typer.confirm("确认继续？"):
            typer.echo("已取消")
            raise typer.Abort()
    
    # 从 episode_id 解析 date（简单实现）
    date = latest_episode_id.split("_")[-1] if "_" in latest_episode_id else latest_episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=latest_episode_id,
    )
    
    typer.echo(f"重置最后一期: {latest_episode_id} (channel: {channel_id})...")
    
    result = reset_episode_assets(spec)
    
    if result["errors"]:
        typer.echo(f"❌ 重置完成，但有错误:")
        for error in result["errors"]:
            typer.echo(f"   {error}")
    else:
        typer.echo(f"✅ 重置完成: {latest_episode_id}")
        typer.echo(f"   删除文件数: {len(result['deleted_files'])}")
        if result["restored_image"]:
            typer.echo(f"   已恢复图片到 available")
        else:
            typer.echo(f"   图片未在 used 中（可能已恢复或不存在）")


@app.command()
def run_stage(
    channel_id: str = typer.Argument(..., help="频道 ID，如 kat"),
    episode_id: str = typer.Argument(..., help="节目 ID，如 kat_20241201"),
    stage_name: str = typer.Argument(..., help="阶段名称：INIT, TEXT_BASE, COVER, MIX, TEXT_SRT, RENDER"),
):
    """
    运行单个阶段
    
    支持的阶段：
    - INIT: 初始化（生成 playlist.csv 和 recipe.json）
    - TEXT_BASE: 生成基础文本资产（标题、描述、标签）
    - COVER: 生成封面图片
    - MIX: 音频混音
    - TEXT_SRT: 生成字幕文件（需要先完成 MIX）
    - RENDER: 视频渲染（需要先完成 COVER 和 MIX）
    
    注意：每个阶段都是幂等的，如果资产已存在会跳过。
    """
    import asyncio
    from ..models import EpisodeSpec, StageName
    from ..config import get_config
    from ..adapters.filesystem import build_asset_paths
    # 显式子模块导入，不依赖 assets.__init__.py 的 re-export
    from ..assets.init import init_episode as stage_init_episode
    from ..assets.text import (
        generate_text_base_assets,
        generate_text_srt,
    )
    from ..assets.cover import generate_cover_for_episode
    from ..assets.mix import run_remix_for_episode
    from ..assets.render import run_render_for_episode
    
    # 解析阶段名称
    stage_name_upper = stage_name.upper()
    stage_mapping = {
        "INIT": (StageName.INIT, stage_init_episode),
        "TEXT_BASE": (StageName.TEXT_BASE, generate_text_base_assets),
        "COVER": (StageName.COVER, generate_cover_for_episode),
        "MIX": (StageName.MIX, run_remix_for_episode),
        "TEXT_SRT": (StageName.TEXT_SRT, generate_text_srt),
        "RENDER": (StageName.RENDER, run_render_for_episode),
    }
    
    if stage_name_upper not in stage_mapping:
        typer.echo(f"❌ 无效的阶段名称: {stage_name}")
        typer.echo(f"   支持的阶段: {', '.join(stage_mapping.keys())}")
        raise typer.Abort()
    
    stage_enum, stage_func = stage_mapping[stage_name_upper]
    
    # 从 episode_id 解析 date（简单实现）
    date = episode_id.split("_")[-1] if "_" in episode_id else episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=episode_id,
    )
    
    config = get_config()
    paths = build_asset_paths(spec, config)
    
    typer.echo(f"运行阶段 {stage_name_upper} for {episode_id} (channel: {channel_id})...")
    
    try:
        result = asyncio.run(stage_func(spec, paths))
        
        if result.success:
            typer.echo(f"✅ 阶段 {stage_name_upper} 完成: {episode_id}")
            typer.echo(f"   耗时: {result.duration_seconds:.2f} 秒")
            if result.key_asset_paths:
                typer.echo(f"   生成文件:")
                for asset_path in result.key_asset_paths:
                    exists = "✅" if asset_path.exists() else "❌"
                    typer.echo(f"     {exists} {asset_path.name}")
        else:
            typer.echo(f"❌ 阶段 {stage_name_upper} 失败: {episode_id}")
            if result.error_message:
                typer.echo(f"   错误: {result.error_message}")
    except Exception as e:
        typer.echo(f"❌ 阶段 {stage_name_upper} 执行异常: {episode_id}")
        typer.echo(f"   错误: {str(e)}")
        raise typer.Exit(1)


@app.command()
def upload_episode(
    channel_id: str = typer.Argument(..., help="频道 ID，如 kat"),
    episode_id: str = typer.Argument(..., help="节目 ID，如 kat_20251201"),
):
    """
    上传期数视频到 YouTube
    
    必需文件：
    - 视频文件 (youtube.mp4): 必须存在且通过 ffprobe 校验
    - 标题文件 (youtube_title.txt): 必须存在且非空
    - 描述文件 (youtube_description.txt): 必须存在
    - 标签文件 (youtube_tags.txt): 必须存在且非空
    - 字幕文件 (youtube.srt): 必须存在（用于上传字幕）
    
    可选文件：
    - 缩略图 (cover.png): 缺失时跳过缩略图上传（会自动调整大小：最大 1280x720 像素，最大 2MB）
    
    配置说明：
    - 默认语言：强制设置为 "en"（字幕上传需要）
    - 播放列表：从 config.yaml 自动读取（默认：PLAn_Q-OQCpRLeHEWW4gf9EjZyTiwCfcaH）
    """
    import asyncio
    from ..models import EpisodeSpec
    from ..config import get_config
    from ..adapters.filesystem import build_asset_paths
    from ..adapters.uploader import upload_episode_video
    
    # 从 episode_id 解析 date（简单实现）
    date = episode_id.split("_")[-1] if "_" in episode_id else episode_id
    
    spec = EpisodeSpec(
        channel_id=channel_id,
        date=date,
        episode_id=episode_id,
    )
    
    config = get_config()
    paths = build_asset_paths(spec, config)
    
    typer.echo(f"上传 {episode_id} 到 YouTube (channel: {channel_id})...")
    typer.echo(f"视频文件: {paths.youtube_mp4}")
    
    result = asyncio.run(upload_episode_video(spec, paths, config))
    
    if result.state == "uploaded":
        typer.echo(f"✅ 上传成功: {episode_id}")
        if result.video_id:
            typer.echo(f"   Video ID: {result.video_id}")
            if result.extra and "video_url" in result.extra:
                typer.echo(f"   URL: {result.extra['video_url']}")
    elif result.state == "failed":
        typer.echo(f"❌ 上传失败: {episode_id}")
        if result.error:
            typer.echo(f"   错误: {result.error}")
        if result.extra:
            typer.echo(f"   详情: {result.extra}")
    else:
        typer.echo(f"⚠️  上传状态: {result.state}")
        if result.error:
            typer.echo(f"   错误: {result.error}")


@app.command()
def rename_library(
    channel_id: str = typer.Argument(..., help="频道 ID，如 rbr 或 kat"),
    model: str = typer.Option("gpt-4o-mini", help="OpenAI模型（用于修复问题标题）"),
    no_api: bool = typer.Option(False, "--no-api", help="不使用API修复（仅使用模板库）"),
    execute: bool = typer.Option(False, "--execute", help="真正执行重命名（默认是dry-run）"),
    source_dir: Optional[str] = typer.Option(None, "--source-dir", help="源目录名称（相对于 library/），默认使用 songs 目录。例如：--source-dir 'Suno 0127'"),
):
    """
    批量重命名频道歌库
    
    功能：
    - 自动检测并修复问题标题（New New、数字重复、以数字结尾等）
    - 使用API生成富有创意的标题（可选）
    - 确保标题唯一性
    - 支持频道特定配置（channels/{channel_id}/config/library_rename.json）
    
    默认行为：
    - 预览模式（dry-run），不会实际重命名文件
    - 使用API修复问题标题
    - 输出重命名计划到 channels/{channel_id}/library/{source_dir}/rename_plan.csv
    
    使用示例：
    - 预览 songs 目录：python3 -m mcpos.cli.main rename-library rbr
    - 执行重命名：python3 -m mcpos.cli.main rename-library rbr --execute
    - 不使用API：python3 -m mcpos.cli.main rename-library rbr --no-api
    - 重命名 Suno 0127 目录：python3 -m mcpos.cli.main rename-library kat --source-dir "Suno 0127" --execute
    """
    from ..config import get_config
    from ..adapters.library_renamer import rename_channel_library
    
    config = get_config()
    
    try:
        rename_channel_library(
            channel_id=channel_id,
            channels_root=config.channels_root,
            model=model,
            execute=execute,
            use_api=not no_api,
            source_dir=source_dir,
        )
        typer.echo(f"\n✅ 重命名完成: {channel_id}")
    except ValueError as e:
        typer.echo(f"❌ 错误: {e}")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ 执行失败: {e}")
        raise typer.Exit(1)


@app.command()
def optimize_poor_titles(
    channel_id: str = typer.Argument(..., help="频道 ID，如 rbr"),
    model: str = typer.Option("gpt-4o-mini", help="OpenAI模型（用于修复问题标题）"),
    no_api: bool = typer.Option(False, "--no-api", help="不使用API修复（仅使用模板库）"),
    execute: bool = typer.Option(False, "--execute", help="真正执行重命名（默认是dry-run）"),
):
    """
    优化 Poor_Titles 目录中的歌曲标题
    
    功能：
    - 只处理 Poor_Titles 目录中的文件
    - 确保不与 RBR_Songs_Library 中的标题重复
    - 自动检测并修复问题标题（New New、数字重复、以数字结尾等）
    - 使用API生成富有创意的标题（可选）
    
    默认行为：
    - 预览模式（dry-run），不会实际重命名文件
    - 使用API修复问题标题
    - 输出优化计划到 channels/{channel_id}/library/songs/Poor_Titles/optimize_plan.csv
    
    使用示例：
    - 预览：python3 -m mcpos.cli.main optimize-poor-titles rbr
    - 执行：python3 -m mcpos.cli.main optimize-poor-titles rbr --execute
    - 不使用API：python3 -m mcpos.cli.main optimize-poor-titles rbr --no-api
    """
    typer.echo("⚠️  optimize-poor-titles 已停用（冗余且易造成高 API 花费）。")
    typer.echo("   请改用：rename-library 并指定 source-dir，例如：")
    typer.echo("   python3 -m mcpos.cli.main rename-library rbr --source-dir \"songs/Poor_Titles\" --no-api")
    raise typer.Exit(1)


@app.command()
def rename_kat_lofi(
    channel_id: str = typer.Argument("kat", help="频道 ID（默认 kat）"),
    source_dir: str = typer.Option("Suno 0127", "--source-dir", help="源目录名称（相对于 library/）"),
    model: str = typer.Option("gpt-4o-mini", help="OpenAI 模型"),
    no_api: bool = typer.Option(False, "--no-api", help="不使用 API（优先使用模板库）"),
    execute: bool = typer.Option(False, "--execute", help="真正执行重命名和 ID3 写入（默认是 dry-run）"),
    rename_all: bool = typer.Option(False, "--rename-all", help="重新命名所有文件（不仅仅是 UUID 格式），用于增加多样性"),
):
    """
    重命名 Kat 频道的 Lo-Fi 曲目库
    
    功能：
    - 为 UUID 格式的文件生成 Lo-Fi 风格的标题（或使用 --rename-all 重新命名所有文件）
    - 写入 ID3 标签（标题和艺术家 0xgarfield）
    - 避免与现有 songs 目录中的标题重复
    - 避免过度使用高频词汇，确保首单词、长度、词汇的多样性
    - 优先使用模板库减少 API 调用，只在必要时调用 API
    
    默认行为：
    - 预览模式（dry-run），不会实际重命名文件
    - 优先使用模板库，必要时使用 API 生成标题
    - 输出重命名计划到 channels/{channel_id}/library/{source_dir}/rename_plan.csv
    
    使用示例：
    - 预览：python3 -m mcpos.cli.main rename-kat-lofi kat --source-dir "Suno 0127"
    - 执行：python3 -m mcpos.cli.main rename-kat-lofi kat --source-dir "Suno 0127" --execute
    - 重新命名所有文件以增加多样性：python3 -m mcpos.cli.main rename-kat-lofi kat --source-dir "Suno 0127" --rename-all --execute
    """
    from ..config import get_config
    from ..adapters.kat_lofi_renamer import rename_kat_lofi_library
    
    config = get_config()
    
    try:
        rename_kat_lofi_library(
            channel_id=channel_id,
            channels_root=config.channels_root,
            source_dir=source_dir,
            model=model,
            execute=execute,
            use_api=not no_api,
            rename_all=rename_all,
        )
        typer.echo(f"\n✅ 重命名完成: {channel_id}")
    except ValueError as e:
        typer.echo(f"❌ 错误: {e}")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ 执行失败: {e}")
        raise typer.Exit(1)


@app.command()
def fix_kat_lofi_titles(
    channel_id: str = typer.Argument("kat", help="频道 ID（默认 kat）"),
    source_dir: str = typer.Option("Suno 0127", "--source-dir", help="源目录名称（相对于 library/）"),
    model: str = typer.Option("gpt-4o-mini", help="OpenAI 模型"),
    execute: bool = typer.Option(False, "--execute", help="真正执行修复和重命名（默认是 dry-run）"),
):
    """
    修复 Kat 频道 Lo-Fi 曲目库中有问题的标题
    
    功能：
    - 检测语法错误、不完整的标题（如以介词结尾、包含问号等）
    - 使用 API 修复这些问题标题
    - 重新命名文件并更新 ID3 标签
    
    默认行为：
    - 预览模式（dry-run），不会实际修复文件
    - 输出修复计划到 channels/{channel_id}/library/{source_dir}/fix_problematic_titles_plan.csv
    
    使用示例：
    - 预览：python3 -m mcpos.cli.main fix-kat-lofi-titles kat --source-dir "Suno 0127"
    - 执行：python3 -m mcpos.cli.main fix-kat-lofi-titles kat --source-dir "Suno 0127" --execute
    """
    from ..config import get_config
    from ..adapters.kat_lofi_renamer import fix_problematic_titles
    
    config = get_config()
    
    try:
        fix_problematic_titles(
            channel_id=channel_id,
            channels_root=config.channels_root,
            source_dir=source_dir,
            model=model,
            execute=execute,
        )
        typer.echo(f"\n✅ 修复完成: {channel_id}")
    except ValueError as e:
        typer.echo(f"❌ 错误: {e}")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ 执行失败: {e}")
        raise typer.Exit(1)


@app.command()
def rbr_broadcast_scan(
    force: bool = typer.Option(False, "--force", help="强制重新扫描所有文件"),
):
    """
    RBR频道广播系统：扫描曲库并分析
    
    将分析结果写入数据库和ID3标签，用于每日节目播放列表生成
    """
    from ..adapters.broadcast.rbr_config import RBRBroadcastConfig
    from ..adapters.broadcast.analyzer import AudioAnalyzer
    from ..adapters.broadcast.db import LibraryManager
    
    config = RBRBroadcastConfig()
    
    # 验证模型
    is_valid, errors = config.validate()
    if not is_valid:
        typer.echo("❌ 配置验证失败:")
        for error in errors:
            typer.echo(f"   - {error}")
        typer.echo("\n💡 请先下载模型:")
        typer.echo("   curl -L -o models/voice_instrumental-discogs-effnet-1.pb https://essentia.upf.edu/models/classifiers/voice_instrumental/voice_instrumental-discogs-effnet-1/voice_instrumental-discogs-effnet-1.pb")
        typer.echo("   curl -L -o models/discogs-effnet-bs64-1.pb https://essentia.upf.edu/models/feature-extractors/discogs/effnet/discogs-effnet-bs64-1/discogs-effnet-bs64-1.pb")
        raise typer.Exit(1)
    
    typer.echo("✅ 模型验证通过")
    typer.echo(f"📁 音乐目录: {config.music_dir}")
    typer.echo(f"💾 数据库: {config.db_path}")
    typer.echo("\n开始扫描...\n")
    
    analyzer = AudioAnalyzer(config)
    manager = LibraryManager(config, analyzer)
    
    stats = manager.scan_directory(force_rescan=force)
    
    typer.echo(f"\n✅ 扫描完成:")
    typer.echo(f"   总文件: {stats['total']}")
    typer.echo(f"   新增: {stats['new']}")
    typer.echo(f"   更新: {stats['updated']}")
    typer.echo(f"   跳过: {stats['skipped']}")
    typer.echo(f"   错误: {stats['errors']}")


@app.command()
def rbr_build_playlist(
    episode_id: str = typer.Argument(..., help="集数ID，如 rbr_20250101"),
    target_bpm: Optional[float] = typer.Option(None, "--bpm", help="目标BPM（160-200，每5一个台阶）"),
    duration: float = typer.Option(60.0, "--duration", help="目标时长（分钟，默认60）"),
    max_vocals: int = typer.Option(3, "--max-vocals", help="最多几首高人声歌曲"),
    output_txt: bool = typer.Option(True, "--txt/--no-txt", help="生成Liquidsoap播放列表文件"),
    output_csv: bool = typer.Option(True, "--csv/--no-csv", help="生成CSV播放列表文件"),
):
    """
    RBR频道：构建一期节目的播放列表
    
    每天一期节目，BPM 160-200，时长30分钟到5小时（80%是1小时）
    
    示例:
    - 1小时节目，BPM 170: python3 -m mcpos.cli.main rbr-build-playlist rbr_20250101 --bpm 170 --duration 60
    - 随机BPM: python3 -m mcpos.cli.main rbr-build-playlist rbr_20250101 --duration 60
    """
    from ..config import get_config
    from ..adapters.broadcast.rbr_config import RBRBroadcastConfig
    from ..adapters.broadcast.playlist_generator import RBRPlaylistGenerator
    
    config = get_config()
    rbr_config = RBRBroadcastConfig(channels_root=config.channels_root)
    
    generator = RBRPlaylistGenerator(rbr_config)
    
    try:
        outputs = []
        
        # 生成Liquidsoap播放列表（.liq格式，包含完整混音逻辑）
        if output_txt:
            liq_file = generator.generate_playlist(
                episode_id=episode_id,
                target_bpm=target_bpm,
                target_duration_minutes=duration,
                max_vocal_tracks=max_vocals,
            )
            outputs.append(("Liquidsoap混音脚本", liq_file))
        
        # 生成CSV播放列表（McPOS内部使用）
        if output_csv:
            csv_file = generator.generate_playlist_csv(
                episode_id=episode_id,
                target_bpm=target_bpm,
                target_duration_minutes=duration,
                max_vocal_tracks=max_vocals,
            )
            outputs.append(("CSV播放列表", csv_file))
        
        typer.echo(f"\n✅ 播放列表已生成: {episode_id}")
        for name, path in outputs:
            typer.echo(f"   {name}: {path}")
        
    except Exception as e:
        typer.echo(f"❌ 生成失败: {e}")
        raise typer.Exit(1)


@app.command()
def rbr_mix_episode(
    episode_id: str = typer.Argument(..., help="集数ID，如 rbr_20250101"),
    csv_path: Optional[str] = typer.Option(None, "--csv", help="CSV播放列表路径（默认从setlists目录读取）"),
    output_path: Optional[str] = typer.Option(None, "--output", "-o", help="输出混音文件路径"),
):
    """
    RBR频道：混音一期节目
    
    从CSV播放列表读取歌曲，使用AutoRemixEngine进行智能混音
    
    示例:
    - 混音rbr_20250101: python3 -m mcpos.cli.main rbr-mix-episode rbr_20250101
    """
    from ..config import get_config
    from ..adapters.broadcast.rbr_mix_from_csv import mix_rbr_episode_from_csv
    
    config = get_config()
    
    # 确定CSV路径
    if csv_path:
        csv_file = Path(csv_path)
    else:
        csv_file = config.channels_root / "rbr" / "setlists" / f"{episode_id}.csv"
    
    if not csv_file.exists():
        typer.echo(f"❌ 播放列表文件不存在: {csv_file}")
        typer.echo(f"   请先运行: python3 -m mcpos.cli.main rbr-build-playlist {episode_id}")
        raise typer.Exit(1)
    
    # 确定输出路径
    output_file = None
    if output_path:
        output_file = Path(output_path)
    
    try:
        result_path = mix_rbr_episode_from_csv(
            csv_path=csv_file,
            output_path=output_file,
            episode_id=episode_id,
        )
        typer.echo(f"\n✅ 混音完成: {episode_id}")
        typer.echo(f"   输出文件: {result_path}")
    except Exception as e:
        typer.echo(f"❌ 混音失败: {e}")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def rbr_generate_schedule(
    start_date: str = typer.Argument("20251201", help="起始日期（YYYYMMDD）"),
    start_episode: str = typer.Option("rbr_20251201", "--start-episode", help="起始集数ID"),
    initial_duration: float = typer.Option(30.0, "--initial-duration", help="初始时长（分钟）"),
    duration_step: float = typer.Option(15.0, "--duration-step", help="时长步长（分钟）"),
    max_duration_hours: float = typer.Option(6.0, "--max-duration", help="最大时长（小时）"),
    center_bpm: float = typer.Option(175.0, "--center-bpm", help="中心BPM"),
    bpm_min: float = typer.Option(150.0, "--bpm-min", help="最小BPM"),
    bpm_max: float = typer.Option(200.0, "--bpm-max", help="最大BPM"),
    generate_playlists: bool = typer.Option(True, "--generate/--no-generate", help="是否生成播放列表"),
    output_csv: str = typer.Option("rbr_schedule.csv", "--output", "-o", help="输出CSV文件路径"),
):
    """
    生成RBR频道排期
    
    使用BPM盘旋算法（以175为中心，向外扩展）和时长梯度生成多期节目排期。
    
    示例:
    - 生成从20251201开始的排期:
      python3 -m mcpos.cli.main rbr-generate-schedule 20251201
    """
    from ..config import get_config
    from ..adapters.broadcast.rbr_config import RBRBroadcastConfig
    from ..adapters.broadcast.scheduler import BRBScheduler
    
    config_obj = get_config()
    config = RBRBroadcastConfig(channels_root=config_obj.channels_root)
    scheduler = BRBScheduler(config)
    
    typer.echo("=" * 60)
    typer.echo("🎵 RBR频道排期生成器")
    typer.echo("=" * 60)
    typer.echo()
    typer.echo(f"起始日期: {start_date}")
    typer.echo(f"起始集数: {start_episode}")
    typer.echo(f"时长梯度: {initial_duration}分钟开始，每{duration_step}分钟递增，最多{max_duration_hours}小时")
    typer.echo(f"BPM范围: {bpm_min}-{bpm_max}，中心: {center_bpm}")
    typer.echo()
    
    # 生成排期
    typer.echo("🚀 开始生成排期...")
    schedules = scheduler.generate_schedule(
        start_date=start_date,
        start_episode_id=start_episode,
        initial_duration=initial_duration,
        duration_step=duration_step,
        max_duration_hours=max_duration_hours,
        center_bpm=center_bpm,
        bpm_range=(bpm_min, bpm_max),
        generate_playlists=generate_playlists,
    )
    
    typer.echo(f"✅ 生成了 {len(schedules)} 期节目")
    typer.echo()
    
    # 分析统计
    typer.echo("📊 使用统计:")
    stats = scheduler.analyze_usage_statistics(schedules)
    typer.echo(f"   总曲目数: {stats['total_tracks']}")
    typer.echo(f"   已使用: {stats['used_tracks']} ({stats['usage_rate']:.1f}%)")
    typer.echo(f"   未使用: {stats['unused_tracks']}")
    typer.echo(f"   平均每首使用次数: {stats['avg_usage_per_track']:.2f}")
    typer.echo()
    
    # 估算需要的曲目数
    typer.echo("📈 曲目需求估算:")
    estimate = scheduler.estimate_required_tracks(schedules, target_repeat_interval_days=30)
    typer.echo(f"   总时长: {estimate['total_minutes']:.0f} 分钟 ({estimate['total_minutes']/60:.1f} 小时)")
    typer.echo(f"   总播放次数: {estimate['total_track_plays']:.0f} 次")
    typer.echo(f"   时间跨度: {estimate['days_span']} 天")
    typer.echo(f"   每个周期需要: {estimate['required_tracks_per_cycle']:.0f} 首")
    typer.echo(f"   当前曲目数: {estimate['current_tracks']}")
    typer.echo(f"   需要增加: {estimate['needed_tracks']:.0f} 首")
    typer.echo(f"   每月需要增加: {estimate['monthly_needed_tracks']:.0f} 首（30天不重复）")
    typer.echo()
    
    # 保存CSV
    import csv
    output_path = Path(output_csv)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'episode_id', 'date', 'target_bpm', 'duration_minutes', 
            'track_count', 'unique_tracks', 'playlist_file'
        ])
        writer.writeheader()
        for s in schedules:
            writer.writerow({
                'episode_id': s.episode_id,
                'date': s.date.strftime('%Y-%m-%d'),
                'target_bpm': s.target_bpm,
                'duration_minutes': s.duration_minutes,
                'track_count': s.track_count,
                'unique_tracks': s.unique_tracks,
                'playlist_file': str(s.playlist_file) if s.playlist_file else '',
            })
    
    typer.echo(f"💾 排期已保存到: {output_path}")
    typer.echo()
    
    # 显示前10期
    typer.echo("📋 前10期节目:")
    typer.echo("-" * 60)
    for s in schedules[:10]:
        typer.echo(f"  {s.episode_id}: {s.date.strftime('%Y-%m-%d')} | "
                  f"BPM {s.target_bpm:.0f} | {s.duration_minutes:.0f}分钟 | "
                  f"{s.track_count}首")
    
    if len(schedules) > 10:
        typer.echo(f"  ... 还有 {len(schedules) - 10} 期")
    
    typer.echo()
    typer.echo("💡 查看完整排期:")
    typer.echo(f"   cat {output_path}")


@app.command()
def scan_library(
    channel_id: str = typer.Argument(..., help="频道 ID，如 rbr"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出CSV文件路径（默认：channels/{channel_id}/library/songs_library_management/library_scan.csv）"),
    use_ml_genre: bool = typer.Option(False, "--ml-genre", help="使用机器学习进行风格检测（需要Essentia）"),
    force: bool = typer.Option(False, "--force", help="强制重新扫描所有文件（忽略已有结果）"),
    enhanced: bool = typer.Option(True, "--enhanced/--basic", help="使用增强版扫描（包含更多参数，支持幂等性）"),
):
    """
    全库扫描：分析所有音频文件并生成CSV报告
    
    功能：
    - 提取元数据（歌名、艺术家、合作艺术家、时长）
    - 分析音频特征（BPM、调值、人声、风格）
    - 增强版：能量等级、情绪向量、结构标记、响度、频谱特征等
    - 支持幂等性：只处理新文件或更新的文件
    
    输出字段（基础版）：
    - filename, title, artist, collab_artist, duration_seconds, duration_minutes
    - bpm, key, has_vocals, genre
    
    输出字段（增强版，额外）：
    - energy_level, mood_vector, structure_markers
    - loudness_lufs, peak_dbfs, spectral_profile
    - camelot_key, file_hash, scan_timestamp
    
    使用示例：
    - 基本扫描：python3 -m mcpos.cli.main scan-library rbr
    - 强制重新扫描：python3 -m mcpos.cli.main scan-library rbr --force
    - 使用基础版：python3 -m mcpos.cli.main scan-library rbr --basic
    
    依赖：
    - librosa, numpy（用于BPM、调值、人声检测）
    - essentia（可选，用于ML风格检测）
    """
    from ..config import get_config
    
    config = get_config()
    songs_dir = config.channels_root / channel_id / "library" / "songs"
    
    if not songs_dir.exists():
        typer.echo(f"❌ 歌曲目录不存在: {songs_dir}")
        raise typer.Exit(1)
    
    if output:
        output_csv = Path(output)
    else:
        output_csv = config.channels_root / channel_id / "library" / "songs_library_management" / "library_scan.csv"
    
    try:
        if enhanced:
            from ..adapters.enhanced_library_scanner import scan_library_enhanced
            scan_library_enhanced(
                songs_dir=songs_dir,
                output_csv=output_csv,
                force_rescan=force,
            )
        else:
            from ..adapters.library_scanner import scan_library
            scan_library(
                songs_dir=songs_dir,
                output_csv=output_csv,
                use_ml_genre=use_ml_genre,
            )
        typer.echo(f"\n✅ 扫描完成: {channel_id}")
        typer.echo(f"   结果已保存到: {output_csv}")
    except Exception as e:
        typer.echo(f"❌ 扫描失败: {e}")
        raise typer.Exit(1)


@app.command()
def rbr_normalize_bpm(
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="预览模式（不实际修改）"),
    from_csv: bool = typer.Option(False, "--from-csv", help="从CSV文件读取（如果数据库为空）"),
    report_file: Optional[str] = typer.Option(None, "--report", "-r", help="报告文件路径"),
):
    """
    RBR频道BPM标准化
    
    将音乐制作语境的BPM转换为跑步语境的BPM：
    - 低于100的BPM乘以2（如65 → 130）
    - 100-120的BPM乘以2（如110 → 220）
    - 120-240的BPM保持不变（如140 → 140）
    - 超过240的BPM除以2（如250 → 125）
    
    示例:
    - 预览修改: python3 -m mcpos.cli.main rbr-normalize-bpm --dry-run
    - 应用修改: python3 -m mcpos.cli.main rbr-normalize-bpm --apply
    """
    from ..config import get_config
    from ..adapters.broadcast.rbr_config import RBRBroadcastConfig
    from ..adapters.broadcast.bpm_normalizer import BPMNormalizer
    
    config_obj = get_config()
    config = RBRBroadcastConfig(channels_root=config_obj.channels_root)
    normalizer = BPMNormalizer(config)
    
    typer.echo("=" * 60)
    typer.echo("🎵 RBR频道BPM标准化")
    typer.echo("=" * 60)
    typer.echo()
    
    if dry_run:
        typer.echo("📋 预览模式（不会实际修改数据）")
    else:
        typer.echo("⚠️  应用模式（将修改数据库和ID3标签）")
    typer.echo()
    
    # 分析当前分布
    typer.echo("📊 分析当前BPM分布...")
    
    # 如果数据库为空，尝试从CSV读取
    if from_csv:
        csv_path = config.channels_root / "rbr" / "library" / "songs_library_management" / "library_scan.csv"
        if csv_path.exists():
            typer.echo(f"   从CSV文件读取: {csv_path}")
            distribution = normalizer.analyze_bpm_distribution_from_csv()
        else:
            typer.echo("❌ CSV文件不存在")
            raise typer.Exit(1)
    else:
        distribution = normalizer.analyze_bpm_distribution()
        if distribution['total'] == 0:
            typer.echo("❌ 数据库中没有BPM数据")
            typer.echo("   请使用 --from-csv 从CSV文件读取")
            typer.echo("   或先导入数据库: python3 mcpos/adapters/broadcast/import_csv_to_db.py")
            raise typer.Exit(1)
    
    typer.echo(f"   总曲目数: {distribution['total']}")
    typer.echo(f"   BPM范围: {distribution['min_bpm']:.1f} - {distribution['max_bpm']:.1f}")
    typer.echo(f"   平均BPM: {distribution['avg_bpm']:.1f}")
    typer.echo()
    typer.echo("   原始分布:")
    for range_name, count in distribution['original_distribution'].items():
        percentage = count / distribution['total'] * 100
        typer.echo(f"     {range_name:10s}: {count:4d} ({percentage:5.1f}%)")
    typer.echo()
    
    # 执行标准化
    typer.echo("🔄 执行BPM标准化...")
    stats = normalizer.normalize_all_tracks(dry_run=dry_run, from_csv=from_csv)
    
    typer.echo()
    typer.echo("=" * 60)
    typer.echo("✅ 标准化完成")
    typer.echo("=" * 60)
    typer.echo(f"   总曲目数: {stats['total']}")
    typer.echo(f"   已修改: {stats['modified']} ({stats['modified']/stats['total']*100:.1f}%)")
    typer.echo(f"   未修改: {stats['unchanged']} ({stats['unchanged']/stats['total']*100:.1f}%)")
    typer.echo(f"   错误: {stats['errors']}")
    typer.echo()
    
    # 显示标准化后的分布
    if not dry_run:
        typer.echo("📊 标准化后的BPM分布:")
        if from_csv:
            new_distribution = normalizer.analyze_bpm_distribution_from_csv()
        else:
            new_distribution = normalizer.analyze_bpm_distribution()
        for range_name, count in new_distribution['normalized_distribution'].items():
            percentage = count / new_distribution['total'] * 100
            typer.echo(f"     {range_name:10s}: {count:4d} ({percentage:5.1f}%)")
        typer.echo()
        typer.echo(f"   标准化后范围: {new_distribution['normalized_min']:.1f} - {new_distribution['normalized_max']:.1f}")
        typer.echo(f"   标准化后平均: {new_distribution['normalized_avg']:.1f}")
        typer.echo()
    
    # 生成报告
    if report_file:
        report_path = Path(report_file)
    else:
        report_path = config.channels_root / "rbr" / "library" / "songs_library_management" / "bpm_normalization_report.txt"
    
    report_text = normalizer.generate_report(stats, report_path)
    
    if stats['changes']:
        typer.echo("📋 修改详情（前10条）:")
        typer.echo("-" * 60)
        for i, change in enumerate(stats['changes'][:10], 1):
            file_path_str = change.get('file_path', '')
            if file_path_str:
                filename = Path(file_path_str).name
            else:
                filename = change.get('title', 'Unknown')
            typer.echo(f"  {i:2d}. {filename}")
            if change.get('title'):
                typer.echo(f"      标题: {change['title']}")
            if change.get('artist'):
                typer.echo(f"      艺术家: {change['artist']}")
            typer.echo(f"      BPM: {change['original_bpm']:.1f} → {change['normalized_bpm']:.1f}")
        
        if len(stats['changes']) > 10:
            typer.echo(f"  ... 还有 {len(stats['changes']) - 10} 条修改")
        typer.echo()
    
    typer.echo(f"💾 报告已保存到: {report_path}")
    typer.echo()
    
    if dry_run:
        typer.echo("💡 要应用这些修改，请运行:")
        typer.echo("   python3 -m mcpos.cli.main rbr-normalize-bpm --apply")


@app.command()
def sample_titles(
    image_filename: str = typer.Argument(..., help="封面文件名或路径"),
    count: int = typer.Option(10, "--count", "-n", help="输出标题数量（默认 10）"),
    channel_id: str = typer.Option("kat", "--channel", "-c", help="频道 ID（默认 kat）"),
    episode_date: Optional[str] = typer.Option(None, "--date", "-d", help="日期（YYYYMMDD 或 YYYY-MM-DD）"),
    theme_color: Optional[str] = typer.Option(None, "--color", help="主题色十六进制（如 #AABBCC）"),
):
    """
    测试用：一次输出多条标题（默认 10 条）
    """
    import asyncio
    import re
    from ..adapters.ai_title_generator import EpisodeBudget, generate_album_title
    from ..adapters.color_extractor import extract_theme_color

    def _parse_hex_color(value: str) -> Optional[tuple[int, int, int]]:
        v = value.strip().lstrip("#")
        if len(v) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", v):
            return None
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)

    theme_rgb = None
    if theme_color:
        theme_rgb = _parse_hex_color(theme_color)
        if theme_rgb is None:
            typer.echo("❌ color 格式无效，请使用 #RRGGBB")
            raise typer.Exit(1)
    else:
        try:
            image_path = Path(image_filename)
            if image_path.exists():
                theme_rgb = extract_theme_color(image_path)
        except Exception:
            theme_rgb = None

    if theme_rgb is None:
        theme_rgb = (0, 0, 0)

    # NOTE: This command is intentionally offline-only to avoid accidental API spend.
    api_key = None

    async def _run() -> list[str]:
        titles: list[str] = []
        for i in range(count):
            budget = EpisodeBudget(max_calls=2)
            title = await generate_album_title(
                track_titles=[],
                image_filename=image_filename,
                theme_color_rgb=theme_rgb,
                episode_date=episode_date,
                api_key=api_key,
                channel_id=channel_id,
                budget=budget,
                seed_salt=f"sample-{i+1}",
            )
            titles.append(title)
        return titles

    titles = asyncio.run(_run())
    typer.echo(f"🎯 输出 {len(titles)} 个标题:")
    for idx, title in enumerate(titles, 1):
        typer.echo(f"{idx:02d}. {title}")


if __name__ == "__main__":
    app()
