# Upload Pipeline v2 Architecture

**Generated**: 2025-01-XX  
**Version**: 2.0  
**Status**: Production

## Overview

Upload Pipeline v2 is a serialized, queue-based upload system designed to prevent duplicate uploads, reduce YouTube API quota consumption, and provide real-time status updates via WebSocket.

## Core Components

### 1. UploadQueue (`kat_rec_web/backend/t2r/services/upload_queue.py`)

**Purpose**: Strictly serial upload queue manager

**Key Features**:
- Serial execution (one upload at a time)
- Prevents duplicate uploads for same episode
- Tracks upload state per episode
- Async task queue

**Architecture**:
```
UploadQueue (Singleton)
├── _queue: asyncio.Queue[UploadTask]
├── _lock: asyncio.Lock
├── _uploading: Dict[str, bool]  # episode_id -> is_uploading
├── _uploaded: Dict[str, bool]   # episode_id -> is_uploaded
└── _worker_task: Optional[asyncio.Task]
```

**State Machine**:
```
episode_id
  ├── Not in queue → enqueue_upload() → queued
  ├── Already uploading → ValueError
  ├── Already uploaded → ValueError
  └── queued → _process_upload_queue() → uploading → uploaded/failed
```

**Methods**:
- `enqueue_upload(episode_id, channel_id, video_file, metadata) -> str`: Enqueue upload task
- `_process_upload_queue()`: Main worker loop (serial execution)
- `_execute_upload(task)`: Execute single upload task
- `_emit_upload_event()`: Broadcast WebSocket events

### 2. Upload Routes (`kat_rec_web/backend/t2r/routes/upload.py`)

**Endpoints**:
- `POST /api/t2r/upload/start`: Start upload (enqueues to UploadQueue)
- `GET /api/t2r/upload/status`: Get upload status (deprecated, prefers WebSocket)
- `POST /api/t2r/upload/full`: Full upload with manifest updates
- `POST /api/t2r/upload/verify`: Schedule verification (deprecated, uses VerifyWorker)

**Key Helpers**:
- `_write_upload_log()`: Unified upload log writer (atomic write)
- `_persist_upload_log()`: Legacy wrapper for backward compatibility
- `_enqueue_serial_upload()`: Enqueue via UploadQueue
- `_execute_upload_task()`: Execute upload (called by UploadQueue)
- `_compute_publish_plan()`: Compute publish schedule (timezone-aware)
- `_update_manifest_and_emit()`: Update manifest + emit WebSocket event

### 3. Upload Task Execution Flow

```
1. Frontend calls POST /api/t2r/upload/start
   ↓
2. _enqueue_serial_upload() → UploadQueue.enqueue_upload()
   ↓
3. UploadQueue._process_upload_queue() (worker loop)
   ↓
4. UploadQueue._execute_upload(task)
   ↓
5. Calls _execute_upload_task() from upload.py
   ↓
6. upload_video() (YouTube API)
   ↓
7. _persist_upload_log() → _write_upload_log()
   ↓
8. broadcast_upload_state_changed() (WebSocket)
   ↓
9. VerifyWorker.schedule_verify() (if successful)
```

## State Transitions

### Upload States

| State | Description | WebSocket Event |
|-------|-------------|-----------------|
| `queued` | Task enqueued, waiting for processing | `upload_state_changed` |
| `uploading` | Currently uploading to YouTube | `upload_state_changed` |
| `uploaded` | Upload complete, waiting for verification | `upload_state_changed` |
| `verifying` | Verification in progress | `upload_state_changed` |
| `verified` | Verification complete | `upload_state_changed` |
| `failed` | Upload or verification failed | `upload_state_changed` |

### State Flow

```
queued → uploading → uploaded → verifying → verified
                              ↓
                           failed (at any stage)
```

## Upload Log Format

**File**: `channels/{channel_id}/output/{episode_id}/{episode_id}_upload_log.json`

**Standard Fields** (required):
- `episode_id`: str
- `channel_id`: str
- `state`: "queued" | "uploading" | "uploaded" | "verifying" | "verified" | "failed"
- `video_id`: Optional[str]
- `error`: Optional[str] (single-line error message)
- `errors`: List[str] (detailed error list)

**Optional Fields**:
- `upload_id`: Optional[str]
- `video_file`: Optional[str]
- `video_url`: Optional[str]
- `status`: "completed" | "failed" | "in_progress" (backward compatibility)
- `verified`: Optional[bool]
- `verified_at`: Optional[str] (ISO timestamp)
- `created_at`: Optional[str] (ISO timestamp)
- `completed_at`: Optional[str] (ISO timestamp)

**Writer**: `_write_upload_log()` (uses atomic write for safety)

## WebSocket Events

**Event Type**: `upload_state_changed`

**Payload**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "uploaded",
  "upload_id": "upload_20251117_1234567890",
  "video_id": "abc123xyz",
  "error": null,
  "errors": null,
  "timestamp": "2025-01-XXT12:34:56.789Z"
}
```

**Broadcast Function**: `broadcast_upload_state_changed()` in `websocket_events.py`

## API Endpoints

### POST /api/t2r/upload/start

**Request**:
```json
{
  "episode_id": "20251117",
  "video_file": "channels/kat_lofi/output/20251117/20251117_youtube.mp4",
  "metadata": {
    "title": "Episode Title",
    "description": "Episode Description",
    "channel_id": "kat_lofi"
  }
}
```

**Response**:
```json
{
  "status": "ok",
  "upload_id": "upload_20251117_1234567890",
  "episode_id": "20251117",
  "progress": 0.0,
  "timestamp": "2025-01-XXT12:34:56.789Z",
  "publish_plan": {
    "mode": "scheduled",
    "privacy_status": "private",
    "publish_at_iso": "2025-01-XXT23:00:00.000Z",
    "local_display": "2025-01-XXT23:00:00+08:00",
    "timezone": "Asia/Shanghai"
  }
}
```

### POST /api/t2r/upload/full

**Request**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "video_file": "channels/kat_lofi/output/20251117/20251117_youtube.mp4",
  "metadata": {},
  "poll_interval": 2.0,
  "max_poll_time": 600.0
}
```

**Response**:
```json
{
  "status": "ok",
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "upload_id": "upload_20251117_1234567890",
  "video_id": "abc123xyz",
  "video_url": "https://www.youtube.com/watch?v=abc123xyz",
  "verified": false,
  "upload_log_path": "channels/kat_lofi/output/20251117/20251117_upload_log.json",
  "message": "Upload completed",
  "errors": [],
  "publish_plan": {...},
  "verification_result": {
    "status": "scheduled",
    "message": "Verification scheduled via VerifyWorker"
  },
  "timestamp": "2025-01-XXT12:34:56.789Z"
}
```

## Integration Points

### Render Queue Integration

**File**: `kat_rec_web/backend/t2r/services/render_queue.py`

After render completes:
```python
upload_queue = get_upload_queue()
upload_id = await upload_queue.enqueue_upload(
    episode_id=episode_id,
    channel_id=channel_id,
    video_file=str(video_file),
    metadata=metadata
)
```

### Verify Worker Integration

After upload completes:
```python
from ..services.verify_worker import get_verify_worker
verify_worker = get_verify_worker()
await verify_worker.schedule_verify(
    episode_id=episode_id,
    channel_id=channel_id,
    video_id=video_id,
    delay_seconds=180
)
```

## Error Handling

### Duplicate Upload Prevention

- `UploadQueue.enqueue_upload()` checks `_uploading` and `_uploaded` dicts
- Raises `ValueError` if episode is already uploading or uploaded
- Prevents race conditions with `asyncio.Lock`

### Upload Failures

- Errors are caught in `_execute_upload_task()`
- Upload log is written with `state="failed"`
- WebSocket event is broadcast with `state="failed"`
- Episode can be retried (not marked as uploaded on failure)

## Performance Considerations

### Serial Execution

- Only one upload at a time (prevents YouTube API quota exhaustion)
- Queue-based processing (non-blocking enqueue)
- Worker loop processes tasks sequentially

### Atomic Log Writing

- Uses `atomic_write_json()` from `utils/atomic_write.py`
- Temporary file + rename for atomicity
- Prevents partial log writes on crashes

## Configuration

### YouTube API

**Config**: `config/config.yaml`
```yaml
youtube:
  client_secrets_file: config/google/client_secrets.json
  token_file: config/google/youtube_token.json
  playlist_id: PLAn_Q-OQCpRLeHEWW4gf9EjZyTiwCfcaH
  verify_delay_seconds: 180
  upload_defaults:
    categoryId: 10
    privacyStatus: unlisted
    tags:
    - lofi
    - music
```

## Dependencies

- `asyncio`: Async queue management
- `scripts.uploader.upload_to_youtube`: YouTube upload logic
- `scripts.uploader.token_manager`: OAuth token management
- `scripts.uploader.upload_helpers`: Metadata update helpers
- `kat_rec_web.backend.t2r.services.verify_worker`: Verification scheduling
- `kat_rec_web.backend.t2r.websocket_events`: WebSocket broadcasting

## Future Improvements

1. **Redis-backed Queue**: Replace in-memory queue with Redis for persistence
2. **Retry Logic**: Automatic retry for transient failures
3. **Priority Queue**: Support priority-based upload ordering
4. **Multi-Channel Queues**: Separate queues per channel for parallel processing

