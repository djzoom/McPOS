# System Overview

**Last Updated**: 2025-11-16  
**Status**: Stable (Stateflow V4 - File System SSOT Architecture)

---

## Architecture

### Core Principles (Stateflow V4)

1. **File System as Single Source of Truth (SSOT)**: All asset states are determined by filesystem detection via `file_detect.py`
2. **No Asset State Registry (ASR)**: ASR has been completely removed. File system is the only source of truth.
3. **Event-Driven Updates**: All state changes flow through the event bus and WebSocket
4. **File System Detection**: Asset states are detected via `file_detect.py` module, not stored in databases
5. **Atomic Writes**: All state updates use temporary files and atomic rename operations
6. **Channel-Centric**: Each channel has independent schedule, library, and output directories
7. **Work Cursor**: Date pointer that only moves forward, protecting completed work
8. **Plugin-Based Architecture**: Extensible workflow system with dynamic plugin loading
9. **Queue-Based Execution**: Serial render/upload queues ensure stability and prevent conflicts

### System Architecture

```
Frontend (Next.js 15 + React 19)
    ↓ WebSocket + REST API
Backend (FastAPI)
    ↓ Event Bus
Core Engine (StateManager, EventBus, Workflow)
    ↓
Plugin System → Channel Automation
    ↓
File System (SSOT) ← file_detect.py
    ↓
Data Layer (schedule_master.json, output directories)
    ↓
Queue System (Render Queue, Upload Queue, Verify Worker)
```

### Technology Stack

- **Backend**: FastAPI, Python 3.11+, asyncio
- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS
- **State Management**: Zustand + React Query
- **Real-time**: WebSocket (`/ws/events`)
- **Media Processing**: FFmpeg, Pillow
- **State Storage**: File System (SSOT via file_detect.py)
- **File Monitoring**: watchdog (optional, with polling fallback)
- **Resource Monitoring**: psutil (optional, with graceful degradation)

### Channel-Centric Structure

```
channels/
  {channel_id}/
    schedule_master.json    # Single source of truth
    config/config.yaml      # Channel-specific config
    library/
      songs/                # Music library
      images/               # Image library
    output/                 # Generated content
    data/
      metrics.json          # Channel metrics
```

---

## Asset State Management System (Stateflow V4)

### File System as Single Source of Truth

**Location**: `kat_rec_web/backend/t2r/utils/file_detect.py`

**Features**:
- Filesystem-based asset detection (no database storage)
- Real-time file system scanning
- Unified detection API for all asset types
- WebSocket real-time updates via `/api/t2r/episodes/{episode_id}/assets`

**Supported Asset Types**:
- `playlist`, `cover`, `audio`, `timeline_csv`, `description`, `captions`, `video`, `render_complete_flag`, `upload_log`, `youtube_title`

**Detection Methods**:
- `detect_video()` - Video file and render flag detection
- `detect_audio()` - Audio file detection
- `detect_cover()` - Cover image detection
- `detect_subtitles()` - SRT file detection
- `detect_description()` - Description file detection
- `detect_title()` - Title file detection
- `detect_all_assets()` - Comprehensive asset detection

**⚠️ ASR Removed**: Asset State Registry (ASR) has been completely removed. All asset states are determined by filesystem detection.

---

## Upload & Verify Pipeline v2

### Upload Pipeline v2

**Architecture Document**: [Upload Pipeline v2 Architecture](ARCHITECTURE_UPLOAD_V2.md)

**Core Components**:
- **UploadQueue** (`kat_rec_web/backend/t2r/services/upload_queue.py`): Serial upload queue manager
- **Upload Routes** (`kat_rec_web/backend/t2r/routes/upload.py`): API endpoints and helpers
- **Unified Logging** (`_write_upload_log()`): Atomic log writing wrapper

**Key Features**:
- Serial execution (one upload at a time)
- Prevents duplicate uploads
- Unified metadata update (single API call)
- Atomic log writing
- WebSocket real-time updates

**State Machine**:
```
queued → uploading → uploaded → verifying → verified
                              ↓
                           failed (at any stage)
```

### Verify Pipeline v2

**Architecture Document**: [Verify Pipeline v2 Architecture](ARCHITECTURE_VERIFY_V2.md)

**Core Components**:
- **VerifyWorker** (`kat_rec_web/backend/t2r/services/verify_worker.py`): Delayed verification worker
- **Unified Logging**: Uses `_write_upload_log()` from upload.py

**Key Features**:
- Delayed verification (default: 180 seconds, configurable)
- Single `videos.list` query per video (1 unit vs 720 units/hour)
- Automatic work cursor update (after successful verification)
- WebSocket real-time updates

**Quota Optimization**:
- **Before**: 720 queries/hour per video (polling every 5 seconds)
- **After**: 1 query per video (after delay)
- **Reduction**: 99.86% quota savings

### End-to-End Lifecycle

**Documentation**: [Upload→Verify Lifecycle](LIFECYCLE_UPLOAD_VERIFY.md)

**Complete Flow**:
1. Upload Initiation → UploadQueue
2. Upload Processing → YouTube API
3. Verification Scheduling → VerifyWorker
4. Verification Processing → YouTube API
5. Work Cursor Update → Schedule Master

**WebSocket Events**: All stages broadcast `upload_state_changed` events with consistent format.

**Usage**:
```python
from kat_rec_web.backend.t2r.utils.file_detect import detect_all_assets, detect_video

# Detect all assets for an episode
assets = await detect_all_assets("kat_lofi", "20251117")

# Detect specific asset
has_video, video_path, has_render_flag = await detect_video("kat_lofi", "20251117")
```

### Asset Detection API

**Endpoint**: `GET /api/t2r/episodes/{episode_id}/assets`

Provides comprehensive asset state for frontend. Returns all asset states detected via filesystem, render status, and upload status.

### Upload Verification & Work Cursor

**Work Cursor**: Date pointer that only moves forward, protecting completed work. Calculated as the day after the last successfully uploaded episode.

**Verification**: Automatic verification after upload completion, including YouTube API checks. Work cursor only advances after successful verification.

**API Endpoints**:
- `GET /api/t2r/schedule/work-cursor` - Get current work cursor date
- `POST /api/t2r/schedule/work-cursor/update` - Update work cursor (forward only)
- `POST /api/t2r/schedule/work-cursor/verify` - Verify upload and update cursor

---

## Resource Monitoring & Intelligent Scheduling

### Resource Monitor

**Location**: `kat_rec_web/backend/t2r/services/resource_monitor.py`

**Features**:
- Real-time CPU, memory, and disk I/O monitoring
- Task resource prediction
- Task acceptance checking
- Resource summary API

**Usage**:
```python
from kat_rec_web.backend.t2r.services.resource_monitor import get_resource_monitor

monitor = get_resource_monitor()
metrics = await monitor.get_current_resources()
can_accept = await monitor.can_accept_task("render", duration=300.0)
```

### Dynamic Semaphore

**Location**: `kat_rec_web/backend/t2r/services/dynamic_semaphore.py`

**Features**:
- Adjusts concurrency based on resource availability
- Automatic limit adjustment (min/max bounds)
- Resource-aware task execution

**Usage**:
```python
from kat_rec_web.backend.t2r.services.dynamic_semaphore import get_dynamic_semaphore

semaphore = get_dynamic_semaphore("remix", initial_limit=2, min_limit=1, max_limit=4)
await semaphore.start()

async with semaphore:
    await remix_audio(episode_id)
```

### Task Priority System

**Location**: `kat_rec_web/backend/t2r/services/task_priority.py`

**Features**:
- Multi-dimensional priority calculation (urgency, dependency, resource, business)
- Priority queue management
- Automatic priority score calculation

**Priority Factors**:
- Urgency: Deadline proximity
- Dependency: Blocking other tasks
- Resource: Resource availability
- Business: Business importance

---

## Plugin System & Pipeline Engine

### Plugin System

**Location**: `kat_rec_web/backend/t2r/services/plugin_system.py`

**Features**:
- Dynamic plugin loading from `t2r/plugins/` directory
- Channel-specific plugins support
- Plugin discovery and registration
- Plugin lifecycle management

**Built-in Plugins**:
- `init_episode_plugin.py`: Episode initialization
- `remix_plugin.py`: Audio remixing
- `cover_plugin.py`: Cover image generation
- `text_assets_plugin.py`: Text assets (title, description, captions, tags)

### Pipeline Engine

**Location**: `kat_rec_web/backend/t2r/services/pipeline_engine.py`

**Features**:
- YAML-based pipeline definition
- Sequential and parallel stage execution
- Conditional stages and retry logic
- Resource-aware task scheduling
- Integration with Asset State Registry

**Pipeline Definition Example**:
```yaml
name: standard_episode_pipeline
stages:
  - name: init
    type: task
    action: init_episode
    dependencies: []
  - name: prepare
    type: parallel
    stages:
      - name: cover
        action: generate_cover
        dependencies: [init]
      - name: text
        action: generate_text_assets
        dependencies: [init]
  - name: remix
    action: remix_audio
    dependencies: [prepare]
    retry:
      max_attempts: 3
      delay: 5.0
```

---

## State Management

### Episode States

```python
STATUS_PENDING = "pending"      # Awaiting production
STATUS_REMIXING = "remixing"    # Mixing audio
STATUS_RENDERING = "rendering"  # Rendering video
STATUS_UPLOADING = "uploading"  # Uploading to YouTube
STATUS_COMPLETED = "completed"  # Fully completed
STATUS_ERROR = "error"          # Requires manual intervention
```

### State Transitions

```
pending → remixing → rendering → uploading → completed
   ↓         ↓          ↓           ↓
  error     error      error      error
   ↓
(recovers to pending or remixing)
```

### Frontend State Management

**Unified Store Architecture**:
- `scheduleStore` - Main store for schedule data and execution state
  - `events`: Episode data
  - `runbookSnapshots`: Execution state cache
  - `getEventWithRunbook()`: Unified selector

**Data Flow**:
```
WebSocket Events → useWebSocket → scheduleStore.runbookSnapshots
                                      ↓
                              Components (auto re-render)
```

---

## Schedule System

### Schedule Master

**Location**: `channels/{channel_id}/schedule_master.json`

**Features**:
- ✅ Immutable once created (eternal standard)
- ✅ Image deduplication (one image per episode)
- ✅ Title deduplication (avoid repeated patterns)
- ✅ Track deduplication (avoid recent repeats, unique starting tracks)
- ✅ Maximum 26 tracks per playlist

### Creating Schedule

```bash
# Create 100-episode schedule
python scripts/kat_cli.py schedule create --episodes 100

# With options
python scripts/kat_cli.py schedule create \
  --episodes 100 \
  --start-date 2025-12-01 \
  --interval 2 \
  --yes  # Skip confirmation
```

### Schedule Features

**Image Management**:
- Random allocation on creation (fixed order)
- One image per episode, marked after use
- Error if images < episodes

**Title Deduplication**:
- Extract pattern from generated titles
- Re-generate if duplicate (max 3 attempts)
- Optimize API prompts to avoid common patterns

**Track Deduplication**:
- Exclude tracks from last 5 episodes
- Ensure unique starting tracks
- Relax restrictions if < 26 tracks available

---

## T2R/MCRB System

**Mission Control: Reality Board (MCRB)** migrates Kat Records content lifecycle from CLI to Web control center.

**Core Features**:
- ✅ Real-time schedule synchronization
- ✅ File state management
- ✅ Auto scan, fix, lock published content
- ✅ Dynamic Recipe generation and Runbook execution
- ✅ End-to-end upload and verification visualization
- ✅ Parallel task management (100+ channels)

**API Endpoints**:
- `/api/t2r/scan` - Schedule scanning and locking
- `/api/t2r/srt/*` - SRT inspection and repair
- `/api/t2r/desc/lint` - Description normalization
- `/api/episodes/plan` - Recipe generation
- `/api/episodes/run` - Runbook execution

---

## Library Management

### V2 System (Database-Based)

**Features**:
- ✅ Full CRUD operations
- ✅ Soft delete mechanism
- ✅ Usage tracking (times_used, usage_status)
- ✅ Advanced search and filtering
- ✅ Folder monitoring and auto-sync

**API Endpoints**:
- `GET /api/library/v2/tracks` - List tracks
- `POST /api/library/v2/tracks` - Create track
- `PATCH /api/library/v2/tracks/{id}` - Update track
- `DELETE /api/library/v2/tracks/{id}/soft` - Soft delete

**Usage Status**:
- `unused` (0 uses)
- `rarely_used` (1-2 uses)
- `occasionally_used` (3-10 uses)
- `frequently_used` (11-50 uses)
- `heavily_used` (50+ uses)

---

## Channel Configuration

### Configuration Priority

1. Channel-specific config (`channels/{channel_id}/config/config.yaml`)
2. Environment variables (`KATREC_*`, `CHANNEL_ID`)
3. Global config (`config/config.yaml`)
4. Code defaults

### Usage

```python
from src.configuration import load_channel_context
from core.channel_context import resolve_channel_id

channel_id = resolve_channel_id(args.channel)
context = load_channel_context(channel_id)
config = context.app_config
```

---

## API Versioning

### Version Management

**Location**: `kat_rec_web/backend/t2r/services/api_versioning.py`

**Features**:
- Version detection (path, Accept header, X-API-Version header)
- Version-specific response formatting
- Data migration helpers
- Support for v1 and v2 API versions

**Compatibility**:
- All existing APIs maintain backward compatibility
- New features use v2 API version
- Version coexistence supported

---

## Data Migration & Compatibility

### Migration Strategy

**Status**: ✅ 85% Complete (Core 100%)

**Completed**:
- ✅ `schedule_master.json` compatibility maintained
- ✅ File system as source of truth
- ✅ Migration scripts (schedule_master.json → ASR)
- ✅ API version management infrastructure
- ✅ Frontend progressive upgrade

**Optional**:
- ⚠️ manifest.json migration (30% - optional)
- ⚠️ Compatibility adapter layer (0% - optional, current APIs already compatible)

### Compatibility

**Backward Compatibility**:
- All existing API endpoints continue to work
- `schedule_master.json` remains readable
- Progressive migration, no breaking changes

**Dependencies**:
- `watchdog` (optional) - File system monitoring
- `psutil` (optional) - Resource monitoring
- `sqlite3` (standard library) - Asset State Registry

---

**Related**: 
- [Workflow Guide](02_WORKFLOW_AND_AUTOMATION.md)
- [Development Guide](03_DEVELOPMENT_GUIDE.md)
- [Upload Pipeline v2 Architecture](ARCHITECTURE_UPLOAD_V2.md)
- [Verify Pipeline v2 Architecture](ARCHITECTURE_VERIFY_V2.md)
- [Upload→Verify Lifecycle](LIFECYCLE_UPLOAD_VERIFY.md)
