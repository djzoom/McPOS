# Essentia 模型文件目录

## 📦 当前模型状态

### ✅ 必需模型（已就绪）

1. **voice_instrumental-musicnn-msd-2.pb** (3.1 MB)
   - 人声检测模型
   - 用于检测音频中是否包含人声
   - 状态: ✅ 已下载

2. **discogs-effnet-bs64-1.pb** (约18 MB)
   - 流派分类模型
   - 用于识别音乐流派（Hip-Hop, Rock, Dance等）
   - 状态: ⚠️ 需要手动下载

### ⭐ 推荐扩展模型

3. **deeptemp-k16-3.pb** (1.3 MB)
   - TempoCNN模型
   - 更准确的BPM检测
   - 状态: ✅ 已下载

4. **danceability-musicnn-msd-1.pb** (~3 MB)
   - 可舞性检测模型
   - 用于RBR频道特别有用
   - 状态: ⏭️ 可选（未下载）

5. **moods_mirex-musicnn-msd-1.pb** (~3 MB)
   - 情绪检测模型
   - 用于情绪匹配的混音策略
   - 状态: ⏭️ 可选（未下载）

## 📥 如何下载缺失的模型

### 方法1: 使用浏览器下载

1. 访问 Essentia 模型库: https://essentia.upf.edu/models/
2. 导航到对应的模型目录
3. 下载 `.pb` 文件到本目录

### 方法2: 使用curl命令

```bash
# 下载discogs模型（必需）
curl -L -o models/discogs-effnet-bs64-1.pb \
  "https://essentia.upf.edu/models/feature-extractors/discogs/effnet/discogs-effnet-bs64-1/discogs-effnet-bs64-1.pb"

# 下载可舞性模型（可选）
curl -L -o models/danceability-musicnn-msd-1.pb \
  "https://essentia.upf.edu/models/classifiers/danceability/danceability-musicnn-msd-1/danceability-musicnn-msd-1.pb"

# 下载情绪检测模型（可选）
curl -L -o models/moods_mirex-musicnn-msd-1.pb \
  "https://essentia.upf.edu/models/classifiers/moods_mirex/moods_mirex-musicnn-msd-1/moods_mirex-musicnn-msd-1.pb"
```

### 方法3: 使用提供的脚本

```bash
# 下载所有推荐模型
bash mcpos/adapters/broadcast/download_extended_models.sh
```

## ✅ 验证下载

下载完成后，检查文件大小：

```bash
ls -lh models/*.pb
```

**正确的大小应该是**:
- voice_instrumental-musicnn-msd-2.pb: ~3 MB
- discogs-effnet-bs64-1.pb: ~18 MB
- deeptemp-k16-3.pb: ~1.3 MB
- danceability-musicnn-msd-1.pb: ~3 MB
- moods_mirex-musicnn-msd-1.pb: ~3 MB

如果文件只有153字节，说明下载失败（可能下载了错误页面）。

## 🎯 下一步

当必需模型都下载完成后，可以开始扫描曲库：

```bash
python3 -m mcpos.cli.main rbr-broadcast-scan
```

## 📚 相关文档

- [MODELS_FOR_MIXING.md](../mcpos/adapters/broadcast/MODELS_FOR_MIXING.md) - 模型选择指南
- [LIQUIDSOAP_TAGS.md](../mcpos/adapters/broadcast/LIQUIDSOAP_TAGS.md) - Liquidsoap标记参数
- [RBR_SETUP.md](../mcpos/adapters/broadcast/RBR_SETUP.md) - RBR设置指南

