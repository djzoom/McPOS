"""
T2R Main Router

Aggregates all T2R routes.
"""
from fastapi import APIRouter
from .routes import scan, srt, desc, plan, upload, audit, metrics

router = APIRouter()

# Include all T2R routes
router.include_router(scan.router, tags=["t2r-scan"])
router.include_router(srt.router, tags=["t2r-srt"])
router.include_router(desc.router, tags=["t2r-desc"])
router.include_router(plan.router, tags=["t2r-plan"])
router.include_router(upload.router, tags=["t2r-upload"])
router.include_router(audit.router, tags=["t2r-audit"])
router.include_router(metrics.router, tags=["t2r-metrics"])

