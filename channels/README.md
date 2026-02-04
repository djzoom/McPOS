# 频道目录

本目录包含所有 McPOS 频道的配置、资源和文档。

---

## 📁 频道列表

### Kat Records (`kat`)

- **目录**: `channels/kat/`
- **类型**: Lo-Fi Jazz-Hop, Vinyl Warmth
- **文档**: [channels/kat/docs/README.md](./kat/docs/README.md)
- **配置**: `channels/kat/config/channel.json`

### Run Baby Run (`rbr`)

- **目录**: `channels/rbr/`
- **类型**: 跑步音乐、节奏训练、BPM 精准匹配
- **文档**: [channels/rbr/docs/README.md](./rbr/docs/README.md)
- **配置**: `channels/rbr/config/channel.json`

---

## 📐 标准目录结构

每个频道都应遵循以下目录结构：

```
channels/{channel_id}/
├── channel_profile.json    # 频道元数据（YouTube 信息等）
├── config/
│   └── channel.json        # 频道配置（时区、发布时间、频道特定参数）
├── library/
│   ├── songs/              # 音频库
│   └── tracklist.csv       # 曲目列表（可选，Kat 频道需要）
├── output/                 # 输出目录
│   └── {episode_id}/       # 每期节目输出
└── docs/                   # 频道文档
    └── README.md           # 频道说明文档
```

---

## 🔧 配置文件说明

### `channel_profile.json`

包含频道的公开元数据：
- 频道 ID、名称、handle
- YouTube 频道 URL
- 频道描述
- YouTube 统计数据

### `config/channel.json`

包含频道的运行时配置：
- 时区设置
- 发布时间
- 频道特定参数（如 RBR 的 BPM 范围）

---

## 📚 相关文档

- [McPOS 使用指南](../mcpos/Doc/USAGE_GUIDE.md)
- [频道制播规范](../mcpos/Doc/CHANNEL_PRODUCTION_SPEC.md)
- [Dev_Bible](../mcpos/Dev_Bible.md) - 频道配置规则

---

## 🆕 添加新频道

要添加新频道，请：

1. 创建 `channels/{channel_id}/` 目录
2. 创建标准目录结构
3. 创建 `channel_profile.json` 和 `config/channel.json`
4. 在 `docs/README.md` 中编写频道文档
5. 在 `mcpos/Dev_Bible.md` 中添加频道配置说明（如需要）

