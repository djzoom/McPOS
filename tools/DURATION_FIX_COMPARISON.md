# 时长修复方案对比（静态图+MP3）

## 问题本质

静态图+MP3生成视频，信息熵极低：
- **视频**：只有1帧有效信息，重复播放
- **音频**：唯一变化的流
- **理论最优**：只编码1帧，用容器时间戳控制时长

## 方案对比

| 方案 | 帧率 | 文件大小 | 编码时间 | 时长准确性 | 信息熵利用率 |
|------|------|----------|----------|------------|--------------|
| **none** (原逻辑) | 1fps | ✅ 最小 (~150MB) | ✅ 最快 (~26min) | ❌ 偏差+33s | ⭐⭐⭐⭐⭐ |
| **30fps** | 30fps | ⚠️ 较大 (~240MB) | ⚠️ 较慢 (~26min) | ✅ ≤1s误差 | ⭐⭐ |
| **1fps-precise** | 1fps | ✅ 最小 (~150MB) | ✅ 最快 (~26min) | ✅ ≤1s误差 | ⭐⭐⭐⭐⭐ |
| **explicit** | 1fps | ✅ 最小 (~150MB) | ✅ 最快 (~26min) | ✅ 严格一致 | ⭐⭐⭐⭐⭐ |
| **mjpeg** | 1fps | ❌ 巨大 (~3123MB) | ✅ 快 (~27min) | ✅ 准确 | ⭐⭐ |

## 推荐方案：1fps-precise（默认）

### 为什么选择它？

1. **信息熵最优**：静态图只需1帧，1fps完美匹配
2. **文件最小**：保持原始1fps的小文件优势
3. **速度最快**：编码时间与原始1fps相同
4. **时长准确**：通过 `fps=1:round=down` + `vsync vfr` 精确控制

### 技术原理

```bash
# 关键改进点
-vf "scale=...,fps=1:round=down"  # 向下取整，避免向上舍入导致超时
-vsync vfr                        # 可变帧率，精确传递时间戳
-fps_mode passthrough            # 让filter的时间戳主导
# 不设 -r（避免双重时间戳冲突）
```

### 预期效果

- **文件大小**：与none相同（~150MB），比30fps小60%
- **编码时间**：与none相同（~26min），比30fps快
- **时长误差**：≤1秒（通过round=down精确控制）

## 30fps方案的权衡

### 什么时候用30fps？

- ✅ 需要绝对精确（要求严格一致，不能有误差）
- ⚠️ 能接受更大的文件体积（多30倍帧数）
- ⚠️ 能接受稍慢的编码（虽然对于静态图差别不大）

### 为什么不作为默认？

对于**静态图**场景：
- 30fps浪费：重复编码同一帧30次/秒
- 信息熵浪费：没有新信息，纯冗余
- 文件浪费：体积增加但质量无提升

## MJPEG的特殊性

MJPEG虽然准确，但：
- 文件体积巨大（~3GB vs ~150MB）
- 不适合实际使用
- 仅在需要快速预览时考虑

## 实际测试建议

运行对比测试验证 `1fps-precise` 效果：

```bash
# 方案C：1fps精确时间戳（推荐）
python tools/ffmpeg_bench.py \
  --image assets/cover_sample/cover_sample.png \
  --audio "assets/song_sample/mix_sample _01_04_32.mp3" \
  --outdir output/bench_1fps_precise \
  --fps 1 \
  --duration-fix 1fps-precise \
  --gen-diagnostics

# 对比：30fps方案
python tools/ffmpeg_bench.py \
  --image assets/cover_sample/cover_sample.png \
  --audio "assets/song_sample/mix_sample _01_04_32.mp3" \
  --outdir output/bench_30fps \
  --fps 1 \
  --duration-fix 30fps \
  --gen-diagnostics
```

## 总结

**默认推荐：`1fps-precise`**
- 最优信息熵利用率（静态图只需1帧）
- 最小文件体积（~150MB）
- 最快编码速度（~26分钟）
- 时长准确（≤1秒误差）

这是**理论最优解**：静态图不需要30fps的冗余帧，只需精确的时间戳控制即可。

