# End-to-End Upload→Verify→Manifest→WebSocket Lifecycle

**Generated**: 2025-01-XX  
**Version**: 2.0  
**Status**: Production

## Overview

This document describes the complete lifecycle of an episode from upload initiation through verification, manifest updates, and WebSocket event broadcasting.

## Lifecycle Stages

### Stage 1: Upload Initiation

**Trigger**: Frontend calls `POST /api/t2r/upload/start` or render queue completes

**Components**:
- `upload.py`: `start_upload()` endpoint
- `upload.py`: `_enqueue_serial_upload()` helper
- `upload_queue.py`: `UploadQueue.enqueue_upload()`

**Flow**:
```
1. Frontend/Backend → POST /api/t2r/upload/start
   ↓
2. _compute_publish_plan() → Calculate publish schedule
   ↓
3. _enqueue_serial_upload() → Enqueue to UploadQueue
   ↓
4. UploadQueue.enqueue_upload() → Create UploadTask
   ↓
5. broadcast_upload_state_changed(state="queued") → WebSocket
```

**Manifest Update**: None (upload not started yet)

**WebSocket Event**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "queued",
  "upload_id": "upload_20251117_1234567890",
  "timestamp": "2025-01-XXT12:34:00.000Z"
}
```

### Stage 2: Upload Processing

**Trigger**: UploadQueue worker picks up task from queue

**Components**:
- `upload_queue.py`: `_process_upload_queue()` worker loop
- `upload_queue.py`: `_execute_upload()` method
- `upload.py`: `_execute_upload_task()` function

**Flow**:
```
1. UploadQueue._process_upload_queue() → Get next task
   ↓
2. UploadQueue._execute_upload(task) → Execute upload
   ↓
3. _execute_upload_task() → Upload to YouTube
   ↓
4. broadcast_upload_state_changed(state="uploading") → WebSocket
   ↓
5. upload_video() → YouTube API (resumable upload)
   ↓
6. _persist_upload_log() → Write upload log
   ↓
7. broadcast_upload_state_changed(state="uploaded") → WebSocket
```

**Manifest Update**: 
- `ManifestStatus.UPLOADING` (via `_update_manifest_and_emit()`)
- `ManifestStatus.UPLOADED` (after successful upload)

**Upload Log**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "upload_id": "upload_20251117_1234567890",
  "video_id": "abc123xyz",
  "video_url": "https://www.youtube.com/watch?v=abc123xyz",
  "state": "uploaded",
  "status": "completed",
  "created_at": "2025-01-XXT12:34:00.000Z",
  "completed_at": "2025-01-XXT12:35:30.000Z"
}
```

**WebSocket Events**:
```json
// Uploading
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "uploading",
  "upload_id": "upload_20251117_1234567890",
  "timestamp": "2025-01-XXT12:34:10.000Z"
}

// Uploaded
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "uploaded",
  "upload_id": "upload_20251117_1234567890",
  "video_id": "abc123xyz",
  "timestamp": "2025-01-XXT12:35:30.000Z"
}
```

### Stage 3: Verification Scheduling

**Trigger**: Upload completes successfully

**Components**:
- `upload.py`: `_execute_upload_task()` (after upload)
- `verify_worker.py`: `VerifyWorker.schedule_verify()`

**Flow**:
```
1. _execute_upload_task() → Upload complete
   ↓
2. VerifyWorker.schedule_verify() → Schedule verification
   ↓
3. VerifyTask created with delay (180s)
   ↓
4. VerifyWorker._worker_loop() started (if not running)
```

**Manifest Update**: None (verification not started yet)

**WebSocket Event**: None (verification scheduled, not started)

### Stage 4: Verification Processing

**Trigger**: VerifyWorker worker loop detects ready task (delay elapsed)

**Components**:
- `verify_worker.py`: `_worker_loop()` worker loop
- `verify_worker.py`: `_execute_verify()` method
- `verify_worker.py`: `_verify_via_videos_list()` method

**Flow**:
```
1. VerifyWorker._worker_loop() → Check for ready tasks
   ↓
2. VerifyWorker._execute_verify(task) → Execute verification
   ↓
3. broadcast_upload_state_changed(state="verifying") → WebSocket
   ↓
4. _verify_via_videos_list(video_id) → YouTube API
   ↓
5. _update_upload_log() → Update log with verification result
   ↓
6. _update_work_cursor() → Update work cursor (if verified)
   ↓
7. broadcast_upload_state_changed(state="verified") → WebSocket
```

**Manifest Update**: None (manifest updated during upload stage)

**Upload Log Update**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "upload_id": "upload_20251117_1234567890",
  "video_id": "abc123xyz",
  "state": "verified",
  "status": "completed",
  "verified": true,
  "verified_at": "2025-01-XXT12:38:30.000Z"
}
```

**WebSocket Events**:
```json
// Verifying
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "verifying",
  "video_id": "abc123xyz",
  "timestamp": "2025-01-XXT12:38:00.000Z"
}

// Verified
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "verified",
  "video_id": "abc123xyz",
  "timestamp": "2025-01-XXT12:38:30.000Z"
}
```

### Stage 5: Work Cursor Update

**Trigger**: Verification succeeds

**Components**:
- `verify_worker.py`: `_update_work_cursor()` method
- `upload_verification.py`: `verify_and_update_work_cursor()` function
- `schedule_service.py`: `update_work_cursor_date()` function

**Flow**:
```
1. _update_work_cursor(task) → Update work cursor
   ↓
2. verify_and_update_work_cursor() → Unified work cursor logic
   ↓
3. update_work_cursor_date() → Update schedule master
```

**Manifest Update**: None (work cursor is separate from manifest)

**WebSocket Event**: None (work cursor update is internal)

## Complete Timeline Example

**Episode**: 20251117  
**Channel**: kat_lofi  
**Video File**: `channels/kat_lofi/output/20251117/20251117_youtube.mp4`

### Timeline

| Time | Stage | Action | WebSocket Event | Manifest |
|------|-------|--------|-----------------|----------|
| 12:34:00 | Initiation | Upload queued | `queued` | - |
| 12:34:10 | Upload | Upload started | `uploading` | `UPLOADING` |
| 12:35:30 | Upload | Upload complete | `uploaded` | `UPLOADED` |
| 12:35:30 | Verification | Verification scheduled | - | - |
| 12:38:00 | Verification | Verification started | `verifying` | - |
| 12:38:30 | Verification | Verification complete | `verified` | - |
| 12:38:30 | Work Cursor | Work cursor updated | - | - |

**Total Duration**: ~4.5 minutes (upload: ~1.5 min, verification delay: 3 min, verification: ~30s)

## Error Scenarios

### Upload Failure

**Flow**:
```
1. Upload fails (network error, quota exceeded, etc.)
   ↓
2. _execute_upload_task() catches exception
   ↓
3. _persist_upload_log(state="failed") → Write failure log
   ↓
4. broadcast_upload_state_changed(state="failed") → WebSocket
   ↓
5. Manifest updated: ManifestStatus.UPLOAD_FAILED
```

**Upload Log**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "failed",
  "status": "failed",
  "error": "YouTube 每日上传配额已用完。请明天再试，或分批上传。",
  "errors": ["uploadLimitExceeded"]
}
```

**WebSocket Event**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "failed",
  "upload_id": "upload_20251117_1234567890",
  "error": "YouTube 每日上传配额已用完。请明天再试，或分批上传。",
  "timestamp": "2025-01-XXT12:35:30.000Z"
}
```

### Verification Failure

**Flow**:
```
1. Verification fails (video not found, not processed, etc.)
   ↓
2. _execute_verify() catches failure
   ↓
3. _update_upload_log(state="failed", verified=false) → Update log
   ↓
4. broadcast_upload_state_changed(state="failed") → WebSocket
   ↓
5. Work cursor NOT updated (verification failed)
```

**Upload Log Update**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "video_id": "abc123xyz",
  "state": "failed",
  "verified": false,
  "error": "Video upload status is 'processing', expected 'processed'",
  "errors": ["Video upload status is 'processing', expected 'processed'"]
}
```

**WebSocket Event**:
```json
{
  "episode_id": "20251117",
  "channel_id": "kat_lofi",
  "state": "failed",
  "video_id": "abc123xyz",
  "error": "Video upload status is 'processing', expected 'processed'",
  "errors": ["Video upload status is 'processing', expected 'processed'"],
  "timestamp": "2025-01-XXT12:38:30.000Z"
}
```

## State Machine Diagram

```
                    [Upload Initiated]
                           |
                           v
                       [queued]
                           |
                           v
                    [uploading]
                           |
                +-----------+-----------+
                |                       |
                v                       v
          [uploaded]              [failed]
                |
                v
        [Verification Scheduled]
                |
                v
            [verifying]
                |
        +-------+-------+
        |               |
        v               v
   [verified]      [failed]
        |
        v
  [Work Cursor Updated]
```

## Frontend Integration

### WebSocket Event Handling

**File**: `kat_rec_web/frontend/hooks/useWebSocket.ts`

**Handler**:
```typescript
if (baseType === 'upload_state_changed') {
  const uploadState = {
    state: data.state || 'pending',
    upload_id: data.upload_id,
    video_id: data.video_id,
    error: data.error,
    errors: data.errors,
    timestamp: data.timestamp || new Date().toISOString(),
  }
  
  patchEvent(episodeId, { uploadState })
  
  // Update assets when upload/verification completes
  if (data.state === 'uploaded' && data.video_id) {
    patchEvent(episodeId, {
      assets: {
        ...currentEvent?.assets,
        uploaded: true,
        uploaded_at: data.timestamp,
      }
    })
  }
  
  if (data.state === 'verified' && data.video_id) {
    patchEvent(episodeId, {
      assets: {
        ...currentEvent?.assets,
        verified: true,
        verified_at: data.timestamp,
      }
    })
  }
}
```

### UI Updates

**GridProgressIndicator**: Shows upload/verification progress based on `uploadState`

**TaskPanel**: Displays detailed upload/verification status

**OverviewGrid**: Shows upload icon when ready, updates via WebSocket

## Key Design Decisions

### 1. Serial Upload Queue

**Rationale**: Prevents YouTube API quota exhaustion

**Trade-off**: Slower batch uploads, but more reliable

### 2. Delayed Verification

**Rationale**: Reduces quota consumption from 720 units/hour to 1 unit per video

**Trade-off**: 3-minute delay, but 99.86% quota savings

### 3. Unified Log Format

**Rationale**: Consistent log structure across upload and verification

**Trade-off**: Backward compatibility with legacy "status" field

### 4. WebSocket over Polling

**Rationale**: Real-time updates, no polling overhead

**Trade-off**: Requires WebSocket connection, but better UX

## Monitoring and Debugging

### Upload Log Files

**Location**: `channels/{channel_id}/output/{episode_id}/{episode_id}_upload_log.json`

**Use Cases**:
- Debugging upload failures
- Checking verification status
- Auditing upload history

### WebSocket Events

**Event Type**: `upload_state_changed`

**Monitoring**: Check browser console for WebSocket messages

### Manifest Status

**Location**: `channels/{channel_id}/output/{episode_id}/manifest.json`

**Status Values**:
- `UPLOADING`: Upload in progress
- `UPLOADED`: Upload complete
- `UPLOAD_FAILED`: Upload failed

## Future Enhancements

1. **Retry Logic**: Automatic retry for transient failures
2. **Progress Tracking**: Real-time upload progress percentage
3. **Batch Operations**: Support for batch upload/verification
4. **Metrics**: Upload/verification success rate tracking

