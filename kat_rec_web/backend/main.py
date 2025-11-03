#!/usr/bin/env python3
"""
Kat Rec Web Control Center - Backend API

FastAPI application for managing Kat Records automation workflow.
Supports single-channel MVP with scalability hooks for multi-channel expansion.
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Check if we should use mock mode
USE_MOCK_MODE = os.getenv("USE_MOCK_MODE", "false").lower() == "true"

# Import routes conditionally to avoid dependency issues in mock mode
from routes import mock, websocket, control

# Only import real routes if not in mock mode (they may require sqlalchemy, redis, etc.)
channels = None
library = None
upload = None
status = None
redis_service = None

if not USE_MOCK_MODE:
    try:
        from routes import channels, library, upload, status
        from services.redis_service import RedisService
        from services.database import init_db
        redis_service = RedisService(os.getenv("REDIS_URL", "redis://localhost:6379"))
    except ImportError as e:
        print(f"⚠️  警告: 无法导入真实路由，某些依赖未安装: {e}")
        print("   继续使用 Mock 模式")
        USE_MOCK_MODE = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown"""
    # Startup
    if not USE_MOCK_MODE and redis_service:
        try:
            await redis_service.connect()
            if 'init_db' in globals():
                await init_db()
            print("✅ Backend services initialized")
        except Exception as e:
            print(f"⚠️  服务初始化警告: {e}")
            print("   继续运行（可能部分功能受限）")
    else:
        print("🔧 Mock mode enabled - skipping Redis and DB initialization")
    
    # Start WebSocket broadcast tasks
    await websocket.start_broadcast_tasks()
    
    # --- WebSocket flush loop at startup ---
    try:
        from routes.websocket import events_manager
        if events_manager and hasattr(events_manager, "ensure_started"):
            await events_manager.ensure_started()
            print("✅ WS flush loop started")
        else:
            print("⚠️  WS manager not available or missing ensure_started()")
    except Exception as e:
        print(f"⚠️  WS manager not available: {e}")
    
    yield
    
    # Shutdown
    if not USE_MOCK_MODE and redis_service:
        try:
            await redis_service.disconnect()
            print("👋 Backend services shutdown")
        except Exception:
            pass


# Create FastAPI app
app = FastAPI(
    title="Kat Rec Web Control Center API",
    description="Backend API for Kat Records automation workflow management",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - enhanced for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",  # Additional dev port
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
if USE_MOCK_MODE:
    # Use mock endpoints when in mock mode
    app.include_router(mock.router, prefix="/api/library", tags=["library (mock)"])
    app.include_router(mock.router, prefix="/metrics", tags=["metrics (mock)"])
    print("⚠️  Mock API endpoints enabled")
else:
    # Use real endpoints
    app.include_router(channels.router, prefix="/api", tags=["channels"])
    app.include_router(library.router, prefix="/api/library", tags=["library"])
    app.include_router(upload.router, prefix="/api", tags=["upload"])
    app.include_router(status.router, prefix="/api", tags=["status"])

# Always include mock router for fallback (can be disabled in production)
app.include_router(mock.router, prefix="/mock", tags=["mock"])

# WebSocket and control routes (always available)
app.include_router(websocket.router, tags=["websocket"])
app.include_router(control.router, tags=["control"])

# --- T2R Routers (scan/srt/plan/upload/audit/metrics) ---
# Internal codename: T2R (preserved for backward compatibility)
# Public name: MCRB (Mission Control Reality Board)
try:
    from t2r.routes import scan, srt, plan, upload, audit, metrics
    # Original prefix: /api/t2r/* (stable, no breaking changes)
    app.include_router(scan.router, prefix="/api/t2r", tags=["t2r"])
    app.include_router(srt.router, prefix="/api/t2r", tags=["t2r"])
    app.include_router(plan.router, prefix="/api/t2r", tags=["t2r"])
    app.include_router(upload.router, prefix="/api/t2r", tags=["t2r"])
    app.include_router(audit.router, prefix="/api/t2r", tags=["t2r"])
    # Metrics router: register both at root /metrics/* and /api/t2r/metrics/*
    app.include_router(metrics.router, prefix="", tags=["metrics"])
    app.include_router(metrics.router, prefix="/api/t2r", tags=["t2r"])
    # Public alias: /api/mcrb/* (no duplication, same router instances)
    app.include_router(scan.router, prefix="/api/mcrb", tags=["mcrb"])
    app.include_router(srt.router, prefix="/api/mcrb", tags=["mcrb"])
    app.include_router(plan.router, prefix="/api/mcrb", tags=["mcrb"])
    app.include_router(upload.router, prefix="/api/mcrb", tags=["mcrb"])
    app.include_router(audit.router, prefix="/api/mcrb", tags=["mcrb"])
    app.include_router(metrics.router, prefix="/api/mcrb", tags=["mcrb"])
    print("✅ T2R/MCRB routers registered (dual prefix support)")
except Exception as e:
    print(f"⚠️  T2R routers not available: {e}")

# Add channels endpoint to mock router when in mock mode
if USE_MOCK_MODE:
    # Add a root endpoint for /api/channels
    @app.get("/api/channels", tags=["channels (mock)"])
    async def get_channels():
        """Mock endpoint for listing channels"""
        from routes.mock import mock_list_channels
        return await mock_list_channels()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Kat Rec Web Control Center API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health():
    """Health check endpoint with environment validation"""
    try:
        from t2r.services.env_check import check_required_paths
        ok, details = check_required_paths()
        if ok:
            return {"status": "ok", "details": details}
        return JSONResponse(details, status_code=503)
    except Exception as e:
        return JSONResponse({"status": "fail", "error": str(e)}, status_code=503)

