# 统一状态管理架构重构文档

**日期**: 2025-11-02  
**状态**: 实施中

## 概述

本项目已重构为**统一状态管理架构**，以 `schedule_master.json` 为**单一数据源（Single Source of Truth）**。所有状态查询和更新都通过统一接口进行，消除了之前三个独立数据源（`schedule_master.json（新架构单一数据源）`, `schedule_master.json`, `schedule_master.json动态查询（已弃用独立文件）`）之间的漂移问题。

## 架构设计

### 核心原则

1. **单一数据源**: `schedule_master.json` 是唯一权威数据源
2. **动态查询**: 不存储使用记录副本，从排播表动态查询
3. **事件驱动**: 生成时实时更新状态，失败时自动回滚
4. **文件系统为真相**: 验证时以文件系统为准，状态从文件系统重建

### 状态定义

期数状态采用明确的状态机模型：

```python
STATUS_PENDING = "pending"      # 待制作（初始状态）
STATUS_REMIXING = "remixing"    # 混音中
STATUS_RENDERING = "rendering"   # 渲染中（视频生成中）
STATUS_UPLOADING = "uploading"  # 上传中
STATUS_COMPLETED = "completed"  # 已完成
STATUS_ERROR = "error"          # 错误（需要人工介入）
```

### 状态转换规则

状态转换受以下规则约束：

```python
STATE_TRANSITIONS = {
    "pending": {"remixing", "error"},
    "remixing": {"rendering", "error"},
    "rendering": {"uploading", "completed", "error"},
    "uploading": {"completed", "error"},
    "completed": set(),  # 终态
    "error": {"pending", "remixing"},  # 可从错误恢复
}
```

## 核心模块

### 1. `src/core/state_manager.py`

统一状态管理器，提供以下功能：

- **状态查询**: `get_episode_status()`, `get_all_used_tracks()`, `get_used_starting_tracks()`
- **状态更新**: `update_status()`（带状态转换验证）
- **状态回滚**: `rollback_status()`（失败时调用）
- **元数据更新**: `update_episode_metadata()`（不改变状态）
- **文件验证**: `verify_episode_files()`（从文件系统验证完整性）

**关键特性**:
- 原子性写入（临时文件 → 重命名）
- 状态转换验证（防止非法状态跳转）
- 缓存机制（减少文件IO）

### 2. `src/core/event_bus.py`

轻量级事件总线，负责：

- **事件分发**: 每个阶段成功/失败时触发事件
- **自动状态更新**: 根据事件类型自动更新 `schedule_master.json` 状态
- **日志记录**: 记录所有事件历史（最多100个）
- **订阅机制**: 支持自定义事件处理器

**事件类型**:
- `REMIX_STARTED`, `REMIX_COMPLETED`, `REMIX_FAILED`
- `VIDEO_RENDER_STARTED`, `VIDEO_RENDER_COMPLETED`, `VIDEO_RENDER_FAILED`
- `YOUTUBE_ASSETS_GENERATED`, `YOUTUBE_ASSETS_FAILED`
- `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`

### 3. `scripts/local_picker/unified_sync.py`

统一状态同步工具（从文件系统重建状态）：

- **同步排播表状态**: 从 `output/` 目录验证文件完整性，更新状态
- **重建生产日志**: 从文件系统重建 `schedule_master.json（新架构单一数据源）`
- **重建歌曲使用记录**: 从 `schedule_master.json` 生成 `schedule_master.json动态查询（已弃用独立文件）`

**设计原则**: 文件系统为真相来源（Source of Truth）

## 工作流程

### 正常流程（成功）

```
1. 生成Playlist/Cover
   → 更新元数据（title, tracks_used, starting_track）
   → 状态保持 "pending"
   → 触发事件: stage_completed("playlist_and_cover")

2. 混音开始
   → 触发事件: remix_started
   → 状态更新为 "remixing"

3. 混音完成
   → 触发事件: remix_completed
   → 状态更新为 "rendering"

4. 视频渲染开始
   → 触发事件: video_render_started
   → 状态保持 "rendering"

5. 视频渲染完成
   → 触发事件: video_render_completed
   → 状态更新为 "completed" ✅
```

### 失败流程（回滚）

```
1. 混音失败
   → 触发事件: remix_failed
   → 状态更新为 "error"
   → 自动回滚为 "pending"

2. 视频渲染失败
   → 触发事件: video_render_failed
   → 状态更新为 "error"
   → 自动回滚为 "pending"
```

## 迁移指南

### 旧代码适配

如果旧代码直接操作 `schedule_master.json（新架构单一数据源）` 或 `schedule_master.json动态查询（已弃用独立文件）`，需要：

1. **替换为状态管理器**:
   ```python
   # 旧代码
   from state_manager（已迁移） import ProductionLog
   log = ProductionLog.load()
   log.update_record(episode_id="20251101", status="completed")
   
   # 新代码
   from core.state_manager import get_state_manager
   state_manager = get_state_manager()
   state_manager.update_status(episode_id="20251101", new_status="completed")
   ```

2. **使用事件总线**:
   ```python
   # 旧代码
   # 手动更新多个数据源
   
   # 新代码
   from core.event_bus import get_event_bus
   event_bus = get_event_bus()
   event_bus.emit_video_render_completed(episode_id="20251101")
   # 状态自动更新
   ```

### 查询使用记录

```python
# 旧代码（从多个源查询）
from state_manager（已迁移） import ProductionLog
from schedule_master import ScheduleMaster
log = ProductionLog.load()
schedule = ScheduleMaster.load()
# 需要手动合并数据

# 新代码（单一数据源）
from core.state_manager import get_state_manager
state_manager = get_state_manager()
used_tracks = state_manager.get_all_used_tracks(include_pending=True)
starting_tracks = state_manager.get_used_starting_tracks(include_pending=True)
```

## 重置流程

### 完整重置

```bash
# 1. 重置系统（清空output，重置排播表状态）
python scripts/reset_all.py --yes

# 2. 从文件系统重建所有状态（如果需要）
python scripts/local_picker/unified_sync.py --sync
```

**注意**: `reset_all.py` 现在只操作 `schedule_master.json`，不再操作 `schedule_master.json（新架构单一数据源）` 和 `schedule_master.json动态查询（已弃用独立文件）`。

### 状态同步

```bash
# 从文件系统同步状态（验证并修正）
python scripts/local_picker/unified_sync.py --sync

# 只同步排播表
python scripts/local_picker/unified_sync.py --sync --schedule-only

# 预览模式
python scripts/local_picker/unified_sync.py --sync --dry-run
```

## CLI命令更新

### `--resume` 选项

```bash
# 继续处理失败的期数
python scripts/local_picker/create_mixtape.py --episode-id 20251102 --resume
```

**实现**: `get_production_id()` 应该检查现有pending或error记录，而不是自动跳转。

### `--validate` 选项

```bash
# 验证状态一致性（不修改）
python scripts/local_picker/unified_sync.py --sync --dry-run
```

## 测试计划

### 测试场景

1. **失败回滚测试**:
   ```bash
   # 模拟混音失败
   # 预期：状态回滚为 "pending"，错误信息记录
   ```

2. **完整流程测试**:
   ```bash
   # 运行完整生成流程
   # 预期：状态按流程更新：pending → remixing → rendering → completed
   ```

3. **重置测试**:
   ```bash
   # 运行 reset_all.py
   # 预期：所有状态重置为 "pending"，使用记录清空
   ```

## 向后兼容

- 如果 `src/core/` 模块不可用，代码自动回退到旧方式
- `schedule_master.json（新架构单一数据源）` 和 `schedule_master.json动态查询（已弃用独立文件）` 仍然可以手动维护（但不推荐）
- 建议迁移到新架构以获得一致性保障

## Phase II: 稳定性与可观测性层

### 新增功能

#### 1. 结构化日志系统 (`src/core/logger.py`)

**功能**:
- 统一的JSON格式日志（时间戳、期数ID、事件名、消息、可选堆栈）
- 自动日志轮转（最大5MB，保留最近5个文件）
- 日志文件：`logs/system_events.log`

**使用示例**:
```python
from core.logger import get_logger

logger = get_logger()
logger.info(
    event_name="remix.completed",
    message="混音完成",
    episode_id="20251102"
)
```

**自动集成**: 事件总线自动记录所有事件到日志文件。

#### 2. 完整性验证工具 (`scripts/local_picker/validate_integrity.py`)

**功能**:
- 检查schedule_master.json字段一致性
- 验证已完成期数的输出文件完整性
- 检测重复的episode_id
- 生成彩色验证报告

**使用方法**:
```bash
# 快速检查
python scripts/local_picker/validate_integrity.py

# 深度检查（包括文件系统验证）
python scripts/local_picker/validate_integrity.py --deep

# JSON格式输出
python scripts/local_picker/validate_integrity.py --json
```

**输出示例**:
```json
{
  "total": 10,
  "errors": [
    {
      "type": "missing_files",
      "episode_id": "20251102",
      "missing": ["video", "audio"]
    }
  ],
  "warnings": [],
  "error_count": 1,
  "warning_count": 0,
  "is_valid": false
}
```

#### 3. 期数恢复工具 (`scripts/local_picker/recover_episode.py`)

**功能**:
- 检测失败的期数（status=error或缺少输出文件）
- 一键重置状态为pending
- 可选自动重新运行生成流程
- 记录恢复操作到日志

**使用方法**:
```bash
# 恢复单个期数
python scripts/local_picker/recover_episode.py --episode-id 20251102

# 恢复并自动重新运行
python scripts/local_picker/recover_episode.py --episode-id 20251102 --rerun

# 恢复所有失败的期数
python scripts/local_picker/recover_episode.py --all
```

**工作流程**:
1. 检测失败期数（status=error或卡在中间状态）
2. 重置状态为pending
3. 记录到日志（`logs/system_events.log`）
4. 可选：自动触发`create_mixtape.py`

#### 4. 增强的原子性和并发控制

**新增特性**:
- `StateLock`类：防止并发更新同一期数
- `_atomic_write`上下文管理器：确保写入原子性
- `StateConflictError`异常：处理并发冲突

**并发安全**:
```python
# 多个线程/进程同时更新同一期数时会自动加锁
with state_manager._lock.acquire(episode_id):
    # 更新状态（线程安全）
    state_manager.update_status(episode_id, STATUS_REMIXING)
```

**原子性写入**:
```python
# 所有写入都通过临时文件 → 重命名
with state_manager._atomic_write(path) as temp_path:
    # 写入临时文件
    json.dump(data, temp_path)
    # 自动原子性重命名
```

### 测试套件 (`tests/state_refactor/`)

**测试覆盖**:
1. **正常流程测试** (`test_state_manager.py::test_normal_pipeline_success`)
   - 验证完整的状态转换：pending → remixing → rendering → completed

2. **失败回滚测试** (`test_state_manager.py::test_intentional_remix_failure`)
   - 验证混音失败时的回滚机制

3. **状态转换验证测试** (`test_state_manager.py::test_state_transition_validation`)
   - 验证无效状态转换被拒绝

4. **并发更新预防测试** (`test_state_manager.py::test_concurrent_update_prevention`)
   - 验证多线程同时更新时的锁机制

5. **重置一致性测试** (`test_reset_consistency.py`)
   - 验证reset_all后的状态一致性

**运行测试**:
```bash
# 运行所有测试
pytest tests/state_refactor/ -v

# 运行特定测试
pytest tests/state_refactor/test_state_manager.py::test_normal_pipeline_success -v
```

### 故障排除

#### 问题1: "期数卡在中间状态"

**症状**: 期数状态为`remixing`或`rendering`，但没有对应的输出文件。

**解决方案**:
```bash
# 1. 检查状态
python scripts/local_picker/validate_integrity.py --deep

# 2. 恢复期数
python scripts/local_picker/recover_episode.py --episode-id 20251102

# 3. 可选：自动重新运行
python scripts/local_picker/recover_episode.py --episode-id 20251102 --rerun
```

#### 问题2: "状态转换错误"

**症状**: `❌ 无效状态转换: completed → pending`

**原因**: 已完成期数不能回退到pending。

**解决方案**:
- 如果需要重新生成，先使用`reset_all.py`重置，或手动修改排播表

#### 问题3: "并发更新冲突"

**症状**: `StateConflictError: 无法获取期数 20251102 的锁`

**原因**: 多个进程同时尝试更新同一期数。

**解决方案**:
1. 等待当前进程完成（30秒超时）
2. 检查是否有其他进程正在运行
3. 如果确定无其他进程，可以手动清理锁（重启Python进程）

#### 问题4: "日志文件过大"

**症状**: `logs/system_events.log`文件超过5MB。

**解决方案**:
- 日志系统会自动轮转，保留最近5个文件
- 旧日志文件会自动重命名为`system_events.log.1`, `system_events.log.2`等

### 监控和调试

#### 查看日志
```bash
# 查看最新日志
tail -f logs/system_events.log

# 查看特定期数的日志
grep "20251102" logs/system_events.log

# 查看错误日志
grep '"level":"ERROR"' logs/system_events.log
```

#### 验证系统健康
```bash
# 快速检查
python scripts/local_picker/validate_integrity.py

# 深度检查（包括文件系统）
python scripts/local_picker/validate_integrity.py --deep
```

#### 批量恢复
```bash
# 恢复所有失败的期数
python scripts/local_picker/recover_episode.py --all

# 恢复并自动重新运行
python scripts/local_picker/recover_episode.py --all --rerun
```

## Phase III: 指标与仪表板层

### 新增功能

#### 1. 指标收集模块 (`src/core/metrics_manager.py`)

**功能**:
- 跟踪每个阶段的耗时（remix, render, upload等）
- 统计成功/失败率
- 计算平均耗时、吞吐量、每日总数
- 持久化到 `data/metrics.json`（追加模式，自动轮转）

**使用示例**:
```python
from core.metrics_manager import get_metrics_manager

metrics = get_metrics_manager()

# 记录事件
metrics.record_event(
    stage="remix",
    status="completed",
    duration=120.5,
    episode_id="20251102"
)

# 获取摘要
summary = metrics.get_summary(period="24h")
print(f"成功率: {summary['success_rate']}%")
print(f"平均耗时: {summary['avg_duration']}s")
```

**自动集成**: 事件总线自动记录所有事件到指标管理器。

#### 2. Metrics API (`src/api/metrics_api.py`)

**端点**:
- `GET /metrics/summary?period=24h` - 获取聚合指标摘要
- `GET /metrics/episodes` - 获取所有期数状态
- `GET /metrics/events?limit=50` - 获取最近事件流
- `GET /metrics/episode/{episode_id}` - 获取特定期数指标

**启动服务**:
```bash
uvicorn src.api.metrics_api:app --reload --port 8000
```

**示例响应**:
```json
{
  "period": "24h",
  "total_events": 150,
  "completed": 120,
  "failed": 5,
  "success_rate": 96.0,
  "avg_duration": 145.3,
  "stages": {
    "remix": {
      "avg_duration": 120.5,
      "completed": 50,
      "failed": 2
    }
  },
  "global_state": {
    "total_episodes": 100,
    "completed": 80,
    "error": 2
  }
}
```

#### 3. Web仪表板 (`web/dashboard/`)

**功能**:
- 实时概览面板（总期数、成功率、失败率）
- 阶段耗时统计
- 期数列表（带状态指示）
- 最近事件流（自动刷新每10秒）
- 一键恢复按钮（针对失败期数）

**访问方式**:
```bash
# 启动仪表板服务器
python web/dashboard/dashboard_server.py

# 或使用uvicorn
uvicorn web.dashboard.dashboard_server:app --reload --port 8000

# 访问 http://localhost:8000
```

**特性**:
- 自动刷新（每10秒）
- 响应式设计
- 彩色状态指示
- 实时事件流

#### 4. CLI监控命令 (`scripts/local_picker/cli_monitor.py`)

**使用方法**:
```bash
# 单次显示
python scripts/local_picker/cli_monitor.py

# 持续监控（每5秒刷新）
python scripts/local_picker/cli_monitor.py --watch

# 自定义刷新间隔
python scripts/local_picker/cli_monitor.py --watch --interval 3
```

**显示内容**:
- 总期数、已完成、失败、进行中统计
- 成功率
- 阶段平均耗时
- 最近5个事件

#### 5. 指标钩子集成

**事件总线集成** (`src/core/event_bus.py`):
- 每个事件自动记录到指标管理器
- 自动计算阶段耗时（从started到completed/failed）
- 记录错误详情

**状态管理器集成** (`src/core/state_manager.py`):
- 错误状态更新时记录失败指标
- 回滚操作记录恢复指标

### 指标数据格式

**事件记录** (`data/metrics.json`):
```json
{
  "events": [
    {
      "timestamp": "2025-11-02T15:30:00",
      "stage": "remix",
      "status": "completed",
      "duration": 120.5,
      "episode_id": "20251102"
    }
  ],
  "daily_stats": {
    "2025-11-02": {
      "total_events": 50,
      "completed": 45,
      "failed": 2,
      "total_duration": 5432.1,
      "stages": {
        "remix": {
          "count": 20,
          "total_duration": 2410.0,
          "failed": 1
        }
      }
    }
  }
}
```

### 使用场景

#### 场景1: 监控系统健康
```bash
# 终端监控
python scripts/local_picker/cli_monitor.py --watch

# Web仪表板
# 访问 http://localhost:8000
```

#### 场景2: 查询特定指标
```bash
# API查询
curl http://localhost:8000/metrics/summary?period=7d

# 获取特定期数指标
curl http://localhost:8000/metrics/episode/20251102
```

#### 场景3: 分析性能
```python
from core.metrics_manager import get_metrics_manager

metrics = get_metrics_manager()

# 获取7天摘要
summary = metrics.get_summary(period="7d")
print(f"7天平均耗时: {summary['avg_duration']}s")
print(f"成功率: {summary['success_rate']}%")

# 分析特定期数
ep_metrics = metrics.get_episode_metrics("20251102")
print(f"混音平均耗时: {ep_metrics['stages']['remix']['avg_duration']}s")
```

## Phase IV: 架构收尾与一致性治理

### 概述

Phase IV 专注于确保整个项目的代码一致性、接口对齐、文档同步，以及清理过期文件。这是系统正式部署前的最后一道质量保障。

### 新增工具

#### 1. 项目一致性审计工具 (`scripts/audit_project_consistency.py`)

**功能**:
- 完整依赖与调用图分析
- API和函数签名一致性检查
- CLI命令对齐验证
- 文档同步检查
- JSON文件模式一致性验证
- 过期文件和未使用导入检测

**使用方法**:
```bash
# 完整审计
python scripts/audit_project_consistency.py

# 生成JSON报告
python scripts/audit_project_consistency.py --json --output audit_report.json

# 自动修复可修复项（未来支持）
python scripts/audit_project_consistency.py --fix
```

**输出**:
- Markdown格式审计报告 (`docs/audit_report.md`)
- JSON格式详细数据（可选）

#### 2. 一致性测试套件 (`tests/test_consistency.py`)

**测试覆盖**:
1. **模块导入测试**: 验证所有核心模块可正常导入
2. **CLI命令测试**: 验证所有CLI命令的`--help`功能正常
3. **JSON模式测试**: 验证所有JSON文件的模式一致性
4. **函数签名测试**: 验证关键函数的签名一致性
5. **冒烟测试**: 基本功能验证（状态管理、事件总线、指标管理器）

**运行测试**:
```bash
# 运行所有一致性测试
pytest tests/test_consistency.py -v

# 运行特定测试类别
pytest tests/test_consistency.py::TestImports -v
pytest tests/test_consistency.py::TestCLICommands -v
```

#### 3. 清理日志 (`docs/cleanup_log.md`)

**内容**:
- 过期文件清单
- 文档更新需求
- 代码清理需求
- 清理检查清单
- 渐进式清理计划

### 审计发现的问题类别

#### 1. 过期导入引用

**问题**: 部分代码仍在使用已弃用的`state_manager（已迁移）`模块

**影响文件**:
- `scripts/local_picker/create_mixtape.py`
- `scripts/local_picker/batch_generate_videos.py`
- `scripts/local_picker/modify_schedule.py`
- `scripts/local_picker/unified_sync.py`

**解决方案**: 
- 逐步迁移到`state_manager`
- 保持向后兼容性（暂时保留`state_manager（已迁移）.py`）

#### 2. 过期文件存在

**文件**:
- `config/schedule_master.json（新架构单一数据源）` - 已弃用，应通过`unified_sync.py`重建
- `data/schedule_master.json动态查询（已弃用独立文件）` - 已弃用，应从`schedule_master.json`动态查询
- `config/pppschedule_master.json（新架构单一数据源）` - 重复/错误命名文件

**清理策略**: 渐进式删除，确保不影响现有功能

#### 3. 文档同步滞后

**需要更新的文档**:
- `docs/PRODUCTION_LOG.md` - 添加已弃用标记
- `docs/SCHEDULE_CREATION_WITH_CONFIRMATION.md` - 更新架构说明
- `README.md` - 更新状态管理部分

**解决方案**: 统一更新所有文档，确保一致性

#### 4. JSON模式一致性

**验证项**:
- `schedule_master.json` - 必需字段、状态值有效性
- `data/metrics.json` - 事件结构一致性
- `data/workflow_status.json` - 模式一致性

**验证方法**: 通过审计工具和测试套件自动检测

### 一致性检查清单

#### ✅ 已完成

- [x] 创建审计工具 (`scripts/audit_project_consistency.py`)
- [x] 创建一致性测试套件 (`tests/test_consistency.py`)
- [x] 创建清理日志 (`docs/cleanup_log.md`)
- [x] 更新`state_refactor.md`文档

#### 🔄 进行中

- [ ] 运行完整审计生成报告
- [ ] 修复发现的错误和警告
- [ ] 更新过期文档引用
- [ ] 迁移`state_manager（已迁移）`调用到`state_manager`

#### 📋 待完成

- [ ] 清理未使用的导入
- [ ] 删除过期文件（确认安全后）
- [ ] 验证所有CLI命令对齐
- [ ] 运行完整测试套件验证

### 函数签名一致性验证

#### 核心函数签名标准

**状态管理器**:
```python
# update_status
def update_status(
    episode_id: str,
    new_status: str,
    message: Optional[str] = None,
    error_details: Optional[str] = None
) -> bool

# rollback_status
def rollback_status(
    episode_id: str,
    target_status: str = "pending"
) -> bool
```

**指标管理器**:
```python
# record_event
def record_event(
    stage: str,
    status: str,
    duration: Optional[float] = None,
    episode_id: Optional[str] = None,
    error_message: Optional[str] = None
) -> None
```

**验证方法**: 通过`inspect.signature()`自动检查所有调用点的参数一致性

### CLI命令对齐验证

#### 命令清单

所有通过`scripts/kat_cli.py`暴露的命令：
- `generate` - 生成视频内容
- `schedule create/show/generate/watch` - 排播表管理
- `batch` - 批量生成
- `reset` - 重置操作
- `help` - 帮助系统
- `api check/setup` - API管理

**验证**: 确保每个命令的`--help`能正常显示，参数正确

### 清理策略

#### 渐进式清理

**阶段1: 文档更新（低风险）**
- 更新所有文档标记已弃用内容
- 添加迁移指南
- 不影响现有功能

**阶段2: 代码迁移（中风险）**
- 逐步迁移`state_manager（已迁移）`调用到`state_manager`
- 保持向后兼容性
- 每次迁移后运行测试

**阶段3: 清理删除（高风险）**
- 确认所有代码已迁移
- 删除过期文件
- 清理未使用导入
- 最终验证测试

### 使用建议

#### 定期审计

建议在以下时机运行审计工具：
1. **发布前**: 确保代码一致性
2. **重构后**: 验证重构未引入问题
3. **定期检查**: 每月运行一次完整性检查

#### 测试验证

在以下场景运行一致性测试：
1. **代码变更后**: 确保核心功能正常
2. **依赖更新后**: 确保导入仍然有效
3. **CI/CD集成**: 作为持续集成的一部分

### 相关文档

- [清理日志](./cleanup_log.md)
- [API完整指南](./API完整指南.md)
- [工具入口整合方案](./工具入口整合方案.md)

---

## 未来优化

1. **SQLite/TinyDB迁移**: 使用数据库确保原子性写入和事务支持
2. **实时WebSocket推送**: 使用WebSocket替代轮询，实现真正的实时更新
3. **状态历史审计**: 记录所有状态变更历史，支持审计和回滚
4. **批量操作优化**: 支持批量状态更新和验证
5. **自动恢复策略**: 智能检测和自动恢复失败的期数
6. **告警系统**: 基于指标阈值触发告警（邮件、Slack等）

