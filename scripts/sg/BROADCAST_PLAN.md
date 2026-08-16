# 📌 播出计划（置顶 · 2026-08-15 **频道已开播**）

> **2026-08-15 07:14 ET 开播**：长片 Ep1 与短片 ep001 同时转为公开，
> 不再等定时。此后长片每周六 19:00 ET 一期，短片每天 21:00 ET 一条。

节奏：**每周 1 长（周六 19:00 ET）+ 每晚 1 短（21:00 ET）**，周配比 1:7。
短片是入口、长片是归宿；短片在当周长片之后上线，点进频道即有得听。

## 一、长片线（8 期已全部制作完成）

排播真源 `config/sg_schedule_master.json`；标题真源 `upload_meta.EPISODE_TITLES`。
封面：Codex 生成的统一视觉家族（金环绕十字 / 午夜蓝 / 右侧衬线经文出处），
八期各有细节变化（月牙、晨光、双烛、村落灯火、湖面倒影…）。

| # | 周六 | 期号 | 时长 | 视频 ID | 状态 |
|---|---|---|---:|---|---|
| 1 | 08-15 | sg_gold_001 | 18m | HrhngFXygL0 | 🔴 **已公开**（提前开播）|
| 2 | 08-22 | sg_gold_002 | 18m | qFwLBQecFmc | ✅ |
| 3 | 08-29 | sg_gold_003 | 21m | BGdv2ilJemc | ✅ |
| 4 | 09-05 | sg_gold_004 | 18m | YWYYTa8Nai8 | ✅ |
| 5 | 09-12 | sg_gold_005 | 30m | TK6GdGYPkI8 | ✅ |
| 6 | 09-19 | sg_gold_006 | 30m | _mREvXvzDpI | ✅ |
| 7 | 09-26 | sg_gold_007 | 30m | 5wG4L_wAGhQ | ✅ |
| 8 | 10-03 | sg_gold_008 | 30m | — | ⏳ 待传（封面已就位，明日配额窗口）|

全部 private + publishAt 定时公开；已上线七期均经 `sg_verify_uploads` 平台核验。

## 二、短片线（50 期已渲齐，逐日上传中）

排播 `TOYTUNE/shorts_schedule.json` · 08-15 → 10-03 每晚 21:00 ET。

- ep001 🔴 **已公开**（含置顶评论）；已上传 ep002–005 定时每日（l4RBhaZboRA / 5VFE2MOA5GQ / 9dyDbp7tiCQ / UwCWq6JEABQ / b-iWgUZ4-kI）
- 余 45 条按日续传，保持领先公开日 2 天以上即可
- 授权：`TOYTUNE/.youtube_token.json`（由 SG 的 client_secrets 现场铸造，**未复制密钥文件**）

### 置顶评论：挂起待补发

YouTube 不允许给未公开（private+定时）的视频发评论 → 403。
`publish.py` 已改为 **回执先行 + 评论挂起**：video_id 先落盘，评论失败仅标记
`comment_pending`，绝不中断上传批。
（此坑曾造成 ep001 成为孤儿——已找回并补记。）
补发时机：视频公开后，对 `publish_state.json` 中 `comment_pending` 的条目重发。

## 三、配额（与 KAT 共享 10,000u/天）

长片一期 ~2100u · 缩略图 50u · 改期 50u · 短片一条 ~1650u。
2026-08-15 已用 8300u（4 长片 + 7 缩略图 + 3 改期 + 5 短片）。
预算制：`quota.can_afford` 不够即停，403 不重试。

## 四、明日窗口（PT 午夜重置后）

1. 传 Ep8（最后一期长片）→ 核验 → 推封面
2. 短片续传 3–4 条
3. ep001 于今晚公开后，补发其置顶评论
