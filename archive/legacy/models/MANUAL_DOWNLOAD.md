# 手动下载模型指南

如果自动下载失败，请按照以下步骤手动下载模型：

## 📥 必需模型

### 1. discogs-effnet-bs64-1.pb (约18MB)

**步骤**:
1. 访问: https://essentia.upf.edu/models/feature-extractors/discogs/effnet/
2. 找到 `discogs-effnet-bs64-1` 目录
3. 下载 `discogs-effnet-bs64-1.pb` 文件
4. 保存到: `models/discogs-effnet-bs64-1.pb`

**验证**: 文件大小应该约18MB

## 📥 扩展模型（可选）

### 2. danceability-musicnn-msd-1.pb (约3MB)

**步骤**:
1. 访问: https://essentia.upf.edu/models/legacy/classifiers/danceability/
2. 找到 `danceability-musicnn-msd-1.pb` 文件
3. 下载并保存到: `models/danceability-musicnn-msd-1.pb`

**注意**: 这是legacy版本，如果找不到，可以跳过（不影响基本功能）

### 3. moods_mirex-musicnn-msd-1.pb (约3MB)

**步骤**:
1. 访问: https://essentia.upf.edu/models/legacy/classifiers/moods_mirex/
2. 找到 `moods_mirex-musicnn-msd-1.pb` 文件
3. 下载并保存到: `models/moods_mirex-musicnn-msd-1.pb`

**注意**: 这是legacy版本，如果找不到，可以跳过（不影响基本功能）

## ✅ 验证下载

下载完成后，运行以下命令检查：

```bash
ls -lh models/*.pb
```

**正确的大小应该是**:
- voice_instrumental-musicnn-msd-2.pb: ~3 MB ✅
- discogs-effnet-bs64-1.pb: ~18 MB ⚠️ 必需
- deeptemp-k16-3.pb: ~1.3 MB ✅
- danceability-musicnn-msd-1.pb: ~3 MB ⏭️ 可选
- moods_mirex-musicnn-msd-1.pb: ~3 MB ⏭️ 可选

如果文件只有153字节，说明下载失败（可能下载了HTML错误页面）。

## 🔍 如果找不到文件

1. **检查目录结构**: 访问 https://essentia.upf.edu/models/ 查看完整的目录结构
2. **查找替代版本**: 某些模型可能有不同的版本号（如 `-1.pb`, `-2.pb`）
3. **使用搜索功能**: 在模型库中搜索模型名称

## 💡 提示

- **必需模型**: 只有 `discogs-effnet-bs64-1.pb` 是必需的，其他都是可选的
- **Legacy模型**: 如果legacy目录下的模型不可用，可以跳过扩展功能
- **基本功能**: 只要有 `voice_instrumental-musicnn-msd-2.pb` 和 `discogs-effnet-bs64-1.pb`，基本功能就可以使用

