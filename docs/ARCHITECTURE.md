# System Architecture

**Last Updated**: 2025-11-04  
**Version**: 1.2.0  
**Status**: Stable

---

## 🏗️ Core Architecture Principles

### 1. Single Source of Truth

**`schedule_master.json`** is the single authoritative data source for all episode states and metadata.

### 2. Event-Driven Updates

All state changes are driven by events from the event bus, ensuring consistency and traceability.

### 3. File System as Verification Source

When verifying episode completeness, the file system is the source of truth. State can be rebuilt from files.

### 4. Atomic Writes

All state updates use temporary files and atomic rename operations to prevent corruption.

---

## 🔄 Maintenance & Release Cycle (MRRC)

The project follows a regular **MRRC (Maintenance, Refactoring & Release Cycle)** to ensure code quality:

### MRRC Phases

1. **Maintenance Pass**
   - Remove scaffolding and deprecated files
   - Clean unused imports and temporary code
   - Archive obsolete configurations

2. **Refactoring Pass**
   - Apply PEP8 standards
   - Add type hints (target: 80%+ coverage)
   - Replace `print()` with structured logging
   - Consolidate duplicate utilities

3. **Documentation Pass**
   - Update README and architecture docs
   - Validate documentation links
   - Generate changelog entries

4. **Logging & Stability Pass**
   - Standardize log levels (DEBUG, INFO, WARNING, ERROR)
   - Verify JSON log format
   - Test state transitions (Stage 1-10)

5. **Release Preparation**
   - Run test suite
   - Check dependencies (`pip check`)
   - Validate system integrity

### Running MRRC

```bash
# Dry run (preview changes)
python scripts/mrrc_cycle.py --dry-run

# Run specific phase
python scripts/mrrc_cycle.py --phase maintenance

# Run full cycle
python scripts/mrrc_cycle.py
```

**Last MRRC**: 2025-11-04  
**MRRC Tool**: `scripts/mrrc_cycle.py`

---

## 📊 State Management

### State Definitions

Episode states follow a clear state machine model:

```python
STATUS_PENDING = "pending"      # Awaiting production (initial state)
STATUS_REMIXING = "remixing"    # Remixing audio
STATUS_RENDERING = "rendering"   # Rendering video
STATUS_UPLOADING = "uploading"  # Uploading to YouTube
STATUS_COMPLETED = "completed"  # Completed
STATUS_ERROR = "error"          # Error (requires manual intervention)
```

### State Transitions

State transitions are constrained by validation rules:

```python
STATE_TRANSITIONS = {
    "pending": {"remixing", "error"},
    "remixing": {"rendering", "error"},
    "rendering": {"uploading", "completed", "error"},
    "uploading": {"completed", "error"},
    "completed": set(),  # Terminal state
    "error": {"pending", "remixing"},  # Can recover from error
}
```

---

## 🔧 Core Modules

### 1. State Manager (`src/core/state_manager.py`)

**Responsibilities**:
- State queries: `get_episode_status()`, `get_all_used_tracks()`
- State updates: `update_status()` (with state transition validation)
- State rollback: `rollback_status()` (called on failure)
- Metadata updates: `update_episode_metadata()` (doesn't change state)
- File verification: `verify_episode_files()` (verifies completeness from file system)

**Key Features**:
- Atomic writes (temp file → rename)
- State transition validation (prevents illegal state jumps)
- Caching mechanism (reduces file IO)
- Concurrency control (StateLock prevents simultaneous updates)

---

### 2. Event Bus (`src/core/event_bus.py`)

**Responsibilities**:
- Event dispatching: Triggers events on each stage success/failure
- Automatic state updates: Automatically updates `schedule_master.json` status based on event type
- Logging: Records all event history (max 100)
- Subscription mechanism: Supports custom event handlers

**Event Types**:
- `REMIX_STARTED`, `REMIX_COMPLETED`, `REMIX_FAILED`
- `VIDEO_RENDER_STARTED`, `VIDEO_RENDER_COMPLETED`, `VIDEO_RENDER_FAILED`
- `UPLOAD_STARTED`, `UPLOAD_COMPLETED`, `UPLOAD_FAILED`
- `YOUTUBE_ASSETS_GENERATED`, `YOUTUBE_ASSETS_FAILED`
- `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`

**Event Flow**:
```
Action → Event Bus → State Manager → schedule_master.json
                ↓
         Metrics Manager
                ↓
         Structured Logger
```

---

### 3. Metrics Manager (`src/core/metrics_manager.py`)

**Responsibilities**:
- Track stage duration
- Record success/failure rates
- Collect daily statistics
- Export metrics data

**Metrics Collected**:
- Stage duration (remix, render, upload)
- Success/failure counts
- Daily episode counts
- Average tracks per episode

---

### 4. Structured Logger (`src/core/logger.py`)

**Responsibilities**:
- Unified log format (timestamp, episode_id, event_name, message)
- Automatic log rotation (max 5MB, keep 5 files)
- JSON format output
- Integration with event bus (automatically records all events)

**Log Format**:
```json
{
  "timestamp": "2025-11-02T15:20:48",
  "event_name": "remix.completed",
  "episode_id": "20251102",
  "message": "Audio remix completed",
  "level": "INFO",
  "metadata": {...}
}
```

---

## 🔄 Workflow Architecture

### Normal Flow (Success)

```
1. Track Selection & Scheduling
   → Update metadata (title, tracks_used, starting_track)
   → State: "pending"
   → Event: stage_completed("track_selection")

2. Remix Start
   → Event: remix_started
   → State: "remixing"

3. Remix Complete
   → Event: remix_completed
   → State: "rendering"

4. Video Render Start
   → Event: video_render_started
   → State: "rendering"

5. Video Render Complete
   → Event: video_render_completed
   → State: "uploading"

6. Upload Start (Stage 10)
   → Event: upload_started
   → State: "uploading"
   → OAuth authentication (if needed)
   → Resumable upload to YouTube

7. Upload Complete
   → Event: upload_completed
   → State: "completed" (terminal)
   → Write `youtube_video_id` to schedule_master.json
   → Generate `*_youtube_upload.json` result file
```

### Error Flow

```
Any Stage Failure
   → Event: {stage}_failed
   → State: "error"
   → Automatic Rollback (optional)
   → Manual Recovery Required
```

---

## 📁 Directory Structure

```
Kat_Rec/
├── config/
│   ├── config.yaml              # Unified configuration
│   ├── workflow.yml            # Workflow definitions
│   ├── schedule_master.json    # Single source of truth
│   └── google/                 # YouTube API credentials
│       ├── client_secrets.json
│       └── youtube_token.json
├── data/
│   ├── song_library.csv        # Song catalog
│   └── metrics.json            # Metrics data
├── src/
│   └── core/                   # Core modules
│       ├── state_manager.py
│       ├── event_bus.py
│       ├── metrics_manager.py
│       └── logger.py
├── scripts/
│   ├── local_picker/
│   │   ├── create_mixtape.py
│   │   ├── youtube_auth.py
│   │   └── youtube_upload.py
│   └── uploader/
│       └── upload_to_youtube.py  # Stage 10: YouTube Upload
├── output/                     # Generated content
│   └── {YYYY-MM-DD}_{Title}/
├── logs/                       # System logs
│   └── system_events.log
└── docs/                       # Documentation
```

---

## 🔐 Security & Data Integrity

### Atomic Writes

All critical file writes use atomic operations:
1. Write to temporary file
2. Verify write success
3. Atomic rename to final location

### Token Security

- OAuth tokens stored with 600 permissions (owner read/write only)
- Token files in `.gitignore`
- Automatic token refresh on expiry

### YouTube Upload (Stage 10)

**Configuration**:
- OAuth 2.0 credentials: `config/google/client_secrets.json`
- Token cache: `config/google/youtube_token.json`
- Upload defaults: `config/config.yaml` → `youtube.upload_defaults`

**Features**:
- Resumable upload (supports large files >256MB)
- Exponential backoff retry (up to 5 attempts)
- Automatic subtitle and thumbnail upload
- Quota awareness and rate limiting
- Idempotent: Skips upload if `youtube_video_id` already exists
- Structured JSON logging to `logs/katrec.log`

### State Consistency

- File system verification before state updates
- Automatic state sync from file system
- Rollback mechanism on failure

---

## 🔗 Related Documents

- [Development Log](./DEVELOPMENT.md) - Recent changes and achievements
- [Roadmap](./ROADMAP.md) - Future improvements
- [State Refactor Details](./archive/state_refactor.md) - Detailed refactoring notes

---

**Last Updated**: 2025-11-02

