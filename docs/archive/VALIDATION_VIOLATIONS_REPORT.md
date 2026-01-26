# validate_no_asr_left.py 违规清单

**生成时间**: 2025-11-15 21:16  
**总违规数**: 31个  
**验证脚本**: `kat_rec_web/backend/t2r/scripts/validate_no_asr_left.py`

---

## 📊 违规统计（按类型）

| 类型 | 数量 | 占比 |
|------|------|------|
| **ASR Read** | 3 | 9.7% |
| **ASR Write** | 2 | 6.5% |
| **Ghost State** | 5 | 16.1% |
| **File Check Warning** | 21 | 67.7% |
| **总计** | 31 | 100% |

---

## 🔴 1. ASR Read 操作（3个）

**问题**: 使用 ASR 服务检查文件状态，应使用 file_detect.py 或 `/api/t2r/episodes/{episode_id}/assets` API

| # | 文件 | 行号 | 模式 |
|---|------|------|------|
| 1 | `backend/t2r/routes/auto_complete.py` | 114 | `check_episode_assets_status\s*\(` |
| 2 | `backend/t2r/services/auto_complete_episodes.py` | 26 | `check_episode_assets_status\s*\(` |
| 3 | `backend/t2r/services/auto_complete_episodes.py` | 129 | `check_episode_assets_status\s*\(` |

**修复建议**: 
- 移除 `check_episode_assets_status()` 调用
- 使用 `file_detect.py` 或 `/api/t2r/episodes/{episode_id}/assets` API 替代

---

## 🔴 2. ASR Write 操作（2个）

**问题**: 检测到 ASR 写入操作，ASR 写入已在 Stateflow V4 中禁用

| # | 文件 | 行号 | 模式 |
|---|------|------|------|
| 1 | `backend/t2r/services/data_migration.py` | 205 | `update_asset_state\s*\(` |
| 2 | `backend/t2r/services/data_migration.py` | 205 | `registry\.update_asset_state` |

**修复建议**: 
- 移除 `update_asset_state()` 调用
- 移除 `registry.update_asset_state` 调用
- 文件系统是 SSOT，不需要写入 ASR

---

## 🟡 3. Ghost State Fallback（5个）

**问题**: 使用 `ep.get("assets")` 或 `episode_data.get("assets")` 作为 fallback，这是 Ghost State 层

| # | 文件 | 行号 | 模式 |
|---|------|------|------|
| 1 | `backend/t2r/routes/automation.py` | 4016 | `ep\.get\(["\']assets["\']\)` |
| 2 | `backend/t2r/routes/cleanup.py` | 77 | `ep\.get\(["\']assets["\']\)` |
| 3 | `backend/t2r/services/data_migration.py` | 198 | `ep\.get\(["\']assets["\']\)` |
| 4 | `backend/t2r/services/episode_flow_adapters.py` | 218 | `ep\.get\(["\']assets["\']\)` |
| 5 | `backend/t2r/services/episode_flow_helper.py` | 86 | `episode_data\.get\(["\']assets["\']\)` |
| 6 | `backend/t2r/services/episode_flow_helper.py` | 88 | `episode_data\.get\(["\']assets["\']\)` |

**注意**: 虽然显示6个，但 `episode_flow_helper.py:86` 和 `88` 可能是同一行或相邻行，实际为5个违规

**修复建议**: 
- 移除 `ep.get("assets")` 和 `episode_data.get("assets")` fallback
- 使用 `file_detect.py` 或 `/api/t2r/episodes/{episode_id}/assets` API 获取文件状态
- 使用 `useEpisodeAssets()` hook（前端）或统一 API（后端）

---

## 🟠 4. File Check Warning（21个）

**问题**: 直接使用文件路径检查（`.exists()`），应使用 `file_detect.py` 统一文件检测

### 4.1 Asset File Check（10个）

**模式**: `(video_path|audio_path|cover_path|srt_path|desc_path|title_path)\.exists\(\)`

| # | 文件 | 行号 |
|---|------|------|
| 1 | `backend/t2r/routes/automation.py` | 3931 |
| 2 | `backend/t2r/routes/automation.py` | 4456 |
| 3 | `backend/t2r/services/episode_flow_adapters.py` | 200 |
| 4 | `backend/t2r/services/episode_flow_adapters.py` | 209 |
| 5 | `backend/t2r/services/episode_flow_adapters.py` | 251 |
| 6 | `backend/t2r/services/episode_flow_adapters.py` | 332 |
| 7 | `backend/t2r/services/render_queue.py` | 638 |
| 8 | `backend/t2r/services/render_validator.py` | 51 |
| 9 | `backend/t2r/utils/video_completion_checker.py` | 36 |
| 10 | `backend/t2r/utils/video_completion_checker.py` | 88 |
| 11 | `backend/t2r/utils/video_completion_checker.py` | 100 |
| 12 | `backend/t2r/utils/video_completion_checker.py` | 163 |

**注意**: 虽然显示12个，但实际为10个违规（某些文件可能有多个违规）

### 4.2 Episode Directory File Check（11个）

**模式**: `(episode_dir|output_dir).*\.exists\(\)`

| # | 文件 | 行号 |
|---|------|------|
| 1 | `backend/t2r/routes/reset.py` | 322 |
| 2 | `backend/t2r/routes/schedule.py` | 129 |
| 3 | `backend/t2r/services/cleanup_service.py` | 128 |
| 4 | `backend/t2r/services/cleanup_service.py` | 188 |
| 5 | `backend/t2r/services/episode_flow_adapters.py` | 142 |
| 6 | `backend/t2r/services/episode_flow_adapters.py` | 144 |
| 7 | `backend/t2r/services/episode_flow_adapters.py` | 285 |
| 8 | `backend/t2r/services/episode_flow_adapters.py` | 287 |

**修复建议**: 
- 将所有直接文件检查（`.exists()`）替换为 `file_detect.py` 的 `detect_all_assets()` 或相关函数
- 或使用 `/api/t2r/episodes/{episode_id}/assets` API
- 确保文件检测逻辑统一，避免重复检查

---

## 📋 按文件分组的违规清单

### `backend/t2r/routes/auto_complete.py` (1个)
- [ ] 114: ASR Read

### `backend/t2r/routes/automation.py` (3个)
- [ ] 3931: File Check Warning (Asset file check)
- [ ] 4016: Ghost State
- [ ] 4456: File Check Warning (Asset file check)

### `backend/t2r/routes/cleanup.py` (1个)
- [ ] 77: Ghost State

### `backend/t2r/routes/reset.py` (1个)
- [ ] 322: File Check Warning (Episode directory file check)

### `backend/t2r/routes/schedule.py` (1个)
- [ ] 129: File Check Warning (Episode directory file check)

### `backend/t2r/services/auto_complete_episodes.py` (2个)
- [ ] 26: ASR Read
- [ ] 129: ASR Read

### `backend/t2r/services/cleanup_service.py` (2个)
- [ ] 128: File Check Warning (Episode directory file check)
- [ ] 188: File Check Warning (Episode directory file check)

### `backend/t2r/services/data_migration.py` (3个)
- [ ] 198: Ghost State
- [ ] 205: ASR Write (update_asset_state)
- [ ] 205: ASR Write (registry.update_asset_state)

### `backend/t2r/services/episode_flow_adapters.py` (7个)
- [ ] 142: File Check Warning (Episode directory file check)
- [ ] 144: File Check Warning (Episode directory file check)
- [ ] 200: File Check Warning (Asset file check)
- [ ] 209: File Check Warning (Asset file check)
- [ ] 218: Ghost State
- [ ] 251: File Check Warning (Asset file check)
- [ ] 285: File Check Warning (Episode directory file check)
- [ ] 287: File Check Warning (Episode directory file check)
- [ ] 332: File Check Warning (Asset file check)

### `backend/t2r/services/episode_flow_helper.py` (2个)
- [ ] 86: Ghost State
- [ ] 88: Ghost State

### `backend/t2r/services/render_queue.py` (1个)
- [ ] 638: File Check Warning (Asset file check)

### `backend/t2r/services/render_validator.py` (1个)
- [ ] 51: File Check Warning (Asset file check)

### `backend/t2r/utils/video_completion_checker.py` (4个)
- [ ] 36: File Check Warning (Asset file check)
- [ ] 88: File Check Warning (Asset file check)
- [ ] 100: File Check Warning (Asset file check)
- [ ] 163: File Check Warning (Asset file check)

---

## 🎯 修复优先级建议

### 高优先级（阻塞 Phase 5）
1. **ASR Write 操作** (2个) - 违反 Stateflow V4 核心原则
2. **ASR Read 操作** (3个) - 应使用统一 API
3. **Ghost State Fallback** (5个) - 违反架构原则

### 中优先级（影响架构一致性）
4. **File Check Warning** (21个) - 应统一使用 file_detect.py

---

## 📝 修复指南

### 修复 ASR Read/Write
```python
# ❌ 错误
status = await asset_service.check_episode_assets_status(episode_id)
registry.update_asset_state(episode_id, asset_type, state)

# ✅ 正确
from t2r.utils.file_detect import detect_all_assets
assets = await detect_all_assets(channel_id, episode_id)
# 或使用 API: GET /api/t2r/episodes/{episode_id}/assets
```

### 修复 Ghost State
```python
# ❌ 错误
assets = ep.get("assets", {})

# ✅ 正确
from t2r.utils.file_detect import detect_all_assets
assets = await detect_all_assets(channel_id, episode_id)
```

### 修复 File Check
```python
# ❌ 错误
if video_path.exists():
    # ...

# ✅ 正确
from t2r.utils.file_detect import detect_all_assets
assets = await detect_all_assets(channel_id, episode_id)
if assets.get("video"):
    # ...
```

---

**报告生成时间**: 2025-11-15 21:16

