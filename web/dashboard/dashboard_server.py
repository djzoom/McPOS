#!/usr/bin/env python3
# coding: utf-8
"""
仪表板服务器

提供Web界面和API端点
"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加项目路径
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    FASTAPI_AVAILABLE = True
except ImportError:
    print("❌ FastAPI未安装")
    print("   请运行: pip install fastapi uvicorn jinja2")
    FASTAPI_AVAILABLE = False
    sys.exit(1)

# 导入指标API（可选）
try:
    from src.api.metrics_api import app as metrics_app
    METRICS_API_AVAILABLE = True
    print("✅ 指标API已加载")
except ImportError as e:
    METRICS_API_AVAILABLE = False
    metrics_app = None
    print(f"⚠️  指标API未加载: {e}")

try:
    from core.state_manager import get_state_manager
    from core.metrics_manager import get_metrics_manager
    STATE_MANAGEMENT_AVAILABLE = True
    print("✅ 状态管理器已加载")
except ImportError as e:
    STATE_MANAGEMENT_AVAILABLE = False
    get_state_manager = None
    get_metrics_manager = None
    print(f"⚠️  状态管理器未加载: {e}")

# 创建主应用
app = FastAPI(title="Kat Records Dashboard")

# 添加CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载指标API（如果可用）
if METRICS_API_AVAILABLE and metrics_app:
    try:
        app.mount("/metrics", metrics_app)
        print("✅ 指标API已挂载到 /metrics")
    except Exception as e:
        print(f"⚠️  无法挂载指标API: {e}")
else:
    print("⚠️  指标API不可用，部分功能将受限")

# 挂载静态文件
templates_dir = Path(__file__).parent / "templates"
if templates_dir.exists():
    app.mount("/static", StaticFiles(directory=str(templates_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """仪表板主页面"""
    dashboard_html = templates_dir / "dashboard.html"
    if dashboard_html.exists():
        return FileResponse(dashboard_html)
    else:
        return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


@app.get("/episodes", response_class=HTMLResponse)
async def episodes_page():
    """期数管理页面"""
    episodes_html = templates_dir / "episodes.html"
    if episodes_html.exists():
        return FileResponse(episodes_html)
    else:
        return HTMLResponse(content="<h1>期数管理页面</h1><p>页面建设中...</p>", status_code=200)


@app.get("/library", response_class=HTMLResponse)
async def library_page():
    """资源库管理页面"""
    library_html = templates_dir / "library.html"
    if library_html.exists():
        return FileResponse(library_html)
    else:
        return HTMLResponse(content="<h1>资源库管理页面</h1><p>页面建设中...</p>", status_code=200)


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page():
    """数据分析页面"""
    analytics_html = templates_dir / "analytics.html"
    if analytics_html.exists():
        return FileResponse(analytics_html)
    else:
        return HTMLResponse(content="<h1>数据分析页面</h1><p>页面建设中...</p>", status_code=200)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    """设置页面"""
    settings_html = templates_dir / "settings.html"
    if settings_html.exists():
        return FileResponse(settings_html)
    else:
        return HTMLResponse(content="<h1>设置页面</h1><p>页面建设中...</p>", status_code=200)


@app.get("/api/health")
async def health():
    """健康检查端点"""
    return {
        "status": "ok",
        "metrics_api": METRICS_API_AVAILABLE,
        "state_management": STATE_MANAGEMENT_AVAILABLE
    }


# 直接实现 metrics API 端点（如果 metrics_api 未加载）
if not METRICS_API_AVAILABLE and STATE_MANAGEMENT_AVAILABLE:
    @app.get("/metrics/summary")
    async def get_summary(period: str = "24h"):
        """获取聚合指标摘要"""
        try:
            from core.metrics_manager import get_metrics_manager
            metrics_manager = get_metrics_manager()
            if metrics_manager:
                summary = metrics_manager.get_summary(period=period)
            else:
                summary = {}
            
            # 添加全局状态信息
            state_manager = get_state_manager()
            if state_manager:
                schedule = state_manager._load()
                if schedule:
                    episodes = schedule.get("episodes", [])
                    
                    # 状态映射：支持中文和英文状态值
                    status_map = {
                        # 中文状态
                        "待制作": "pending",
                        "制作中": "remixing",
                        "上传中": "uploading",
                        "排播完毕待播出": "uploading",
                        "已完成": "completed",
                        "已跳过": "pending",
                        # 英文状态（向后兼容）
                        "pending": "pending",
                        "remixing": "remixing",
                        "rendering": "rendering",
                        "uploading": "uploading",
                        "completed": "completed",
                        "error": "error",
                    }
                    
                    # 统计各状态的数量
                    status_counts = {"pending": 0, "remixing": 0, "rendering": 0, 
                                   "completed": 0, "error": 0, "uploading": 0}
                    
                    for ep in episodes:
                        status = ep.get("status", "待制作")
                        # 规范化状态
                        normalized = status_map.get(status, "pending")
                        if normalized in status_counts:
                            status_counts[normalized] += 1
                    
                    summary["global_state"] = {
                        "total_episodes": len(episodes),
                        "pending": status_counts["pending"],
                        "remixing": status_counts["remixing"],
                        "rendering": status_counts["rendering"],
                        "completed": status_counts["completed"],
                        "error": status_counts["error"],
                    }
            
            return summary
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取指标失败: {str(e)}")
    
    @app.get("/metrics/episodes")
    async def get_episodes_status():
        """获取所有期数的状态"""
        try:
            state_manager = get_state_manager()
            if not state_manager:
                return {"episodes": [], "total": 0}
            
            schedule = state_manager._load()
            if not schedule:
                return {"episodes": [], "total": 0}
            
            from datetime import datetime
            episodes = []
            
            # 状态映射（用于统一显示）
            status_normalize = {
                "待制作": "pending",
                "制作中": "remixing", 
                "上传中": "uploading",
                "排播完毕待播出": "uploading",
                "已完成": "completed",
                "已跳过": "pending",
            }
            
            for ep in schedule.get("episodes", []):
                original_status = ep.get("status", "待制作")
                # 将中文状态转换为英文（前端期望英文）
                normalized_status = status_normalize.get(original_status, original_status)
                # 如果不在映射中，尝试原样使用（可能是英文）
                if normalized_status == original_status and original_status not in ["pending", "remixing", "rendering", "completed", "error", "uploading"]:
                    normalized_status = "pending"
                
                episodes.append({
                    "episode_id": ep.get("episode_id"),
                    "episode_number": ep.get("episode_number"),
                    "schedule_date": ep.get("schedule_date"),
                    "status": normalized_status,  # 使用规范化后的状态
                    "title": ep.get("title"),
                    "status_updated_at": ep.get("status_updated_at"),
                    "error_details": ep.get("error_details"),
                })
            
            return {
                "episodes": episodes,
                "total": len(episodes),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取期数状态失败: {str(e)}")
    
    @app.get("/metrics/events")
    async def get_events(limit: int = 50):
        """获取最近的事件流"""
        try:
            from core.metrics_manager import get_metrics_manager
            from datetime import datetime
            metrics_manager = get_metrics_manager()
            if metrics_manager:
                events = metrics_manager.get_recent_events(limit=limit)
            else:
                events = []
            
            return {
                "events": events,
                "count": len(events),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取事件失败: {str(e)}")


@app.post("/api/recover/{episode_id}")
async def recover_episode_api(episode_id: str):
    """恢复期数API端点"""
    if not STATE_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="状态管理器不可用")
    
    try:
        state_manager = get_state_manager()
        if not state_manager:
            raise HTTPException(status_code=500, detail="状态管理器未初始化")
        
        # 回滚状态
        success = state_manager.rollback_status(episode_id, target_status="pending")
        
        if success:
            # 记录指标（如果可用）
            if get_metrics_manager:
                try:
                    metrics_manager = get_metrics_manager()
                    metrics_manager.record_event(
                        stage="recovery",
                        status="completed",
                        episode_id=episode_id
                    )
                except Exception as metrics_error:
                    # 指标管理器可选，记录但不失败
                    import logging
                    logging.getLogger(__name__).debug(f"Metrics recording failed: {metrics_error}")
            
            return {"status": "success", "message": f"期数 {episode_id} 已恢复"}
        else:
            raise HTTPException(status_code=500, detail="恢复失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

