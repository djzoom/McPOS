# YouTube Upload Guide

**Stage 10**: YouTube Video Upload System  
**Last Updated**: 2025-11-02

---

## 🎯 Overview

Stage 10 automatically uploads rendered videos to YouTube, updates `schedule_master.json` with video IDs, and logs all events in structured JSON format.

---

## ⚙️ Setup

### 1. OAuth Configuration

1. **Create Google Cloud Project**:
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing

2. **Enable YouTube Data API v3**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"

3. **Create OAuth 2.0 Credentials**:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client ID"
   - Application type: "Desktop app"
   - Download JSON file
   - Save as: `config/google/client_secrets.json`

### 2. Initial Authorization

Run the setup wizard:

```bash
python scripts/local_picker/youtube_auth.py --setup
```

Or let the upload script handle it automatically on first run.

---

## 📖 Usage

### CLI Command

```bash
# Basic upload (auto-detects files)
python scripts/kat_cli.py upload --episode 20251102

# With explicit file paths
python scripts/kat_cli.py upload \
  --episode 20251102 \
  --video output/20251102_youtube.mp4 \
  --title-file output/20251102_youtube_title.txt \
  --desc-file output/20251102_youtube_description.txt

# Override privacy settings
python scripts/kat_cli.py upload --episode 20251102 --privacy public

# Force re-upload (even if already uploaded)
python scripts/kat_cli.py upload --episode 20251102 --force
```

### Direct Script Call

```bash
python scripts/uploader/upload_to_youtube.py \
  --episode 20251102 \
  --video output/20251102_youtube.mp4 \
  --title-file output/20251102_youtube_title.txt \
  --desc-file output/20251102_youtube_description.txt
```

---

## ⚙️ Configuration

Edit `config/config.yaml`:

```yaml
youtube:
  client_secrets_file: "config/google/client_secrets.json"
  token_file: "config/google/youtube_token.json"
  upload_defaults:
    privacyStatus: "unlisted"  # Options: private, unlisted, public
    categoryId: 10  # Music category
    tags:
      - "lofi"
      - "music"
      - "Kat Records"
      - "chill"
  quota_limit_daily: 9000  # Daily API quota limit
```

---

## 📁 File Structure

### Required Input Files

- `{episode_id}_youtube.mp4` - Video file
- `{episode_id}_youtube_title.txt` - Video title (auto-detected)
- `{episode_id}_youtube_description.txt` - Video description (auto-detected)
- `{episode_id}_youtube.srt` - Subtitle file (optional, auto-uploaded if exists)
- `{episode_id}_cover.png` - Thumbnail (optional, auto-uploaded if exists)

### Output Files

- `{episode_id}_youtube_upload.json` - Upload result metadata:
  ```json
  {
    "video_id": "abc123xyz",
    "video_url": "https://www.youtube.com/watch?v=abc123xyz",
    "upload_time": "2025-11-02T18:30:00",
    "duration_seconds": 42.5,
    "episode_id": "20251102"
  }
  ```

### State Updates

`schedule_master.json` is automatically updated with:
- `youtube_video_id`: YouTube video ID
- `youtube_video_url`: Full YouTube URL
- `youtube_uploaded_at`: ISO timestamp

---

## 🔄 Workflow Integration

### Automatic State Transitions

```
Video Render Complete
  → State: "rendering" → "uploading"
  → Event: UPLOAD_STARTED

Upload Complete
  → State: "uploading" → "completed"
  → Event: UPLOAD_COMPLETED
  → Updates: youtube_video_id, youtube_video_url

Upload Failed
  → State: "uploading" → "error"
  → Event: UPLOAD_FAILED
```

### Workflow Console

Stage 10 can be executed from the workflow console:
- Select stage "10_youtube_upload"
- Or run: `run_stage("10_youtube_upload")`

---

## 📊 Logging

All upload events are logged to `logs/katrec.log` in JSON format:

```json
{"event":"upload","episode":"20251102","status":"started","timestamp":"2025-11-02T18:30:00"}
{"event":"upload","episode":"20251102","status":"completed","video_id":"abc123","video_url":"https://www.youtube.com/watch?v=abc123","latency":42.5}
```

---

## 🔧 Features

### 1. Resumable Upload

Large files (>256MB) are automatically chunked and uploaded using resumable upload protocol.

### 2. Retry Mechanism

Automatic retry with exponential backoff:
- Maximum 5 retry attempts
- Wait time: `2^n` seconds (1s, 2s, 4s, 8s, 16s)

### 3. Idempotent

Skips upload if `youtube_video_id` already exists in `schedule_master.json`. Use `--force` to override.

### 4. Automatic Metadata

- Auto-detects title and description files
- Auto-uploads subtitles if `.srt` exists
- Auto-uploads thumbnail if `_cover.png` exists

### 5. Quota Awareness

Tracks daily API quota usage (default: 9000 units/day). Fails gracefully with clear error message if quota exceeded.

---

## ❌ Error Handling

### Common Errors

1. **Authentication Failed**
   ```
   Error: Authentication failed. Please re-authorize.
   ```
   Solution: Run `python scripts/local_picker/youtube_auth.py --setup`

2. **Quota Exceeded**
   ```
   Error: API quota exceeded. Please try again tomorrow.
   ```
   Solution: Wait 24 hours or increase quota in Google Cloud Console

3. **Video File Not Found**
   ```
   Error: Video file not found: output/20251102_youtube.mp4
   ```
   Solution: Ensure video file exists or run Stage 9 (Video Rendering) first

### Recovery

On upload failure:
- State is set to "error"
- Can retry by running upload command again
- Automatic rollback available (configurable)

---

## 🔗 Related Documents

- [Architecture](./ARCHITECTURE.md) - System architecture overview
- [Roadmap](./ROADMAP.md) - Future improvements
- [CLI Reference](./cli_reference.md) - Command-line interface

---

**Status**: ✅ Production Ready (Stage 10 Complete)

