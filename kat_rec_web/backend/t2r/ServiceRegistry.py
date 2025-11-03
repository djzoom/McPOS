"""
Service Registry

Centralized registry for T2R service imports to avoid duplicate/fragile imports.
This module provides a single source of truth for service initialization.
"""
from typing import Optional

# Lazy-loaded service modules
_scan = None
_srt = None
_plan = None
_upload = None
_audit = None
_metrics = None

def get_scan_router():
    """Get scan router (lazy import)"""
    global _scan
    if _scan is None:
        from t2r.routes import scan
        _scan = scan
    return _scan.router

def get_srt_router():
    """Get SRT router (lazy import)"""
    global _srt
    if _srt is None:
        from t2r.routes import srt
        _srt = srt
    return _srt.router

def get_plan_router():
    """Get plan router (lazy import)"""
    global _plan
    if _plan is None:
        from t2r.routes import plan
        _plan = plan
    return _plan.router

def get_upload_router():
    """Get upload router (lazy import)"""
    global _upload
    if _upload is None:
        from t2r.routes import upload
        _upload = upload
    return _upload.router

def get_audit_router():
    """Get audit router (lazy import)"""
    global _audit
    if _audit is None:
        from t2r.routes import audit
        _audit = audit
    return _audit.router

def get_metrics_router():
    """Get metrics router (lazy import)"""
    global _metrics
    if _metrics is None:
        from t2r.routes import metrics
        _metrics = metrics
    return _metrics.router

def register_all_routers(app, prefix_t2r: str = "/api/t2r", prefix_mcrb: str = "/api/mcrb"):
    """
    Register all T2R routers with both prefixes.
    
    Args:
        app: FastAPI application instance
        prefix_t2r: Original prefix (backward compatibility)
        prefix_mcrb: Public alias prefix
    """
    routers = [
        ("scan", get_scan_router()),
        ("srt", get_srt_router()),
        ("plan", get_plan_router()),
        ("upload", get_upload_router()),
        ("audit", get_audit_router()),
        ("metrics", get_metrics_router()),
    ]
    
    for name, router in routers:
        # Original prefix
        app.include_router(router, prefix=prefix_t2r, tags=["t2r"])
        # Public alias
        app.include_router(router, prefix=prefix_mcrb, tags=["mcrb"])
    
    return len(routers)

