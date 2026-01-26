# Workflow & Automation

**Last Updated**: 2025-01-XX  
**Status**: Production Ready (Enhanced with Plugin System, Pipeline Engine & Upload/Verify v2)

---

## Asset Generation Workflow

### Generation Order

1. **Initialization** (init_episode)
   - Recipe JSON
   - Playlist CSV
   - Playlist Metadata

2. **Parallel Preparation** (async)
   - Cover generation (`_ensure_cover`)
   - Title generation (`_generate_title_only`)
   - Other text assets (`_generate_other_text_assets`)
     - Description
     - Captions (SRT)
     - Tags

3. **Serial Remix** (FFmpeg queue limit)
   - Audio remix (`remix`)
   - Timeline file (`timeline.csv`)

4. **Render Queue**
   - Dependency check
   - Queue entry
   - Video generation

### Required Files

1. `{episode_id}_manifest.json`
2. `playlist_metadata.json`
3. `playlist.csv`
4. `{episode_id}_cover.png`
5. `{episode_id}_youtube_title.txt`
6. `{episode_id}_youtube_description.txt`
7. `{episode_id}_youtube.srt`
8. `{episode_id}_youtube_tags.txt`
9. `{episode_id}_full_mix.mp3`
10. `{episode_id}_full_mix_timeline.csv`

### Technical Implementation

**Async File Operations**:
- `async_file_exists()` - File existence check
- `async_read_json()` - JSON reading
- `async_write_json()` - JSON writing
- `async_parse_playlist()` - Playlist parsing

**File System Event Monitoring**:
- Uses `file_watcher.py` (watchdog library if available)
- Falls back to periodic checks
- Timeout mechanism prevents infinite waits

**Error Handling**:
- Retry mechanism (exponential backoff)
- Partial failure tolerance
- Detailed error logging

---

## YouTube Integration

### Architecture

**Upload Pipeline v2**: See [Upload Pipeline v2 Architecture](../docs/ARCHITECTURE_UPLOAD_V2.md)  
**Verify Pipeline v2**: See [Verify Pipeline v2 Architecture](../docs/ARCHITECTURE_VERIFY_V2.md)  
**End-to-End Lifecycle**: See [Upload→Verify Lifecycle](../docs/LIFECYCLE_UPLOAD_VERIFY.md)

### Setup

1. **Create Google Cloud Project**
   - Enable YouTube Data API v3
   - Create OAuth 2.0 credentials (Desktop app)
   - Download `client_secrets.json`

2. **Place Credentials**
   ```bash
   mv ~/Downloads/client_secret_*.json \
      config/google/client_secrets.json
   ```

3. **Initial Authorization**
   ```bash
   python scripts/uploader/upload_to_youtube.py --setup
   ```

### Usage

**API Endpoints**:
- `POST /api/t2r/upload/start` - Start upload (enqueues to UploadQueue)
- `POST /api/t2r/upload/full` - Full upload with manifest updates
- `GET /api/t2r/upload/status` - Get upload status (deprecated, prefers WebSocket)
- `POST /api/t2r/upload/verify` - Schedule verification (deprecated, uses VerifyWorker)

**CLI Usage**:
```bash
# Basic upload
python scripts/kat_cli.py upload --episode 20251102

# With options
python scripts/kat_cli.py upload \
  --episode 20251102 \
  --privacy unlisted \
  --schedule  # Schedule publish at episode date 9:00 AM
```

### Features

**Upload Pipeline v2**:
- ✅ Serial upload queue (prevents duplicate uploads)
- ✅ Resumable upload (files >256MB)
- ✅ Automatic token refresh (TokenManager)
- ✅ Unified metadata update (single `videos.update` call)
- ✅ Atomic log writing
- ✅ WebSocket real-time updates

**Verify Pipeline v2**:
- ✅ Delayed verification (3-minute delay, configurable)
- ✅ Single `videos.list` query per video (1 unit vs 720 units/hour)
- ✅ Automatic work cursor update (after successful verification)
- ✅ WebSocket real-time updates

**Legacy Features** (still supported):
- ✅ Retry mechanism (exponential backoff, max 5 attempts)
- ✅ Idempotency (skip if `youtube_video_id` exists)
- ✅ Auto metadata detection
- ✅ Quota awareness

### Metadata Requirements

**Input Files**:
- `{episode_id}_youtube.mp4` - Video file
- `{episode_id}_youtube_title.txt` - Title (auto-detected)
- `{episode_id}_youtube_description.txt` - Description (auto-detected)
- `{episode_id}_youtube.srt` - Subtitles (optional, auto-uploaded if exists)
- `{episode_id}_cover.png` - Thumbnail (optional, auto-resized if >2MB)

**Format Requirements**:
- Description: No markdown, no separators (----), plain text only
- Title: Must use "Kat Records Presents", not "× Vibe Coding"
- SRT: `HH:MM:SS,mmm` format (comma separator for milliseconds)

---

## Rendering Pipeline

### Render Queue

**Global FIFO Queue** (`render_queue.py`):
- Processes one job at a time (with priority support)
- Checks all dependencies before rendering
- FFmpeg-based video generation
- WebSocket progress updates

### Dependencies

Before rendering, system checks:
- ✅ Playlist CSV exists
- ✅ Cover image exists
- ✅ Audio mix exists
- ✅ Title/description files exist

### Video Generation

```bash
# FFmpeg command (simplified)
ffmpeg -loop 1 -i cover.png -i full_mix.mp3 \
  -c:v libx264 -c:a aac \
  -shortest output.mp4
```

### Render Completion Detection

**Methods**:
1. **`render_complete_flag`** - Flag file created after successful render
2. **`ffprobe` validation** - Verifies video file integrity and completeness
3. **File size monitoring** - Tracks file growth during rendering

**Best Practice**: Use `ffprobe` as primary check (validates file integrity), `render_complete_flag` as confirmation.

---

## Render Queue Synchronization

### Problem

Render queue may not reflect actual file system state:
- Completed renders may still show as "waiting"
- Ready episodes may not appear in queue

### Solution

**Asset Synchronization Service** (`render_queue_sync.py`):
- `sync_episode_assets_from_filesystem()` - Syncs single episode assets
- `sync_all_episodes_assets()` - Syncs all episodes
- `get_episodes_ready_for_render()` - Gets episodes ready for rendering
- `get_episodes_with_completed_render()` - Gets completed renders

**Automatic Sync**:
- `list_episodes` API automatically syncs assets before returning
- Frontend can call sync API periodically (every 30 seconds)

**API Endpoints**:
- `POST /api/t2r/render-queue-sync/sync-all` - Sync all episodes
- `GET /api/t2r/render-queue-sync/ready-for-render` - Get ready episodes
- `GET /api/t2r/render-queue-sync/completed-renders` - Get completed renders

### Render Complete Flag

**Location**: `{episode_id}_render_complete.flag`

**Created When**:
- Video render completes successfully
- `ffprobe` validation passes
- Contains render metadata (time, path, size, checksum)

**Required For**:
- Frontend to show render as complete
- Episode to leave render queue

---

## Timeline CSV Generation

### Process

1. **Generated During Remix Stage**
   - After audio remix completes
   - Extracted from `playlist.csv` Timeline section

2. **Extraction Logic**:
   - Find rows with `Section="Timeline"` and `Timeline="Needle"`
   - Filter out SFX (Needle On Vinyl Record, Vinyl Noise, Silence)
   - Write to `{episode_id}_full_mix_timeline.csv`

3. **Format**:
   ```csv
   Timecode,Track Name,Side
   0:00,Track Title,A
   0:03,Another Track,B
   ```

### Troubleshooting

**If timeline.csv is missing**:
- Check if remix stage completed successfully
- Verify `playlist.csv` contains Timeline section
- Manually regenerate from `playlist.csv` if needed

---

## Track Selection Logic

### Deduplication Mechanisms

1. **Recent Tracks Exclusion** (5-episode window)
   - Excludes tracks used in last 5 episodes
   - Prevents immediate repetition
   - Based on `episode_number`, not date

2. **Starting Track Uniqueness** (global)
   - Each episode must have unique starting track
   - Global check across all episodes
   - Prioritizes new tracks as starting tracks

3. **New Track Ratio** (70% new, 30% old)
   - 70% of playlist uses tracks never used before
   - 30% uses previously used tracks
   - Smart interleaving for variety

### Reset Behavior

**After Reset**:
- `tracks_used` may be cleared for reset episodes
- Starting tracks may be preserved if episode uploaded
- Risk: Reset episodes may reuse tracks from before reset

**Recommendation**: Preserve `tracks_used` for uploaded episodes during reset to maintain deduplication.

---

## Automation Worker

### Channel Automation ✅ **Enhanced with Plugin System**

**Location**: `kat_rec_web/backend/t2r/services/channel_automation.py`

**Process**:
1. Episode enqueued via `enqueue_episode()`
2. Worker starts if not running
3. Processes jobs FIFO
4. Parallel preparation (cover + title) - **Now uses plugins**
5. Sequential remix (FFmpeg queue limit) - **Now uses plugins**

**Plugin Integration**:
- `_init_episode`: Uses `init_episode_plugin`
- `_ensure_cover`: Uses `cover_plugin`
- `_generate_title_only`: Uses `text_assets_plugin`
- `_run_remix_stage`: Uses `remix_plugin`
- `_generate_other_text_assets`: Uses `text_assets_plugin`

**Worker Loop**:
- Checks queue every 500ms when empty
- Exits after 3 consecutive empty checks
- Handles job failures gracefully
- **Resource-aware**: Uses dynamic semaphore for concurrency control

### Render Queue ✅ **Enhanced with Priority System**

**Location**: `kat_rec_web/backend/t2r/services/render_queue.py`

**Process**:
- Global FIFO queue (with priority support)
- One render job at a time
- Dependency verification before render
- WebSocket progress updates
- **Priority-based**: Tasks with higher priority (e.g., near deadline) are processed first

### Plugin System ✅ **New Feature**

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
- `text_assets_plugin.py`: Text assets generation

**Usage**:
```python
from kat_rec_web.backend.t2r.services.plugin_system import get_plugin_manager

plugin_manager = await get_plugin_manager()
plugin = await plugin_manager.load_plugin("init_episode_plugin")
result = await plugin.execute(context)
```

### Pipeline Engine ✅ **New Feature**

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

### Resource Monitoring & Dynamic Semaphore ✅ **New Feature**

**Location**: 
- `kat_rec_web/backend/t2r/services/resource_monitor.py`
- `kat_rec_web/backend/t2r/services/dynamic_semaphore.py`

**Features**:
- Real-time CPU, memory, and disk I/O monitoring
- Dynamic semaphore that adjusts concurrency based on resource availability
- Task resource prediction and acceptance checking
- Automatic concurrency adjustment (min/max limits)

**Usage**:
```python
from kat_rec_web.backend.t2r.services.dynamic_semaphore import get_dynamic_semaphore

semaphore = get_dynamic_semaphore("remix", initial_limit=2, min_limit=1, max_limit=4)
await semaphore.start()

async with semaphore:
    # Task execution with automatic resource-aware concurrency control
    await remix_audio(episode_id)
```

### Task Priority System ✅ **New Feature**

**Location**: `kat_rec_web/backend/t2r/services/task_priority.py`

**Features**:
- Multi-dimensional priority calculation (urgency, dependency, resource, business)
- Priority queue management
- Automatic priority score calculation
- Integration with resource monitor and dynamic semaphore

**Priority Factors**:
- Urgency: Deadline proximity
- Dependency: Blocking other tasks
- Resource: Resource availability
- Business: Business importance

---

## Troubleshooting

### Episode Only Generated Playlist

**Symptoms**: Only `playlist.csv`, `manifest.json`, `playlist_metadata.json` exist

**Causes**:
1. Backend service not running (`channel_automation` worker not started)
2. Episode not enqueued (only `init-episode` called, not `create-episode`)
3. CLI used `--no-remix` or `--no-video` flags

**Solutions**:
```bash
# Check backend
lsof -i :8000

# Check automation queue
tail -f logs/system_events.log | grep "\[automation\]"

# Resume workflow
python scripts/resume_episode_workflow.py \
  --channel kat_lofi \
  --use-automation 20251111 20251112
```

### File Generation Incomplete

**Check**:
- Log errors in `logs/system_events.log`
- Verify file system permissions
- Confirm all dependencies generated

### Cover Generation Failed

**Check**:
- Image library status
- API configuration
- File system permissions

### MP3 Remix Timeout

**Check**:
- FFmpeg process status
- Audio file integrity
- System resources

### YouTube Upload Errors

**Common Issues**:
1. **Authentication Failed**: Run `--setup` again
2. **Quota Exceeded**: Wait 24 hours or increase quota
   - Upload v2 uses serial queue to prevent quota exhaustion
   - Verify v2 reduces quota consumption by 99.86% (1 unit vs 720 units/hour)
3. **Video File Not Found**: Ensure video rendered first
4. **ModuleNotFoundError**: Install Google API libraries
5. **Upload Queue Full**: Wait for current upload to complete (serial execution)
6. **Verification Timeout**: Check YouTube API status, video may still be processing

**Upload v2 Features**:
- Serial upload queue prevents duplicate uploads
- WebSocket events provide real-time status updates
- Upload logs are written atomically to `{episode_id}_upload_log.json`

**Verify v2 Features**:
- Delayed verification (default: 180 seconds) reduces quota consumption
- Single verification query per video
- Work cursor updated only after successful verification

### Render Queue Sync Issues

**Symptoms**:
- Completed renders still in queue
- Ready episodes not appearing

**Solutions**:
```bash
# Manual sync
curl -X POST http://localhost:8000/api/t2r/render-queue-sync/sync-all \
  -H "Content-Type: application/json" \
  -d '{"channel_id": "kat_lofi"}'

# Check ready episodes
curl http://localhost:8000/api/t2r/render-queue-sync/ready-for-render?channel_id=kat_lofi
```

### Timeline CSV Missing

**Symptoms**: `{episode_id}_full_mix_timeline.csv` not generated

**Causes**:
- Remix stage failed or interrupted
- Playlist CSV format issue
- File write permission error

**Solutions**:
- Check remix stage completion
- Verify playlist.csv contains Timeline section
- Manually regenerate from playlist.csv if needed

---

## Common Issues & Fixes

### Frontend/Backend Inconsistency

**Problem**: Frontend shows void, backend folder exists

**Fix**: Ensure `playlist_path` saved in episode object, add file system fallback checks

### GridProgress Not Updating

**Problem**: Progress bar shows incorrect state

**Fix**: Unified `hasPlaylist` logic, adjusted `preparation.done` threshold (80%), fixed WebSocket updates

### Worker Exits Prematurely

**Problem**: Episode enqueued but not processed

**Fix**: Added retry mechanism (3 consecutive empty checks), 500ms delay between checks

### Async/Sync Mixing

**Problem**: File operations block event loop

**Fix**: Migrated all file operations to async, unified async utility functions

### Render Completion Detection

**Problem**: Video rendered but not detected as complete

**Fix**: Use `ffprobe` validation as primary check, `render_complete_flag` as confirmation

---

**Related**: 
- [System Overview](01_SYSTEM_OVERVIEW.md)
- [Development Guide](03_DEVELOPMENT_GUIDE.md)
- [Upload Pipeline v2 Architecture](ARCHITECTURE_UPLOAD_V2.md)
- [Verify Pipeline v2 Architecture](ARCHITECTURE_VERIFY_V2.md)
- [Upload→Verify Lifecycle](LIFECYCLE_UPLOAD_VERIFY.md)
