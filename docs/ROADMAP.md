# Roadmap & Future Plans

**Last Updated**: 2025-11-02  
**Status**: Active Planning

---

## 🎯 P0 Tasks (1-2 weeks, Must Complete)

### ✅ 1. DEMO Logic Removal (Completed)

- ✅ Removed all DEMO-related code
- ✅ Unified output directory structure
- ✅ Updated all references

**Status**: ✅ Completed

---

### ✅ 2. YouTube Upload MVP (Completed)

**Goal**: Implement complete YouTube upload pipeline, close publishing loop

**Status**: ✅ Completed (2025-11-02)

**Functional Requirements**:
- ✅ OAuth local callback flow
- ✅ Token persistence and automatic refresh
- ✅ Chunked upload (supports large files)
- ✅ Failure retry mechanism (exponential backoff)
- ✅ Quota awareness and rate limiting
- ✅ Status tracking (write back to schedule_master.json)

**Deliverables**:
- ✅ `scripts/uploader/upload_to_youtube.py` - Complete Stage 10 upload script
- ✅ `scripts/local_picker/youtube_auth.py` - OAuth authentication
- ✅ `config/workflow.yml` - Stage 10 workflow definition
- ✅ `config/config.example.yaml` - YouTube configuration template
- ✅ State machine: `uploading` state handling integrated
- ✅ Event bus: `UPLOAD_STARTED`, `UPLOAD_COMPLETED`, `UPLOAD_FAILED` events
- ✅ CLI integration: `kat upload` command
- ✅ Documentation updates: ARCHITECTURE.md, ROADMAP.md

**Technical Stack**:
- Google API Client Library (`google-api-python-client`)
- OAuth 2.0 (`google-auth-oauthlib`)
- Chunked Upload (Resumable Upload)
- Structured JSON logging

**Usage Example**:
```bash
# CLI
python scripts/kat_cli.py upload --episode 20251102

# Direct
python scripts/uploader/upload_to_youtube.py \
  --episode 20251102 \
  --video output/20251102_youtube.mp4
```

---

### 3. Unified Logging & Exception Handling

**Goal**: Unify all modules' logging and exception handling to JSON structured output

**Functional Requirements**:
- [ ] Unified logger factory (extend `src/core/logger.py`)
  - JSON format output
  - Fields: `level, ts, module, episode_id, action, latency, err_code`
- [ ] Daily rotation
- [ ] Console and file dual channels
- [ ] Fatal errors trigger "rollback + mark error"
- [ ] Unified exception handling pattern

**Deliverables**:
- Update `src/core/logger.py` with enhanced features
- `config/logging.yaml`
- Migrate all modules to use unified logger

---

### 4. Configuration Consolidation

**Goal**: All scripts use unified configuration entry point

**Current Status**:
- ✅ `src/configuration.py` unified configuration framework exists
- ✅ Supports `config/config.yaml`
- ⚠️ Need to ensure all scripts migrate to unified configuration

**Tasks**:
- [x] Create `config/config.example.yaml` template
- [ ] Create `scripts/install.sh` one-click initialization script
- [ ] Migrate all scripts to use `AppConfig.load()`
- [ ] Documentation updates

---

### 5. Core Smoke Tests

**Goal**: Test coverage for critical workflow paths

**Test Requirements**:
- [ ] Single episode full workflow (title→cover→mix→render)
- [ ] Batch generation workflow
- [ ] Recovery/retry workflow
- [ ] State machine transition tests (pending→remixing→rendering→completed/error)

**Deliverables**:
- `tests/test_workflow_golden_paths.py`
- Extend `tests/test_consistency.py`

---

## 📋 P1 Tasks (2-6 weeks)

### 1. Parallelization & Caching

- Multi-process mixing/rendering
- Cover and title generation result caching
- Idempotency keys (episode_id + stage)
- Automatic retry on failure (limit + circuit breaker)

### 2. Quality Gate

- Cover/description/title normalization validators
- Post-generation scoring and rejection mechanism

### 3. Observability

- Metrics: Throughput (episodes/day), failure rate, average latency, render CPU/GPU utilization, upload success rate
- Export CSV reports

---

## 🚀 P2 Tasks (>6 weeks)

### 1. Theming Engine & Tag System

- Holiday/emotion filters
- Theme cover template library
- A/B testing

### 2. Mobile/Management Interface

- Mobile-friendly dashboard
- Remote trigger and preview

### 3. Community & Ecosystem

- Template marketplace
- Library collaboration
- Automated reporting

---

## 📊 Priority Assessment

### High (Immediate)

- **Publishing closure**: YouTube upload missing → Cannot verify end-to-end stability and rhythm
- **Exception/logging/tests**: Hard threshold before parallelization
- **Configuration scatter**: Different scripts read different configuration points

### Medium (Near-term)

- **Stage 11: Auto Playlist Integration** - Automatically add uploaded videos to YouTube playlists
- **Stage 12: Analytics Reporting** - Track views, engagement metrics via YouTube Analytics API
- **Stage 13: Comment Pinning & Metadata Sync** - Auto-pin comments, sync metadata updates
- **Stage 14: Auto Scheduling** - Integration with n8n / cron for scheduled uploads

**Technical Debt**:
- Cascading failures after parallelization (no idempotency and retry limits)
- Quota/rate/window management (mismatch between upload and generation rhythm)

### Low (Later)

- **Mobile and community features** (no immediate impact on capacity)

---

## 🔗 Related Documents

- [Development Log](./DEVELOPMENT.md) - Recent development achievements
- [Architecture](./ARCHITECTURE.md) - System architecture
- [System Health Report](./archive/system_health_report.md) - Detailed health analysis

---

**Last Updated**: 2025-11-02

