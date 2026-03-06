# Essentia模型下载URL（已验证）

## ✅ 已找到的正确URL

### 必需模型

1. **voice_instrumental-musicnn-msd-2.pb** (3.1 MB) ✅ 已下载
   - URL: `https://essentia.upf.edu/models/classifiers/voice_instrumental/voice_instrumental-musicnn-msd-2.pb`
   - 状态: ✅ 已就绪

2. **discogs-effnet-bs64-1.pb** (约18 MB) ⚠️ 需要下载
   - **问题**: 直接URL可能不正确
   - **建议**: 手动访问 https://essentia.upf.edu/models/feature-extractors/discogs/effnet/
   - 查找 `discogs-effnet-bs64-1` 目录，下载其中的 `.pb` 文件

### 扩展模型（从legacy目录）

3. **danceability-musicnn-msd-1.pb** (约3 MB)
   - ✅ URL: `https://essentia.upf.edu/models/legacy/classifiers/danceability/danceability-musicnn-msd-1.pb`
   - 状态: 可用

4. **moods_mirex-musicnn-msd-1.pb** (约3 MB)
   - ✅ URL: `https://essentia.upf.edu/models/legacy/classifiers/moods_mirex/moods_mirex-musicnn-msd-1.pb`
   - 状态: 可用

5. **deeptemp-k16-3.pb** (1.3 MB) ✅ 已下载
   - URL: `https://essentia.upf.edu/models/tempo/tempocnn/deeptemp-k16-3.pb`
   - 状态: ✅ 已就绪

## 📥 快速下载命令

```bash
# 进入项目根目录
cd /Users/z/Downloads/Kat_Rec

# 下载扩展模型（从legacy目录）
curl -L -o models/danceability-musicnn-msd-1.pb \
  "https://essentia.upf.edu/models/legacy/classifiers/danceability/danceability-musicnn-msd-1.pb"

curl -L -o models/moods_mirex-musicnn-msd-1.pb \
  "https://essentia.upf.edu/models/legacy/classifiers/moods_mirex/moods_mirex-musicnn-msd-1.pb"

# 验证下载
ls -lh models/*.pb
```

## 🔍 discogs模型查找指南

如果 `discogs-effnet-bs64-1.pb` 的URL不正确，请：

1. 访问: https://essentia.upf.edu/models/feature-extractors/discogs/effnet/
2. 查看目录列表，找到包含 `discogs-effnet-bs64-1` 的目录
3. 进入该目录，找到 `.pb` 文件
4. 右键点击文件，选择"复制链接地址"
5. 使用该URL下载

**可能的URL格式**:
- `https://essentia.upf.edu/models/feature-extractors/discogs/effnet/discogs-effnet-bs64-1/discogs-effnet-bs64-1.pb`
- `https://essentia.upf.edu/models/feature-extractors/discogs/effnet/discogs-effnet-bs64-1.pb`
- `https://essentia.upf.edu/models/classifiers/genre_discogs400/discogs-effnet-bs64-1.pb`

## ✅ 验证

下载完成后，检查文件大小：

```bash
ls -lh models/*.pb
```

**正确的大小**:
- voice_instrumental-musicnn-msd-2.pb: ~3 MB ✅
- discogs-effnet-bs64-1.pb: ~18 MB ⚠️
- deeptemp-k16-3.pb: ~1.3 MB ✅
- danceability-musicnn-msd-1.pb: ~3 MB
- moods_mirex-musicnn-msd-1.pb: ~3 MB

如果文件只有153字节，说明下载失败（下载了HTML错误页面）。

