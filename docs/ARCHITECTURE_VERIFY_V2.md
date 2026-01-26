# Verify Pipeline v2 Architecture

**Generated**: 2025-01-XX  
**Version**: 2.0  
**Status**: Production

## Overview

Verify Pipeline v2 implements delayed verification to reduce YouTube API quota consumption. Instead of polling every 5 seconds (720 queries/hour), it waits for a configurable delay (default: 180 seconds) then performs a single `videos.list` query (1 unit).

## Core Components

### 1. VerifyWorker (`kat_rec_web/backend/t2r/services/verify_worker.py`)

**Purpose**: Background worker for delayed video verification

**Key Features**:
- Configurable delay before verification (default: 180 seconds)
- Single `videos.list` query per video (1 unit vs 720 units/hour)
- Prevents duplicate verification
- Async task queue
- Automatic work cursor update after successful verification

**Architecture**:
```
VerifyWorker (Singleton)
├── _tasks: Dict[str, VerifyTask]
├── _lock: asyncio.Lock
└── _worker_task: Optional[asyncio.Task]
```

**VerifyTask Structure**:
```python
@dataclass
class VerifyTask:
    episode_id: str
    channel_id: str
    video_id: str
    scheduled_at: datetime
    delay_seconds: int
```

### 2. Verification Flow

```
1. Upload completes → VerifyWorker.schedule_verify()
   ↓
2. Task scheduled with delay (default: 180s)
   ↓
3. VerifyWorker._worker_loop() checks for ready tasks
   ↓
4. VerifyWorker._execute_verify(task)
   ↓
5. _verify_via_videos_list(video_id) → YouTube API
   ↓
6. _update_upload_log() → Update log with verification result
   ↓
7. _update_work_cursor() → Update work cursor (if verified)
   ↓
8. _emit_verification_event() → WebSocket broadcast
```

## State Transitions

### Verification States

| State | Description | WebSocket Event |
|-------|-------------|-----------------|
| `verifying` | Verification in progress | `upload_state_changed` |
| `verified` | Verification complete | `upload_state_changed` |
| `failed` | Verification failed | `upload_state_changed` |

### State Flow

```
uploaded → verifying → verified
                    ↓
                 failed
```

## Verification Process

### 1. Scheduling

**Method**: `schedule_verify(episode_id, channel_id, video_id, delay_seconds=180)`

**Behavior**:
- Prevents duplicate verification (checks `_tasks` dict)
- Creates `VerifyTask` with scheduled timestamp
- Starts worker loop if not running
- Returns immediately (non-blocking)

### 2. Worker Loop

**Method**: `_worker_loop()`

**Behavior**:
- Checks every 10 seconds for ready tasks
- Task is "ready" when `elapsed >= delay_seconds`
- Executes ready tasks sequentially
- Stops when no more tasks

### 3. Verification Execution

**Method**: `_execute_verify(task)`

**Steps**:
1. Emit `verifying` event (WebSocket)
2. Call `_verify_via_videos_list(video_id)`
3. If verified:
   - Update upload log (`state="verified"`)
   - Update work cursor via `verify_and_update_work_cursor()`
   - Emit `verified` event (WebSocket)
4. If failed:
   - Update upload log (`state="failed"`)
   - Emit `failed` event (WebSocket)

### 4. YouTube API Verification

**Method**: `_verify_via_videos_list(video_id)`

**API Call**: `youtube.videos().list(part="id,snippet,status", id=video_id)`

**Quota Cost**: 1 unit (vs 720 units/hour for polling)

**Checks**:
- Video exists on YouTube
- `uploadStatus == "processed"`

**Returns**: `(is_verified: bool, errors: List[str], video_info: Optional[Dict])`

## Upload Log Updates

**Method**: `_update_upload_log(channel_id, episode_id, video_id, verified, errors)`

**Uses**: `_write_upload_log()` from `upload.py` (unified wrapper)

**Updates**:
- `state`: "verified" or "failed"
- `verified`: bool
- `verified_at`: ISO timestamp
- `error`: Optional[str] (if failed)
- `errors`: Optional[List[str]] (if failed)

**Preserves**: Existing fields (upload_id, video_file, video_url, etc.)

## Work Cursor Update

**Method**: `_update_work_cursor(task)`

**Integration**: Calls `verify_and_update_work_cursor()` from `upload_verification.py`

**Behavior**:
- Only updates work cursor if verification succeeds
- Uses `use_youtube_api=False` (already verified via videos.list)
- Fetches `schedule_date` from schedule master
- Updates work cursor date to episode's schedule date

**Result**:
- Work cursor advances only after successful verification
- Prevents premature cursor advancement

## WebSocket Events

**Event Type**: `upload_state_changed`

**States**:
- `verifying`: Verification started
- `verified`: Verification successful
- `failed`: Verification failed

**Payload**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "verified",
  "video_id": "abc123xyz",
  "errors": null,
  "timestamp": "2025-01-XXT12:37:56.789Z"
}
```

**Broadcast Function**: `broadcast_upload_state_changed()` in `websocket_events.py`

## API Endpoints

### POST /api/t2r/upload/verify

**⚠️ DEPRECATED**: This endpoint is kept for backward compatibility. New code should use VerifyWorker directly.

**Request**:
```json
{
  "episode_id": "20251117",
  "video_id": "abc123xyz",
  "platform": "youtube",
  "channel_id": "kat_lofi"
}
```

**Response**:
```json
{
  "status": "ok",
  "episode_id": "20251117",
  "video_id": "abc123xyz",
  "checks": [
    {
      "name": "verification_scheduled",
      "status": "passed",
      "message": "Verification scheduled (delay: 180s)"
    }
  ],
  "all_passed": true,
  "verified": false,
  "message": "Verification scheduled via VerifyWorker (delay: 180s)",
  "timestamp": "2025-01-XXT12:34:56.789Z"
}
```

**Behavior**: Schedules verification via VerifyWorker (does not perform immediate verification)

## Configuration

### Verify Delay

**Config**: `config/config.yaml`
```yaml
youtube:
  verify_delay_seconds: 180  # Default: 3 minutes
```

**Rationale**:
- YouTube processes uploads asynchronously
- Immediate verification may fail (video not yet processed)
- 180 seconds is sufficient for most videos
- Configurable for different video sizes

## Integration Points

### Upload Queue Integration

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

### Upload Verification Service Integration

**File**: `kat_rec_web/backend/t2r/services/upload_verification.py`

After verification succeeds:
```python
from ..services.upload_verification import verify_and_update_work_cursor
result = await verify_and_update_work_cursor(
    channel_id=task.channel_id,
    episode_id=task.episode_id,
    schedule_date=schedule_date,
    use_youtube_api=False  # Already verified via videos.list
)
```

## Error Handling

### Duplicate Verification Prevention

- `schedule_verify()` checks `_tasks` dict
- Returns early if episode already scheduled
- Prevents duplicate verification tasks

### Verification Failures

- Errors are caught in `_execute_verify()`
- Upload log is updated with `state="failed"`
- WebSocket event is broadcast with `state="failed"`
- Work cursor is NOT updated on failure

### YouTube API Errors

- Network errors: Retry not implemented (future improvement)
- Quota errors: Logged and broadcast as failure
- Video not found: Broadcast as failure

## Performance Considerations

### Quota Optimization

**Before (Polling)**:
- Poll every 5 seconds: 720 queries/hour
- Quota cost: 720 units/hour per video

**After (Delayed Verification)**:
- Single query after delay: 1 query per video
- Quota cost: 1 unit per video
- **Reduction**: 99.86% quota savings

### Delay Strategy

- Default: 180 seconds (3 minutes)
- Configurable via `youtube.verify_delay_seconds`
- Sufficient for most video sizes
- Can be adjusted for larger videos

## Dependencies

- `asyncio`: Async task queue
- `scripts.uploader.upload_to_youtube`: YouTube API client
- `kat_rec_web.backend.t2r.routes.upload`: `_write_upload_log()` wrapper
- `kat_rec_web.backend.t2r.services.upload_verification`: Work cursor update
- `kat_rec_web.backend.t2r.websocket_events`: WebSocket broadcasting

## Future Improvements

1. **Retry Logic**: Automatic retry for transient failures
2. **Adaptive Delay**: Adjust delay based on video size
3. **Batch Verification**: Verify multiple videos in single API call
4. **Verification Status API**: Query verification status without polling

