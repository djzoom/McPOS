# Timeline CSV 缺失问题与选歌逻辑分析

## 问题1: 20251119 期缺少 timeline.csv

### 现状检查

**文件状态**：
- ✅ `20251119_full_mix.mp3` - 存在（81MB）
- ✅ `20251119_cover.png` - 存在（11MB）
- ❌ `20251119_full_mix_timeline.csv` - **缺失**
- ✅ `playlist.csv` - 存在，且包含 Timeline section

**Playlist.csv 内容验证**：
```bash
# playlist.csv 包含 Timeline section，格式正确
Section,Field,Value,Side,Order,Title,Duration,DurationSeconds,Timeline,Timestamp,Description
Timeline,,,A,,,,,Needle,0:00,Needle On Vinyl Record
Timeline,,,A,,,,,Needle,0:03,Planetary Whispers Under Endless Skies
...
```

### 问题分析

**Timeline CSV 生成逻辑**（`plan.py` lines 1295-1428）：

1. **生成时机**：在 remix 阶段完成后，从 `playlist.csv` 读取 Timeline section
2. **读取条件**：查找 `Section="Timeline"` 且 `Timeline="Needle"` 的行
3. **过滤逻辑**：排除 SFX（"Needle On Vinyl Record", "Vinyl Noise", "Silence"）
4. **写入文件**：`{episode_id}_full_mix_timeline.csv`

**可能的原因**：

1. **Remix 阶段未完成**：如果 remix 阶段出错或中断，timeline.csv 不会生成
2. **文件写入失败**：虽然有错误处理，但可能被静默忽略
3. **Playlist 格式问题**：虽然 playlist.csv 存在，但可能格式不完整
4. **时序问题**：remix 完成但 timeline.csv 生成失败，但 remix 状态已标记为完成

### 解决方案

**立即修复**：手动从 playlist.csv 生成 timeline.csv

```python
# 可以从 playlist.csv 重新生成 timeline.csv
import csv
from pathlib import Path

playlist_path = Path("/Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251119/playlist.csv")
timeline_csv_path = Path("/Users/z/Downloads/Kat_Rec/channels/kat_lofi/output/20251119/20251119_full_mix_timeline.csv")

playlist_timeline_events = []
with playlist_path.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get("Section", "").strip() == "Timeline" and row.get("Timeline", "").strip() == "Needle":
            playlist_timeline_events.append({
                "side": row.get("Side", "").strip(),
                "timestamp": row.get("Timestamp", "").strip(),
                "description": row.get("Description", "").strip(),
            })

# 过滤 SFX
clean_timeline_events = [
    ev for ev in playlist_timeline_events
    if ev["description"] not in ("Needle On Vinyl Record", "Vinyl Noise", "Silence")
]

# 写入 timeline.csv
with timeline_csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Timecode", "Track Name", "Side"])
    for event in clean_timeline_events:
        timestamp = event.get("timestamp", "")
        description = event.get("description", "")
        side = event.get("side", "")
        if timestamp and description:
            writer.writerow([timestamp, description, side])
```

---

## 问题2: 选歌逻辑与防止过密排播

### 选歌逻辑概述

**核心函数**：`select_tracks()` in `create_mixtape.py` (lines 343-500)

**参数**：
- `excluded_tracks`: 临近期数使用的歌曲（窗口：最近5期）
- `excluded_starting_tracks`: 所有已使用的起始曲目（全局唯一）
- `all_used_tracks`: 所有已使用的歌曲（用于识别新歌）
- `new_track_ratio`: 新歌比例（默认70%）

### 防止过密排播的机制

#### 1. **邻近排播防护**（`excluded_tracks`）

**实现位置**：
- `schedule_master.py`: `get_recent_tracks(episode_id, window=5)` (lines 397-419)
- `state_manager.py`: `get_recent_tracks(episode_id, window=5)` (lines 678-708)

**逻辑**：
```python
def get_recent_tracks(self, episode_id: str, window: int = 5) -> Set[str]:
    """
    获取最近 N 期使用的歌曲（避免临近期数重复）
    
    窗口：当前期之前，向前检查 window 期（默认5期）
    例如：当前是第10期，检查第5-9期使用的歌曲
    """
    current_ep = self.get_episode(episode_id)
    current_number = current_ep.get("episode_number", 0)
    recent_tracks = set()
    
    for ep in self.episodes:
        ep_num = ep.get("episode_number", 0)
        # 检查是否在窗口内（当前期之前）
        if ep_num < current_number and ep_num >= current_number - window:
            tracks = ep.get("tracks_used", [])
            recent_tracks.update(tracks)
    
    return recent_tracks
```

**效果**：
- ✅ 防止最近5期内重复使用同一首歌
- ✅ 基于 `episode_number` 计算，不依赖日期
- ✅ 动态查询，实时反映排播表状态

#### 2. **起始曲目唯一性**（`excluded_starting_tracks`）

**实现位置**：
- `schedule_master.py`: `get_used_starting_tracks()` (lines 421-428)

**逻辑**：
```python
def get_used_starting_tracks(self) -> Set[str]:
    """获取所有已使用的起始曲目（全局唯一）"""
    starting_tracks = set()
    for ep in self.episodes:
        starting = ep.get("starting_track")
        if starting:
            starting_tracks.add(starting)
    return starting_tracks
```

**效果**：
- ✅ 确保每期的起始曲目都是唯一的
- ✅ 全局检查，不限于窗口期
- ✅ 优先使用新歌作为起始曲目

#### 3. **选歌流程**（`select_tracks()`）

**步骤**：

1. **分离新歌和旧歌**：
   ```python
   # 排除临近期数使用的歌曲
   if excluded_tracks and track.title in excluded_tracks:
       continue  # 跳过，不参与选歌
   
   # 分离新歌（从未使用过）和旧歌（已使用过）
   if track.title not in all_used_tracks:
       new_tracks.append(track)
   else:
       old_tracks.append(track)
   ```

2. **选择起始曲目**：
   ```python
   # 必须排除已使用的起始曲目
   new_starting = [t for t in new_tracks if t.title not in excluded_starting_tracks]
   old_starting = [t for t in old_tracks if t.title not in excluded_starting_tracks]
   
   # 优先使用新歌作为起始曲目
   if new_starting:
       starting_candidate = new_starting[0]
   ```

3. **按比例混合**：
   - 70% 新歌，30% 旧歌
   - 智能穿插，均匀分布

### Reset 后的风险分析

#### 问题：Reset 后制作的下一期是否可能与 Reset 前最后一期有相同歌曲？

**答案：有可能，但概率较低**

**原因分析**：

1. **Reset 会清空 `tracks_used`**：
   - Reset 时，所有期数的 `tracks_used` 会被清空
   - `excluded_tracks`（最近5期）会变成空集合
   - `all_used_tracks` 也会变成空集合

2. **但 `excluded_starting_tracks` 可能保留**：
   - 如果 Reset 时保留了已上传期数的信息，`starting_track` 可能还在
   - 但 `tracks_used` 列表会被清空

3. **实际影响**：
   - ✅ **起始曲目**：如果 Reset 前最后一期的 `starting_track` 还在 schedule 中，会被排除（安全）
   - ⚠️ **其他歌曲**：如果 Reset 前最后一期的 `tracks_used` 被清空，且该期不在"最近5期"窗口内，**可能被重复使用**

**示例场景**：

假设 Reset 前最后一期是第10期：
- Reset 后制作第11期
- 第10期的 `tracks_used` 被清空
- 第11期检查"最近5期"（第6-10期）
- 如果第10期的 `tracks_used` 为空，第11期**不会排除**第10期使用的歌曲
- **结果**：可能重复使用第10期的歌曲

### 改进建议

#### 方案1：Reset 时保留已上传期数的 `tracks_used`

```python
def _preserve_uploaded_episodes_assets(channel_id: str) -> Dict:
    # 不仅保留图片，也保留已上传期数的 tracks_used
    for ep in episodes:
        if is_episode_uploaded(ep):
            # 保留 tracks_used（用于防止邻近排播）
            uploaded_tracks_used.append({
                "episode_id": ep.get("episode_id"),
                "episode_number": ep.get("episode_number"),
                "tracks_used": ep.get("tracks_used", []),
            })
```

#### 方案2：扩展窗口检查范围

```python
def get_recent_tracks(self, episode_id: str, window: int = 5) -> Set[str]:
    # 不仅检查最近5期，也检查已上传的期数（即使不在窗口内）
    # 这样可以防止 Reset 后立即重复使用已上传期数的歌曲
    uploaded_episodes_tracks = set()
    for ep in self.episodes:
        if ep.get("uploaded", False):
            # 已上传期数的歌曲也应该被排除（至少一段时间内）
            tracks = ep.get("tracks_used", [])
            uploaded_episodes_tracks.update(tracks)
    
    recent_tracks = ...  # 原有逻辑
    recent_tracks.update(uploaded_episodes_tracks)  # 合并已上传期数的歌曲
    return recent_tracks
```

#### 方案3：在 Reset 时标记"最近上传期数"

```python
def _restore_uploaded_episodes_assets(...):
    # 不仅恢复图片，也恢复已上传期数的 tracks_used
    # 这样 get_recent_tracks 可以正常检查到
    for ep_data in preserved_uploaded_episodes:
        # 在 schedule 中保留已上传期数的 tracks_used
        # 即使期数状态被重置，tracks_used 仍然保留
        pass
```

### 当前防护措施总结

✅ **已实现**：
1. 邻近排播防护（最近5期窗口）
2. 起始曲目唯一性（全局）
3. 新歌优先策略（70%新歌）

⚠️ **潜在风险**：
1. Reset 后，已上传期数的 `tracks_used` 可能被清空
2. 如果已上传期数不在"最近5期"窗口内，其歌曲可能被重复使用
3. 需要确保 Reset 时保留已上传期数的 `tracks_used` 信息

### 建议

**短期**：检查 Reset 逻辑，确保已上传期数的 `tracks_used` 被保留

**长期**：扩展 `get_recent_tracks` 逻辑，不仅检查窗口期，也检查已上传期数（至少保留一段时间，如30天）

