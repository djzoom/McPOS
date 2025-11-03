#!/usr/bin/env python3
# coding: utf-8
"""
指标API端点

使用FastAPI提供实时指标查询接口
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 添加项目路径
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    FASTAPI_AVAILABLE = True
except ImportError as e:
    # 不直接抛出异常，让调用方处理
    FASTAPI_AVAILABLE = False
    FastAPI = None
    HTTPException = None
    CORSMiddleware = None

try:
    from core.metrics_manager import get_metrics_manager
    from core.state_manager import get_state_manager
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    get_metrics_manager = None
    get_state_manager = None

# 创建FastAPI应用（仅在FastAPI可用时）
if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Kat Records Metrics API",
        description="实时指标和状态查询API",
        version="1.0.0"
    )
    
    # 添加CORS中间件
    if CORSMiddleware:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # 生产环境应该限制
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
else:
    # FastAPI不可用时，创建一个占位符对象
    class MockApp:
        def mount(self, *args, **kwargs):
            pass
        def get(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    app = MockApp()


@app.get("/")
async def root():
    """API根路径"""
    return {
        "name": "Kat Records Metrics API",
        "version": "1.0.0",
        "endpoints": {
            "/summary": "获取聚合指标摘要",
            "/episodes": "获取所有期数状态",
            "/events": "获取最近事件流",
            "/episode/{episode_id}": "获取特定期数指标",
        }
    }


@app.get("/summary")
async def get_summary(period: str = "24h") -> Dict:
    """
    获取聚合指标摘要
    
    Args:
        period: 时间周期 ("24h", "7d", "30d", "all")
    
    Returns:
        聚合指标字典
    """
    if not FASTAPI_AVAILABLE or not HTTPException:
        raise Exception("FastAPI未安装")
    if not IMPORTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="核心模块未导入")
    
    try:
        metrics_manager = get_metrics_manager()
        if not metrics_manager:
            return {"global_state": {}, "stages": {}}
        summary = metrics_manager.get_summary(period=period)
        
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


@app.get("/episodes")
async def get_episodes_status() -> Dict:
    """
    获取所有期数的状态
    
    Returns:
        期数状态列表
    """
    if not FASTAPI_AVAILABLE or not HTTPException:
        raise Exception("FastAPI未安装")
    if not IMPORTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="核心模块未导入")
    
    try:
        state_manager = get_state_manager()
        if not state_manager:
            return {"episodes": [], "total": 0}
        
        schedule = state_manager._load()
        if not schedule:
            return {"episodes": [], "total": 0}
        
        episodes = []
        for ep in schedule.get("episodes", []):
            episodes.append({
                "episode_id": ep.get("episode_id"),
                "episode_number": ep.get("episode_number"),
                "schedule_date": ep.get("schedule_date"),
                "status": ep.get("status", "pending"),
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


@app.get("/events")
async def get_events(limit: int = 50) -> Dict:
    """
    获取最近的事件流
    
    Args:
        limit: 返回数量限制（默认50）
    
    Returns:
        事件列表
    """
    if not FASTAPI_AVAILABLE or not HTTPException:
        raise Exception("FastAPI未安装")
    if not IMPORTS_AVAILABLE:
        raise HTTPException(status_code=503, detail="核心模块未导入")
    
    try:
        metrics_manager = get_metrics_manager()
        if not metrics_manager:
            return {"events": [], "count": 0, "timestamp": datetime.now().isoformat()}
        events = metrics_manager.get_recent_events(limit=limit)
        
        return {
            "events": events,
            "count": len(events),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取事件失败: {str(e)}")


@app.get("/episode/{episode_id}")
async def get_episode_metrics(episode_id: str) -> Dict:
    """
    获取特定期数的指标
    
    Args:
        episode_id: 期数ID
    
    Returns:
        期数指标字典
    """
    try:
        metrics_manager = get_metrics_manager()
        metrics = metrics_manager.get_episode_metrics(episode_id)
        
        # 添加当前状态
        state_manager = get_state_manager()
        if state_manager:
            ep = state_manager.get_episode(episode_id)
            if ep:
                metrics["current_status"] = ep.get("status")
                metrics["schedule_date"] = ep.get("schedule_date")
                metrics["title"] = ep.get("title")
        
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取期数指标失败: {str(e)}")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

