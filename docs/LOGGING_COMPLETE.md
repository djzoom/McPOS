# 结构化日志记录完成总结

## ✅ 完成情况

所有5个阶段的日志记录已全部完成！

### 阶段1：生成歌单和封面 ✅
- ✅ 阶段开始日志
- ✅ 单个期数成功日志
- ✅ 单个期数失败日志（含错误详情）
- ✅ 超时日志
- ✅ 阶段完成统计日志

### 阶段2：生成YouTube资源 ✅
- ✅ 阶段开始日志
- ✅ 单个期数成功日志
- ✅ 单个期数失败日志（含错误详情）
- ✅ 超时日志
- ✅ 阶段完成统计日志

### 阶段3：生成音频混音 ✅
- ✅ 阶段开始日志
- ✅ 单个期数成功日志
- ✅ 单个期数失败日志（含退出码）
- ✅ 超时日志
- ✅ 阶段完成统计日志

### 阶段4：生成视频 ✅
- ✅ 阶段开始日志
- ✅ 单个期数成功日志
- ✅ 单个期数失败日志（含退出码）
- ✅ 超时日志
- ✅ 阶段完成统计日志

### 阶段5：检查并打包 ✅
- ✅ 阶段开始日志
- ✅ 单个期数成功日志（含移动文件数）
- ✅ 单个期数跳过日志（文件已在文件夹中）
- ✅ 文件移动失败警告日志
- ✅ 阶段完成统计日志

## 日志格式

所有日志都遵循统一的格式：

### 事件命名规则
```
breadth_first.{stage}.{event_type}
```

**stage**: 阶段编号（1-5）
**event_type**: 
- `started`: 阶段开始
- `completed`: 阶段完成统计
- `episode.success`: 单个期数成功
- `episode.failed`: 单个期数失败
- `episode.timeout`: 单个期数超时
- `episode.skipped`: 单个期数跳过（仅阶段5）
- `file_move.failed`: 文件移动失败（仅阶段5）

### 日志级别
- `INFO`: 成功、开始、完成、跳过
- `WARNING`: 超时、文件操作失败
- `ERROR`: 生成失败

### 元数据
所有日志都包含：
- `episode_id`: 期数ID（单个期数操作）
- `episode_count`: 期数总数（阶段操作）
- `success_count`: 成功数量（完成统计）
- `total_count`: 总数量（完成统计）
- `force`: 是否强制模式（阶段开始）
- `error`: 错误信息（失败时）
- `returncode`: 退出码（失败时）
- `moved_count`: 移动文件数（阶段5成功时）
- `final_dir`: 最终目录（阶段5成功时）
- `file`: 文件名（文件操作失败时）

## 示例日志

### 阶段开始
```json
{
  "timestamp": "2024-01-01T12:00:00",
  "level": "INFO",
  "event": "breadth_first.stage1.started",
  "message": "开始阶段1：生成歌单和封面（10期数）",
  "metadata": {
    "episode_count": 10,
    "force": false
  }
}
```

### 单个期数成功
```json
{
  "timestamp": "2024-01-01T12:05:00",
  "level": "INFO",
  "event": "breadth_first.stage1.episode.success",
  "message": "期数 20240101 歌单和封面生成成功",
  "episode_id": "20240101"
}
```

### 单个期数失败
```json
{
  "timestamp": "2024-01-01T12:10:00",
  "level": "ERROR",
  "event": "breadth_first.stage1.episode.failed",
  "message": "期数 20240102 生成失败: 参数错误或脚本执行失败",
  "episode_id": "20240102",
  "metadata": {
    "error": "参数错误或脚本执行失败"
  }
}
```

### 单个期数超时
```json
{
  "timestamp": "2024-01-01T12:15:00",
  "level": "WARNING",
  "event": "breadth_first.stage1.episode.timeout",
  "message": "期数 20240103 生成超时",
  "episode_id": "20240103"
}
```

### 阶段完成统计
```json
{
  "timestamp": "2024-01-01T12:20:00",
  "level": "INFO",
  "event": "breadth_first.stage1.completed",
  "message": "阶段1完成：成功 8/10",
  "metadata": {
    "success_count": 8,
    "total_count": 10
  }
}
```

### 阶段5特殊日志（文件移动失败）
```json
{
  "timestamp": "2024-01-01T12:25:00",
  "level": "WARNING",
  "event": "breadth_first.stage5.file_move.failed",
  "message": "期数 20240101 移动文件失败: 20240101_cover.png",
  "episode_id": "20240101",
  "metadata": {
    "file": "20240101_cover.png",
    "error": "Permission denied"
  }
}
```

## 实现特性

### 1. 优雅降级
所有日志记录都使用 `try-except ImportError` 模式，如果日志系统不可用，会优雅地跳过，不影响主流程。

```python
try:
    from src.core.logger import get_logger
    logger = get_logger()
    logger.info(...)
except ImportError:
    pass  # 日志系统不可用时优雅降级
```

### 2. 可选日志
每个函数都检查 `HAS_LOGGER` 标志，只有在日志系统可用时才记录阶段级别的日志。

### 3. 详细元数据
所有日志都包含丰富的元数据，便于后续分析和监控。

### 4. 统一格式
所有阶段的日志格式统一，便于解析和查询。

## 日志查询建议

### 查询所有阶段开始
```
breadth_first.stage*.started
```

### 查询所有失败
```
breadth_first.stage*.episode.failed
```

### 查询特定期数
```
episode_id = "20240101"
```

### 查询超时情况
```
breadth_first.stage*.episode.timeout
```

### 查询完成统计
```
breadth_first.stage*.completed
```

## 总结

✅ 所有5个阶段的日志记录已完整实现
✅ 统一的日志格式和命名规范
✅ 丰富的元数据支持
✅ 优雅降级机制
✅ 详细的成功/失败/超时追踪

这些日志将为系统监控、问题诊断和性能分析提供强有力的支持！

