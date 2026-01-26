# 视频渲染完成判断方法分析

## 当前实现

### 1. `render_complete_flag` 文件
- **位置**: `{episode_id}_render_complete.flag`
- **创建时机**: 渲染完成后，在 `plan.py` 的 `_execute_stage_core` 中创建
- **内容**: 包含渲染完成时间、视频路径、文件大小、校验和等信息
- **优点**: 简单、明确、可靠
- **缺点**: 依赖文件系统写入，可能存在时序问题

### 2. `ffprobe` 验证
- **位置**: `kat_rec_web/backend/t2r/services/render_validator.py`
- **实现**: 使用 `ffprobe` 读取视频元数据（时长、分辨率、编码格式等）
- **优点**: 能验证视频文件是否真正完整和有效
- **缺点**: 需要额外调用外部工具，有一定性能开销

### 3. 文件大小监控
- **位置**: `kat_rec_web/backend/t2r/routes/episodes.py` 的 `get_video_render_progress`
- **实现**: 通过监控文件大小变化来估算渲染进度
- **优点**: 实时性好，可以显示进度
- **缺点**: 无法准确判断是否真正完成

## 问题分析

用户观察到：**在 Finder 中，渲染完的 MP4 有缩略图，没渲染完的则没有。**

这是因为：
1. macOS 的 Quick Look 需要读取视频文件的**元数据**（特别是 `moov` atom）来生成缩略图
2. 如果视频文件还在写入中，`moov` atom 可能还没有写入到文件末尾，Quick Look 无法读取
3. 只有当视频文件完整时，`moov` atom 才会在正确位置，Quick Look 才能生成缩略图

## 改进方案

### 方案 1: 使用 `ffprobe` 作为主要判断依据（推荐）

**原理**: 如果 `ffprobe` 能成功读取视频的元数据（特别是时长），说明文件已经完整。

**优点**:
- 直接验证文件完整性，不依赖额外的 flag 文件
- 与 Finder 缩略图生成机制一致（都需要读取元数据）
- 已经在代码中实现，只需调整判断逻辑

**实现**:
```python
def is_video_complete(video_path: Path) -> bool:
    """检查视频文件是否完整（基于 ffprobe 元数据读取）"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            return duration > 0  # 如果能读取到时长，说明文件完整
    except Exception:
        pass
    return False
```

### 方案 2: 检查文件大小稳定性

**原理**: 如果文件大小在一段时间内不再变化，可能表示渲染完成。

**优点**: 简单、快速
**缺点**: 不够准确，文件可能因为其他原因停止增长

**实现**:
```python
async def is_video_size_stable(video_path: Path, check_interval: float = 2.0, stable_count: int = 3) -> bool:
    """检查文件大小是否稳定"""
    last_size = None
    stable_count_current = 0
    
    for _ in range(stable_count):
        if not video_path.exists():
            return False
        current_size = video_path.stat().st_size
        if last_size is not None and current_size == last_size:
            stable_count_current += 1
        else:
            stable_count_current = 0
        last_size = current_size
        await asyncio.sleep(check_interval)
    
    return stable_count_current >= stable_count
```

### 方案 3: 检查文件末尾是否可读

**原理**: 尝试读取文件的最后几个字节，如果成功，说明文件已经完整。

**优点**: 简单、快速
**缺点**: 不够准确，文件可能还在写入中

**实现**:
```python
def is_video_tail_readable(video_path: Path, tail_bytes: int = 1024) -> bool:
    """检查文件末尾是否可读"""
    try:
        with video_path.open('rb') as f:
            f.seek(-tail_bytes, 2)  # 从文件末尾向前读取
            data = f.read(tail_bytes)
            return len(data) == tail_bytes
    except Exception:
        return False
```

### 方案 4: 检查 macOS Quick Look 元数据（仅 macOS）

**原理**: 检查文件是否有 Quick Look 生成的缩略图元数据。

**优点**: 与用户观察一致
**缺点**: 仅适用于 macOS，且依赖系统生成元数据

**实现**:
```python
def has_quicklook_thumbnail(video_path: Path) -> bool:
    """检查文件是否有 Quick Look 缩略图（仅 macOS）"""
    try:
        import xattr
        attrs = xattr.listxattr(str(video_path))
        # Quick Look 会生成 com.apple.quarantine 等扩展属性
        return any('quarantine' in attr.lower() or 'quicklook' in attr.lower() for attr in attrs)
    except Exception:
        return False
```

## 推荐方案

**组合方案**: 使用 `ffprobe` 作为主要判断依据，`render_complete_flag` 作为辅助确认。

**理由**:
1. `ffprobe` 能直接验证文件完整性，与 Finder 缩略图生成机制一致
2. `render_complete_flag` 提供额外的确认和元数据记录
3. 两者结合，既准确又可靠

**实现建议**:
1. 在 `plan.py` 中，渲染完成后先使用 `ffprobe` 验证文件完整性
2. 验证通过后再创建 `render_complete_flag`
3. 在判断渲染完成时，优先检查 `ffprobe` 验证结果，其次检查 `render_complete_flag`

## 当前代码位置

- **渲染完成判断**: `kat_rec_web/backend/t2r/routes/plan.py` (lines 1956-1969)
- **ffprobe 验证**: `kat_rec_web/backend/t2r/services/render_validator.py`
- **前端判断**: `kat_rec_web/frontend/stores/scheduleStore.ts` (line 950-953)
- **进度查询**: `kat_rec_web/backend/t2r/routes/episodes.py` (lines 465-567)

