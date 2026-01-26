# Development Guide

**Last Updated**: 2025-01-XX  
**Status**: Active Development (Enhanced with Upload/Verify v2)

---

## Development Environment

### Prerequisites

- Python 3.11+
- Node.js 18+
- pnpm
- Rust (for Tauri app)
- FFmpeg

### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd Kat_Rec

# Python environment
python3 -m venv .venv311
source .venv311/bin/activate
pip install -e ".[dev]"

# Frontend environment
cd kat_rec_web/frontend
pnpm install
```

---

## Development Standards

### Code Style

**Python**:
- Follow PEP 8
- Use Black formatter
- Type hints where possible

**TypeScript**:
- Strict mode (`strict: true`)
- Avoid `any`, use specific types
- Use `import type` for type-only imports
- ESLint + Prettier

**Naming Conventions**:
- Components: PascalCase (`ChannelCard.tsx`)
- Hooks: camelCase with `use` prefix (`useChannel.ts`)
- Functions: camelCase (`formatDate.ts`)
- Constants: UPPER_SNAKE_CASE (`MAX_CHANNELS`)

### Git Workflow

**Branch Strategy**:
- `main` - Production
- `develop` - Integration
- `feature/模块名` - Features
- `fix/问题描述` - Bug fixes

**Commit Format** (Conventional Commits):
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Logging

**Backend**:
```python
from src.core.unified_logger import get_logger

logger = get_logger(__name__)
logger.info("Operation completed", extra={
    "event_name": "operation.completed",
    "metadata": {"result": "success"}
})
```

**Frontend**:
```typescript
console.log('Info message')
console.warn('Warning message')
console.error('Error message', error)
```

---

## Command Line Interface

### Main Entry

**`scripts/kat_cli.py`** - Unified CLI for all operations

### Common Commands

```bash
# Generate single episode
python scripts/kat_cli.py generate --id 20251102

# Batch generate
python scripts/kat_cli.py batch --count 10

# Schedule management
python scripts/kat_cli.py schedule create --episodes 100
python scripts/kat_cli.py schedule show
python scripts/kat_cli.py schedule watch --watch

# YouTube upload (uses Upload v2 pipeline)
python scripts/kat_cli.py upload --episode 20251102 --privacy unlisted

# See Upload/Verify v2 architecture:
# - docs/ARCHITECTURE_UPLOAD_V2.md
# - docs/ARCHITECTURE_VERIFY_V2.md
# - docs/LIFECYCLE_UPLOAD_VERIFY.md

# Reset
python scripts/kat_cli.py reset --schedule-only --yes
```

### Command Reference

**`generate`**: Generate video content (cover, remix, video)
- `--id <ID>` - Episode ID (YYYYMMDD)
- `--seed <N>` - Random seed
- `--no-remix` - Skip remix
- `--no-video` - Skip video

**`schedule create`**: Create schedule master
- `--episodes <N>` - Total episodes (required)
- `--start-date <DATE>` - Start date
- `--interval <N>` - Interval in days (default: 2)
- `--yes` - Skip confirmation
- `--force` - Overwrite existing

**`upload`**: Upload to YouTube
- `--episode <ID>` - Episode ID (required)
- `--privacy <STATUS>` - Privacy (private/unlisted/public)
- `--schedule` - Schedule publish
- `--force` - Force re-upload

---

## Frontend Development

### Architecture

**Tech Stack**:
- Next.js 15 (App Router)
- React 19 + TypeScript
- Zustand (state management)
- React Query (data fetching)
- Tailwind CSS (styling)
- WebSocket (real-time updates)

### Project Structure

```
frontend/
├── app/              # Next.js routes
│   └── (mcrb)/      # Route groups
├── components/       # UI components
│   ├── ui/          # ShadCN base components
│   └── mcrb/        # Feature components
├── stores/          # Zustand stores
├── hooks/           # Custom hooks
├── services/        # API services
├── utils/           # Utilities
└── types/           # TypeScript types
```

### State Management

**Unified Store**:
```typescript
import { useScheduleStore } from '@/stores/scheduleStore'

// Get event with runbook state
const eventWithRunbook = useScheduleStore((state) => 
  state.getEventWithRunbook(eventId)
)

// Direct runbook access
const runbookSnapshot = useScheduleStore((state) => 
  state.runbookSnapshots[episodeId]
)
```

### WebSocket Integration

```typescript
import { useWebSocket } from '@/hooks/useWebSocket'

// Automatically connects and updates stores
useWebSocket()
```

### Development Server

```bash
cd kat_rec_web/frontend
pnpm dev  # http://localhost:3000
```

---

## Testing

### Backend Tests

```bash
cd kat_rec_web/backend

# All tests
pytest tests/ -v

# Specific test
pytest tests/test_episodeflow_end2end.py -v

# Coverage
pytest --cov=src/core --cov-report=html
```

### Frontend Tests

```bash
cd kat_rec_web/frontend

# Unit tests
pnpm test

# E2E tests
pnpm test:e2e
```

### WebSocket Verification

```bash
python scripts/verify_websocket_events.py
```

### Atlas Console Debugging

**Atlas Console Debugging** 是 Vibe Coding Infra 的一部分，提供统一的浏览器侧调试工具，用于观察状态流、组件生命周期、队列变化、事件广播和 UI 行为。

#### 快速开始

1. **打开控制台**: 在 Atlas 中按 `⌥ + ⌘ + I` (Option + Command + I)

2. **加载调试工具**: 复制 `kat_rec_web/frontend/scripts/atlas-debug-core.js` 内容到控制台

3. **使用核心命令**:
   ```javascript
   // 暴露全局状态
   KAT.debug.exposeGlobalState()
   
   // 监听WebSocket事件
   KAT.debug.watchSocketEvents('20250117')  // 过滤特定episode
   
   // 监听FlowBus
   KAT.debug.monitorFlowBus()
   
   // 检查DOM
   KAT.debug.inspectDOM('2025-01-17')
   
   // 性能追踪
   const trace = KAT.debug.performanceTrace('ui_update')
   trace.start()
   // ... 执行操作 ...
   trace.end()
   
   // 检查State Drift
   KAT.debug.checkStateDrift('20250117')
   
   // 快速检查17日节目
   KAT.debug.checkEpisode17()
   
   // 生成Debug Summary
   KAT.debug.generateSummary('17日节目显示问题')
   ```

#### 核心原则

1. **可重现性**: 所有调试动作必须可重现，不依赖临时手动 patch
2. **真实状态验证**: 必须从控制台侧验证 state machine 的真实状态
3. **只读观测**: 控制台调试只用于观测，不允许篡改业务状态
4. **文档化**: 每一次调试都记录成可复制的步骤

#### 故障模式处理

**事件顺序乱序**:
```javascript
// 记录所有WebSocket消息
KAT.debug.watchSocketEvents()
// 执行操作...
console.log('WebSocket消息序列:', KAT.debug._data.wsMessages)
```

**State Drift**:
```javascript
// 检查store状态与ASR snapshot的差异
const episode = KAT.debug.checkStateDrift('20250117')
```

**UI 卡顿**:
```javascript
// 性能追踪
const trace = KAT.debug.performanceTrace('ui_update')
trace.start()
// ... 操作 ...
trace.end()

// 检查DOM数量
KAT.debug.inspectDOM()
```

#### Debug Summary 模板

每次调试结束后，使用 `KAT.debug.generateSummary()` 生成摘要，并添加到 DEVELOPMENT.md 的 "Atlas Debug Session" 区段。

**相关文档**:
- [Atlas Console Debugging Extension](VIBE_CODING_ATLAS_DEBUGGING_EXTENSION.md)
- [Atlas Console Debug Guide](ATLAS_CONSOLE_DEBUG_GUIDE.md)

### System Audit

```bash
# Quick verification (5 minutes)
bash scripts/verify_sprint6.sh

# Health check
curl http://localhost:8000/health | jq

# Metrics
curl http://localhost:8000/metrics/system | jq
```

---

## Tauri Desktop App

### Building

```bash
# Ensure frontend exported
cd kat_rec_web/frontend
NEXT_OUTPUT_MODE=export pnpm build

# Build Tauri app (macOS)
cd ../../desktop/tauri
pnpm tauri build
```

### Development Mode

```bash
make app:dev
```

**Features**:
- Auto-starts backend (port 8010)
- Waits for health check
- Opens window to `/t2r`
- Injects API/WebSocket URLs

### App Location

```
desktop/tauri/src-tauri/target/release/bundle/macos/
  Kat Rec Control Center.app
```

---

## Build & Deployment

### Backend Build

```bash
# Check dependencies
pip check

# Run tests
pytest tests/ -v

# Start server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend Build

```bash
cd kat_rec_web/frontend

# Production build
pnpm build
pnpm start
```

### Deployment

**Backend**:
- Environment variables: `OPENAI_API_KEY`, database connection, log level
- Use systemd (Linux) or process manager
- Health check endpoint: `/health`

**Frontend**:
- Build to static export
- Serve with Nginx or similar
- Configure API base URL

---

## Code Quality

### Pre-commit Checks

- ESLint (auto-fix)
- Prettier (format)
- TypeScript type check

### Code Review Checklist

- [ ] Code passes ESLint
- [ ] Code formatted with Prettier
- [ ] TypeScript types correct
- [ ] Tests pass (if applicable)
- [ ] Commit message follows convention
- [ ] No debug logs
- [ ] No hardcoded configs

---

## Performance

### Code Splitting

```typescript
// Lazy load heavy components
const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
  loading: () => <Skeleton />,
})
```

### Image Optimization

```tsx
import Image from 'next/image'

<Image src="/logo.png" alt="Logo" width={200} height={200} />
```

### State Management

```typescript
// ✅ Subscribe only to needed state
const channel = useChannelStore(state => 
  state.channels.find(ch => ch.id === id)
)

// ❌ Avoid subscribing to entire store
const { channels } = useChannelStore()
```

---

## Async Migration

### High Priority (File I/O Operations, Frequent Calls)

**1. `sync_episode_assets_from_filesystem`** (`render_queue_sync.py`)
- **Reason**: Executes many file system operations
- **Impact**: Blocks API requests, affects response time
- **Status**: ✅ Migrated to async (uses `AssetService`)

**2. `check_episode_assets_status`** (`auto_complete_episodes.py`)
- **Reason**: Calls `sync_episode_assets_from_filesystem`
- **Impact**: Blocks auto-completion flow
- **Status**: ✅ Migrated to async (uses `AssetService`)

**3. `load_manifest`** (`manifest.py`)
- **Reason**: File I/O operation (reads JSON)
- **Impact**: Blocks plan execution flow
- **Status**: ⚠️ Consider migrating to async

**4. `save_manifest`** (`manifest.py`)
- **Reason**: File I/O operation (writes JSON)
- **Impact**: Blocks plan execution and upload flow
- **Status**: ⚠️ Consider migrating to async

### Medium Priority (May Involve External Calls)

**5. `check_video_completion`** (`video_completion_checker.py`)
- **Reason**: May call `ffprobe` external tool
- **Impact**: Blocks asset synchronization
- **Status**: ⚠️ Consider migrating to async with `asyncio.create_subprocess_exec`

### Migration Tools

**Async File Operations**:
- `async_file_exists()` - File existence check
- `async_read_json()` - JSON reading
- `async_write_json()` - JSON writing
- `async_parse_playlist()` - Playlist parsing

**Location**: `kat_rec_web/backend/t2r/utils/async_file_ops.py`

### Migration Best Practices

1. **Use async utilities**: Replace sync file operations with async versions
2. **Maintain backward compatibility**: Keep sync versions if needed
3. **Test thoroughly**: Verify API response times and concurrent request handling
4. **Update callers**: Ensure all callers use `await` for async functions

---

**Related**: 
- [System Overview](01_SYSTEM_OVERVIEW.md)
- [Workflow Guide](02_WORKFLOW_AND_AUTOMATION.md)
- [Deployment](04_DEPLOYMENT_AND_ROADMAP.md)
- [Upload Pipeline v2 Architecture](ARCHITECTURE_UPLOAD_V2.md)
- [Verify Pipeline v2 Architecture](ARCHITECTURE_VERIFY_V2.md)
- [Upload→Verify Lifecycle](LIFECYCLE_UPLOAD_VERIFY.md)
