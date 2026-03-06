# Kat Records 频道文档

**频道 ID**: `kat`  
**频道名称**: Kat Records  
**最后更新**: 2025-01-XX

---

## 📋 频道概述

Kat Records 是一个专注于 Lo-Fi Jazz-Hop、vinyl warmth 和深度专注音乐的虚拟唱片厂牌。

### 频道定位

- **内容类型**: Lo-Fi Jazz-Hop, Vinyl Warmth, Deep Focus Music
- **典型时长**: 60 分钟（双面 LP 格式）
- **核心特色**: 情感捕捉、夜间色调、文学性、精致、永恒

---

## 📁 频道结构

```
channels/kat/
├── channel_profile.json    # 频道元数据
├── config/
│   └── channel.json        # 频道配置（时区、发布时间等）
├── library/
│   ├── songs/              # 音频库
│   └── tracklist.csv       # 曲目列表（含时长信息）
├── output/                 # 输出目录
│   └── {episode_id}/       # 每期节目输出
└── docs/                   # 频道文档
    └── README.md           # 本文件
```

---

## ⚙️ 配置说明

### `config/channel.json`

```json
{
  "timezone": "UTC+7",
  "publish_time_local": "23:00",
  "channel_type": "kat"
}
```

### `channel_profile.json`

包含频道的 YouTube 元数据、描述等信息。

---

## 🎯 制播流程

Kat 频道使用 McPOS 标准流程：

1. **INIT** - 生成 `playlist.csv` 和 `recipe.json`
2. **TEXT_BASE** - 使用 AI 生成标题、描述、标签
3. **COVER** - 生成 4K 封面图片
4. **MIX** - 生成混音音频
5. **TEXT_SRT** - 生成字幕文件
6. **RENDER** - 生成 4K 视频

---

## 📝 使用示例

```bash
# 初始化一期节目
python3 -m mcpos.cli.main init-episode kat kat_20251201

# 运行完整流程
python3 -m mcpos.cli.main run-episode kat kat_20251201

# 运行单个阶段
python3 -m mcpos.cli.main run-stage kat kat_20251201 TEXT_BASE
```

---

## 🔗 相关文档

- [McPOS 使用指南](../../mcpos/Doc/USAGE_GUIDE.md)
- [频道制播规范](../../mcpos/Doc/CHANNEL_PRODUCTION_SPEC.md)
- [Dev_Bible](../../mcpos/Dev_Bible.md) - Kat 频道配置（第 9 节）

