#!/usr/bin/env python3
# coding: utf-8
"""
KAT Records Studio - 命令行入口

统一的命令行接口，支持所有功能

用法：
    python scripts/kat_cli.py <命令> [参数...]
    kat <命令> [参数...]  # 如果设置了alias

示例：
    python scripts/kat_cli.py generate --id 20251101
    python scripts/kat_cli.py schedule create --episodes 15
    python scripts/kat_cli.py help
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Add paths for importing upload modules
sys.path.insert(0, str(REPO_ROOT / "scripts" / "uploader"))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))


def run_subprocess(cmd: list[str], description: str = ""):
    """运行子进程命令"""
    if description:
        print(f"🔧 {description}...")
        print()
    
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            check=False,
        )
        return result.returncode
    except KeyboardInterrupt:
        print("\n\n❌ 已取消")
        return 130
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1


def cmd_generate(args):
    """生成视频命令"""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "local_picker" / "create_mixtape.py"),
        "--font_name", "Lora-Regular",
    ]
    
    if args.episode_id:
        cmd.extend(["--episode-id", args.episode_id])
    
    if args.seed:
        cmd.extend(["--seed", str(args.seed)])
    
    if args.no_remix:
        cmd.append("--no-remix")
    
    if args.no_video:
        cmd.append("--no-video")
    
    return run_subprocess(cmd, "生成视频内容")


def cmd_schedule(args):
    """排播表命令"""
    if args.action == "create":
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "create_schedule_with_confirmation.py"),
            "--episodes", str(args.episodes),
        ]
        if args.start_date:
            cmd.extend(["--start-date", args.start_date])
        if args.interval:
            cmd.extend(["--interval", str(args.interval)])
        if args.yes:
            cmd.append("--yes")
        if args.force:
            cmd.append("--force")
        
        return run_subprocess(cmd, f"创建排播表（{args.episodes}期）")
    
    elif args.action == "show":
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "show_schedule.py"),
        ]
        if args.pending:
            cmd.append("--pending")
        if args.id:
            cmd.extend(["--id", args.id])
        
        return run_subprocess(cmd, "显示排播表")
    
    elif args.action == "generate":
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "generate_full_schedule.py"),
            "--format", args.format,
            "--update-schedule",
        ]
        if args.output:
            cmd.extend(["--output", args.output])
        
        return run_subprocess(cmd, "生成完整排播表（标题+曲目）")
    
    elif args.action == "watch":
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "watch_schedule_status.py"),
        ]
        if args.watch:
            cmd.append("--watch")
        if args.interval:
            cmd.extend(["--interval", str(args.interval)])
        
        return run_subprocess(cmd, "监视排播表状态")
    
    else:
        print(f"❌ 未知的排播表操作: {args.action}")
        return 1


def cmd_batch(args):
    """批量生成命令"""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "local_picker" / "batch_generate_videos.py"),
        str(args.count),
    ]
    
    return run_subprocess(cmd, f"批量生成{args.count}期视频")


def cmd_upload(args):
    """上传视频到YouTube命令"""
    try:
        # Import upload functions
        from upload_to_youtube import (
            load_config,
            get_authenticated_service,
            upload_video,
            read_metadata_files,
            check_already_uploaded,
            update_schedule_record,
            log_event,
            YouTubeUploadError,
            REPO_ROOT as UPLOAD_REPO_ROOT
        )
        
        episode_id = args.episode
        
        # Load configuration
        config = load_config()
        if args.privacy:
            config["privacy_status"] = args.privacy
        if args.schedule:
            config["schedule"] = True
        if getattr(args, 'playlist_id', None):
            config["playlist_id"] = args.playlist_id
        
        # Auto-detect video file if not provided
        output_dir = REPO_ROOT / "output"
        if args.video:
            video_file = Path(args.video)
        else:
            # Try to find video file automatically
            video_file = output_dir / f"{episode_id}_youtube.mp4"
            
            # If not found, try in final directories
            if not video_file.exists():
                final_dirs = list(output_dir.glob(f"{episode_id[:8]}-*"))
                for final_dir in final_dirs:
                    candidate = final_dir / f"{episode_id}_youtube.mp4"
                    if candidate.exists():
                        video_file = candidate
                        break
            
            # If still not found, search recursively
            if not video_file.exists():
                all_videos = list(output_dir.rglob(f"{episode_id}_youtube.mp4"))
                if all_videos:
                    video_file = all_videos[0]
        
        # Validate video file
        if not video_file.exists():
            print(f'\n❌ 视频文件未找到: {video_file}')
            print(f'💡 请确保视频文件存在，或使用 --video 参数指定路径\n')
            return 1
        
        # Check if already uploaded (idempotent)
        existing_video_id = check_already_uploaded(episode_id)
        if existing_video_id and not args.force:
            print(f'\n✅ 期数 {episode_id} 已上传')
            print(f'📺 视频: https://www.youtube.com/watch?v={existing_video_id}')
            print(f'💡 使用 --force 强制重新上传\n')
            return 0
        
        # Read metadata
        metadata = read_metadata_files(
            episode_id,
            video_file,
            args.title_file,
            args.desc_file
        )
        
        # Use defaults if metadata not found
        if not metadata["title"]:
            metadata["title"] = f"Kat Records Lo-Fi Mix - {episode_id}"
            print(f'⚠️  未找到标题文件，使用默认标题')
        
        if not metadata["description"]:
            metadata["description"] = "Kat Records - Lo-Fi Radio Mix"
            print(f'⚠️  未找到描述文件，使用默认描述')
        
        # Show upload info
        print(f'\n📤 准备上传期数 {episode_id} 到 YouTube')
        print(f'   📹 视频: {video_file.name}')
        print(f'   📝 标题: {metadata["title"][:60]}{"..." if len(metadata["title"]) > 60 else ""}')
        if metadata["subtitle_path"]:
            print(f'   📄 字幕: {Path(metadata["subtitle_path"]).name}')
        if metadata["thumbnail_path"]:
            print(f'   🖼️  缩略图: {Path(metadata["thumbnail_path"]).name}')
        if config.get("playlist_id"):
            print(f'   📋 播放列表: {config["playlist_id"]}')
        print()
        
        # Log upload start
        log_event("upload", episode_id, "started", video_file=str(video_file))
        
        try:
            # Get authenticated service
            youtube = get_authenticated_service(config)
            
            # Upload video
            result = upload_video(
                youtube=youtube,
                video_file=video_file,
                title=metadata["title"],
                description=metadata["description"],
                config=config,
                subtitle_path=Path(metadata["subtitle_path"]) if metadata["subtitle_path"] else None,
                thumbnail_path=Path(metadata["thumbnail_path"]) if metadata["thumbnail_path"] else None,
                episode_id=episode_id,
                max_retries=5
            )
            
            # Update schedule_master.json
            update_schedule_record(episode_id, result["video_id"], result["video_url"])
            
            # Trigger event bus
            try:
                from core.event_bus import get_event_bus
                event_bus = get_event_bus()
                event_bus.emit_upload_started(episode_id)
                event_bus.emit_upload_completed(episode_id, result["video_id"], result["video_url"])
            except Exception:
                pass  # Event bus optional
            
            # Write upload result JSON
            output_dir = video_file.parent
            result_file = output_dir / f"{episode_id}_youtube_upload.json"
            import json
            result_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
            
            # Show success message
            print(f'\n✅ 上传成功！')
            print(f'   📺 视频ID: {result["video_id"]}')
            print(f'   🔗 URL: {result["video_url"]}')
            if result.get("playlist_id"):
                print(f'   📋 已添加到播放列表: {result["playlist_id"]}')
            print(f'   ⏱️  耗时: {result.get("duration_seconds", 0):.1f} 秒')
            print()
            
            # Log success
            log_event("upload", episode_id, "completed", **result)
            
            return 0
            
        except YouTubeUploadError as e:
            error_msg = str(e)
            log_event("upload", episode_id, "error", error=error_msg, exception_type=type(e).__name__)
            
            # Provide friendly error messages
            if "403" in error_msg or "accessNotConfigured" in error_msg:
                print(f'\n❌ 上传失败：YouTube Data API v3 未启用')
                print(f'\n🔧 解决步骤：')
                print(f'   1. 访问 Google Cloud Console：')
                print(f'      https://console.cloud.google.com/')
                print(f'   2. 转到 "APIs & Services" → "Library"')
                print(f'   3. 搜索并启用 "YouTube Data API v3"')
                print(f'   4. 等待 2-5 分钟让更改生效')
                print(f'   5. 重新运行上传命令')
                print(f'\n💡 或运行检查脚本：')
                print(f'   .venv/bin/python3 scripts/check_youtube_api.py\n')
            elif "401" in error_msg or "unauthorized" in error_msg.lower():
                print(f'\n⚠️  认证失败：需要重新授权')
                print(f'💡 下次运行上传时会自动触发授权流程\n')
            else:
                print(f'\n❌ 上传失败：{error_msg}\n')
            
            return 1
            
        except Exception as e:
            error_msg = str(e)
            log_event("upload", episode_id, "error", error=error_msg, exception_type=type(e).__name__)
            print(f'\n❌ 上传失败：{error_msg}\n')
            return 1
            
    except ImportError as e:
        print(f'\n❌ 导入错误：{e}')
        print(f'💡 请确保所有依赖已正确安装\n')
        return 1
    except KeyboardInterrupt:
        print('\n\n❌ 已取消操作')
        return 130
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f'\n❌ 文件操作错误：{type(e).__name__}: {e}')
        return 1
    except Exception as e:
        print(f'\n❌ 错误：{type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return 1


def cmd_reset(args):
    """重置命令"""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "reset_schedule.py"),
    ]
    
    if args.schedule_only:
        cmd.append("--schedule-only")
    elif args.include_output:
        cmd.append("--include-output")
    elif args.full_reset:
        cmd.append("--full-reset")
    
    if args.yes:
        cmd.append("--yes")
    
    return run_subprocess(cmd, "重置排播表和输出文件")


def cmd_help(args):
    """帮助命令"""
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "show_help.py"),
    ]
    
    if args.quick:
        cmd.append("--quick")
    elif args.category:
        cmd.extend(["--category", args.category])
    elif args.command:
        cmd.extend(["--command", args.command])
    elif args.docs:
        cmd.append("--docs")
    
    return run_subprocess(cmd)


def cmd_api(args):
    """API相关命令"""
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
    
    if args.action == "check":
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "check_api_status.py"),
        ]
        if args.test:
            cmd.append("--test")
        return run_subprocess(cmd, "检查API状态")
    
    elif args.action == "setup":
        # 使用新的配置向导（configure_api.py）
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "local_picker" / "configure_api.py"),
        ]
        return run_subprocess(cmd, "配置API密钥")


def cmd_web(args):
    """启动Web控制台命令"""
    try:
        # 尝试导入配置
        try:
            from configuration import AppConfig
            config = AppConfig.load()
            web_config = config.web
            host = args.host or web_config.host
            port = args.port or web_config.port
            auto_open = args.open if args.open is not None else web_config.auto_open_browser
        except Exception:
            # 如果配置不可用，使用参数或默认值
            host = args.host or "127.0.0.1"
            port = args.port or 8080
            auto_open = args.open if args.open is not None else True
        
        # 检查是否使用 Docker 模式
        if args.docker:
            return cmd_web_docker(args)
        
        # 检查是否使用完整版 web (kat_rec_web)
        if args.full:
            return cmd_web_full(args)
        
        # 默认启动简单的 dashboard 服务器
        return cmd_web_dashboard(host, port, auto_open, args.reload)
        
    except KeyboardInterrupt:
        print("\n\n✅ Web服务器已停止")
        return 0
    except (ImportError, ModuleNotFoundError) as e:
        print(f'\n❌ 缺少依赖：{e}')
        return 1
    except Exception as e:
        print(f'\n❌ 启动Web服务器失败：{type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return 1


def cmd_web_dashboard(host: str, port: int, auto_open: bool, reload: bool) -> int:
    """启动简单的 Dashboard 服务器"""
    try:
        import uvicorn
        
        # 检查 dashboard_server 是否存在
        dashboard_server = REPO_ROOT / "web" / "dashboard" / "dashboard_server.py"
        if not dashboard_server.exists():
            print(f'\n❌ Dashboard 服务器未找到: {dashboard_server}')
            return 1
        
        # 自动打开浏览器
        if auto_open:
            import webbrowser
            import threading
            url = f"http://{host}:{port}"
            
            def open_browser():
                import time
                time.sleep(1.5)  # 等待服务器启动
                webbrowser.open(url)
            
            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()
        
        print(f'\n🚀 启动 Web 控制台...')
        print(f'   🌐 地址: http://{host}:{port}')
        print(f'   📊 仪表板: http://{host}:{port}/')
        if auto_open:
            print(f'   🔗 浏览器将自动打开')
        print(f'\n💡 按 Ctrl+C 停止服务器\n')
        
        # 动态导入 dashboard_server 模块
        import importlib.util
        spec = importlib.util.spec_from_file_location("dashboard_server", dashboard_server)
        dashboard_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dashboard_module)
        
        # 运行服务器
        uvicorn.run(
            dashboard_module.app,
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
        
        return 0
        
    except ImportError as e:
        print(f'\n❌ 缺少依赖：{e}')
        print(f'\n💡 正在尝试自动安装依赖...')
        
        # 尝试自动安装
        try:
            import subprocess
            install_cmd = [sys.executable, "-m", "pip", "install", "fastapi", "uvicorn[standard]"]
            result = subprocess.run(
                install_cmd,
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f'✅ 依赖安装成功！')
                print(f'\n正在重新启动 Web 服务器...\n')
                # 重新尝试启动
                return cmd_web_dashboard(host, port, auto_open, reload)
            else:
                print(f'❌ 自动安装失败')
                print(f'\n请手动运行以下命令安装依赖：')
                print(f'  pip install fastapi uvicorn[standard]')
                print(f'\n或安装所有依赖：')
                print(f'  pip install -r requirements.txt')
                return 1
        except Exception as install_error:
            print(f'❌ 自动安装出错：{install_error}')
            print(f'\n请手动运行以下命令安装依赖：')
            print(f'  pip install fastapi uvicorn[standard]')
            return 1
    except Exception as e:
        print(f'\n❌ 启动失败：{e}')
        import traceback
        traceback.print_exc()
        return 1


def cmd_web_full(args) -> int:
    """启动完整的 kat_rec_web (需要 Docker)"""
    kat_rec_web_dir = REPO_ROOT / "kat_rec_web"
    docker_compose_file = kat_rec_web_dir / "docker-compose.yml"
    
    if not docker_compose_file.exists():
        print(f'\n❌ kat_rec_web 未找到: {docker_compose_file}')
        print(f'💡 完整版 Web 控制台需要 Docker')
        return 1
    
    try:
        import subprocess
        
        print(f'\n🐳 启动完整版 Web 控制台 (Docker)...')
        print(f'   目录: {kat_rec_web_dir}')
        
        cmd = ["docker-compose", "up"]
        if args.detach:
            cmd.append("-d")
        
        result = subprocess.run(
            cmd,
            cwd=kat_rec_web_dir,
            check=False
        )
        
        if result.returncode == 0:
            print(f'\n✅ Web 控制台已启动')
            print(f'   🌐 前端: http://localhost:3000')
            print(f'   🔧 后端: http://localhost:8000')
            print(f'   📚 API 文档: http://localhost:8000/docs')
        else:
            print(f'\n❌ Docker Compose 启动失败')
            print(f'💡 请确保 Docker 已安装并运行')
        
        return result.returncode
        
    except FileNotFoundError:
        print(f'\n❌ Docker Compose 未找到')
        print(f'💡 请安装 Docker 和 Docker Compose')
        return 1
    except Exception as e:
        print(f'\n❌ 错误：{e}')
        return 1


def cmd_web_docker(args) -> int:
    """使用 Docker 启动 Dashboard (简化版)"""
    print(f'\n🐳 Docker 模式暂不支持简单 Dashboard')
    print(f'💡 使用 --full 启动完整的 kat_rec_web')
    return cmd_web_full(args)


def main():
    parser = argparse.ArgumentParser(
        description="KAT Records Studio - 命令行入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  kat generate --id 20251101              # 生成指定期数
  kat schedule create --episodes 15       # 创建排播表
  kat schedule show                       # 显示排播表
  kat batch --count 10                   # 批量生成10期
  kat upload --episode 20251101           # 上传视频
  kat web                                 # 启动Web控制台
  kat web --port 9000                    # 在自定义端口启动
  kat web --full                          # 启动完整版Web应用(Docker)
  kat help                                # 显示帮助
  kat help --quick                        # 快速参考
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # generate 命令
    parser_generate = subparsers.add_parser("generate", help="生成视频内容")
    parser_generate.add_argument("--id", "--episode-id", dest="episode_id", help="期数ID（YYYYMMDD格式）")
    parser_generate.add_argument("--seed", type=int, help="随机种子")
    parser_generate.add_argument("--no-remix", action="store_true", help="跳过混音")
    parser_generate.add_argument("--no-video", action="store_true", help="跳过视频")
    parser_generate.set_defaults(func=cmd_generate)
    
    # schedule 命令
    parser_schedule = subparsers.add_parser("schedule", help="排播表管理")
    schedule_subparsers = parser_schedule.add_subparsers(dest="action", help="排播表操作")
    
    # schedule create
    parser_schedule_create = schedule_subparsers.add_parser("create", help="创建排播表")
    parser_schedule_create.add_argument("--episodes", type=int, required=True, help="期数")
    parser_schedule_create.add_argument("--start-date", help="起始日期（YYYY-MM-DD）")
    parser_schedule_create.add_argument("--interval", type=int, default=2, help="排播间隔（天）")
    parser_schedule_create.add_argument("--yes", action="store_true", help="跳过确认")
    parser_schedule_create.add_argument("--force", action="store_true", help="强制覆盖")
    parser_schedule_create.set_defaults(func=cmd_schedule)
    
    # schedule show
    parser_schedule_show = schedule_subparsers.add_parser("show", help="显示排播表")
    parser_schedule_show.add_argument("--pending", action="store_true", help="只显示pending状态")
    parser_schedule_show.add_argument("--id", help="显示指定ID详情")
    parser_schedule_show.set_defaults(func=cmd_schedule)
    
    # schedule generate
    parser_schedule_generate = schedule_subparsers.add_parser("generate", help="生成完整排播表")
    parser_schedule_generate.add_argument("--format", default="markdown", choices=["markdown", "csv", "both"])
    parser_schedule_generate.add_argument("--output", help="输出文件路径")
    parser_schedule_generate.set_defaults(func=cmd_schedule)
    
    # schedule watch
    parser_schedule_watch = schedule_subparsers.add_parser("watch", help="监视排播表状态")
    parser_schedule_watch.add_argument("--watch", action="store_true", help="持续监视模式")
    parser_schedule_watch.add_argument("--interval", type=int, default=10, help="监视间隔（秒）")
    parser_schedule_watch.set_defaults(func=cmd_schedule)
    
    # batch 命令
    parser_batch = subparsers.add_parser("batch", help="批量生成")
    parser_batch.add_argument("--count", "-n", type=int, required=True, help="生成期数")
    parser_batch.set_defaults(func=cmd_batch)
    
    # upload 命令
    parser_upload = subparsers.add_parser("upload", help="上传视频到YouTube")
    parser_upload.add_argument("--episode", required=True, help="期数ID (YYYYMMDD格式)")
    parser_upload.add_argument("--video", type=Path, help="视频文件路径（自动检测如果未指定）")
    parser_upload.add_argument("--title-file", type=Path, help="标题文件路径（自动检测如果未指定）")
    parser_upload.add_argument("--desc-file", type=Path, help="描述文件路径（自动检测如果未指定）")
    parser_upload.add_argument("--privacy", choices=["private", "unlisted", "public"], help="视频可见性（覆盖配置）")
    parser_upload.add_argument("--force", action="store_true", help="强制上传（即使已上传）")
    parser_upload.add_argument("--schedule", action="store_true", help="计划上传（设置为期数日期的9:00 AM发布）")
    parser_upload.add_argument("--playlist-id", dest="playlist_id", help="播放列表ID（覆盖配置中的playlist_id）")
    parser_upload.set_defaults(func=cmd_upload)
    
    # reset 命令
    parser_reset = subparsers.add_parser("reset", help="重置排播表和输出文件")
    reset_group = parser_reset.add_mutually_exclusive_group(required=True)
    reset_group.add_argument("--schedule-only", action="store_true", help="只清除排播表")
    reset_group.add_argument("--include-output", action="store_true", help="清除排播表 + 期数文件夹")
    reset_group.add_argument("--full-reset", action="store_true", help="完全清除（排播表 + 所有output）")
    parser_reset.add_argument("--yes", action="store_true", help="跳过确认")
    parser_reset.set_defaults(func=cmd_reset)
    
    # help 命令
    parser_help = subparsers.add_parser("help", help="显示帮助")
    parser_help.add_argument("--quick", action="store_true", help="快速参考")
    parser_help.add_argument("--category", help="按类别查看")
    parser_help.add_argument("--command", help="查看命令详情")
    parser_help.add_argument("--docs", action="store_true", help="文档索引")
    parser_help.set_defaults(func=cmd_help)
    
    # api 命令
    parser_api = subparsers.add_parser("api", help="API管理")
    api_subparsers = parser_api.add_subparsers(dest="action", help="API操作")
    
    parser_api_check = api_subparsers.add_parser("check", help="检查API状态")
    parser_api_check.add_argument("--test", action="store_true", help="执行实际API调用测试")
    parser_api_check.set_defaults(func=cmd_api)
    
    parser_api_setup = api_subparsers.add_parser("setup", help="配置API密钥")
    parser_api_setup.set_defaults(func=cmd_api)
    
    # web 命令
    parser_web = subparsers.add_parser("web", help="启动Web控制台")
    parser_web.add_argument("--host", default=None, help="服务器主机地址（默认：127.0.0.1）")
    parser_web.add_argument("--port", type=int, default=None, help="服务器端口（默认：8080）")
    parser_web.add_argument("--open", action="store_true", dest="open", default=None, help="自动打开浏览器")
    parser_web.add_argument("--no-open", action="store_false", dest="open", help="不自动打开浏览器")
    parser_web.add_argument("--reload", action="store_true", help="启用自动重载（开发模式）")
    parser_web.add_argument("--docker", action="store_true", help="使用Docker模式（需要Docker）")
    parser_web.add_argument("--full", action="store_true", help="启动完整的kat_rec_web（需要Docker）")
    parser_web.add_argument("--detach", "-d", action="store_true", help="后台运行（仅Docker模式）")
    parser_web.set_defaults(func=cmd_web)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        print("\n💡 使用 'kat help' 查看完整帮助")
        return 1
    
    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

