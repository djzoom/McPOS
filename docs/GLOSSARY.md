# Glossary

**Last Updated**: 2025-01-XX

## Naming Conventions

### MCRB vs T2R

- **MCRB** (Mission Control Reality Board): Public-facing name used in:
  - Documentation
  - User interfaces
  - Navigation menus
  - Public APIs (URL paths: `/api/mcrb/*`)
  - User-facing terminology

- **T2R** (Trip to Reality): Internal codename preserved for:
  - Code modules (`t2r/` package)
  - Internal function/variable names
  - WebSocket event names (`t2r_scan_progress`, `t2r_fix_applied`, etc.)
  - Legacy API paths (`/api/t2r/*`) - maintained for backward compatibility
  - Telemetry and logging

**Relationship**: MCRB (public name) ≡ T2R (internal codename)

### Route Aliases

- `/api/t2r/*` - Original prefix (stable, maintained for backward compatibility)
- `/api/mcrb/*` - Public alias (same router instances, no duplication)
- Both prefixes serve identical functionality; choose based on context:
  - Public APIs → use `/api/mcrb/*`
  - Internal tools → use `/api/t2r/*`

### WebSocket Events

All WebSocket events maintain `t2r_*` prefix for:
- Consistency with existing telemetry
- Minimal disruption to verification scripts
- Backward compatibility with monitoring tools

**Event Schema**:
```json
{
  "type": "t2r_{event_type}",
  "version": <monotonically_increasing_int>,
  "ts": "ISO8601_timestamp",
  "level": "info|warn|error",
  "data": {...}
}
```

**Key Events**:
- `t2r_scan_progress` - Schedule scanning progress
- `t2r_fix_applied` - SRT fix completion
- `t2r_runbook_stage_update` - Runbook execution stages
- `t2r_upload_progress` - Video upload progress
- `t2r_verify_result` - Post-upload verification

## Technical Terms

### Atomic Operations

- **Atomic Write**: JSON writes using `t2r/utils/atomic_write.py` to prevent corruption
- **Atomic Group**: Multiple writes bundled via `t2r/utils/atomic_group.py` for transaction-like behavior

### Service Architecture

- **Backend**: FastAPI application (`kat_rec_web/backend/`)
- **Frontend**: Next.js application (`kat_rec_web/frontend/`)
- **T2R Module**: Core business logic (`kat_rec_web/backend/t2r/`)

### State Management

- **Channel Task State**: Backend state enum → UI tag mapping via `StateManager`
- **Episode Status**: Episode lifecycle states synchronized between backend and frontend

## Versioning

- **API Version**: 1.0.0 (semantic versioning)
- **WS Event Version**: Monotonically increasing integer per `ConnectionManager` instance
- **Schema Stability**: Until v1.0, event names and main routes remain unchanged

## Paths & Conventions

- **Static Export**: Frontend builds to `kat_rec_web/frontend/out/` for desktop app packaging
- **Output Directory**: Runtime artifacts (`output/`) - excluded from git
- **Data Directory**: Indices and journals (`data/`) - version controlled

---

**Note**: This glossary is maintained as part of the consolidation effort. For code-specific details, refer to inline documentation and API schemas.

