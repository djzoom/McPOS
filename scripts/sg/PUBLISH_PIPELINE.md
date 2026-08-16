# SG 发布管线架构（2026-08-14 勘探定稿）

生产线（冻结 v2）产出成品;本文回答**成品之后**的一切:SEO、排播、上传、
短视频引流。结论先行:**发布栈已基本建成,唯一断点是 OAuth 授权**。
大量设计直接继承 KAT / RBR 的实战教训,出处随文标注。

## 〇、全景

```
                     ┌─ 长视频线(本仓 scripts/sg) ─────────────────┐
 release_gate 七关 → episode_meta(内容→SEO) → upload_meta(定稿+主表) │
                   → quota.can_afford → sg_upload/sg_batch_upload    │
                   → sg_verify_uploads(上架后核验)                    │
                     └───────────────────────────────────────────────┘
                     ┌─ 短视频线(~/Projects/TOYTUNE) ───────────────┐
 render_shorts(S1/S5/S7 · 28.8s 完美循环) → shorts_copy(文案真源)    │
                   → publish.py package/verify/upload(排期+断点续传)  │
                     └───────────────────────────────────────────────┘
 两线共用:shorts_copy.SCRIPTURES 经文策展(22 条 KJV+转折句) ——
 短视频与长视频对同一节经文的说法**由构造保证一致**。
```

## 一、长视频 SEO —— 标题从成片里读出来,不是贴上去的

`episode_meta.py --session <期> --episode <号>`:扫 plan 找出本期**实际念到**
的经文,取最主要一处作题眼。实测(sg_gold_005):检出 Psalm 127:2 + 42:5,
生成 97 字符标题、完整简介(含 KJV 原文、"voice rests after 17 minutes"
时长承诺、金环因果一句)、9 个标签。构造性一致 —— 不会出现「标题写诗篇 23、
片中一句没念」。

SEO 家规(继承 RBR,写在 upload_meta.py):
- 时长进标题(助眠观众按时长搜)· 经文出处写全(Psalm 46:10 是搜索词)
- 关键词前置、品牌靠后 · 期号让系列可被追 · 不用句号(Kat/RBR 家规)
- **只动未发布期**;标题回写主表前自动落 .bak 与回滚收据

定稿流:episode_meta 生成草稿 → 人审后写入 upload_meta.EPISODE_TITLES
(真源)→ `--sync-check` 回写排播主表。
⚠ 已知张力:EPISODE_TITLES 目前只有第 1 期,其余期若跳过人审直接用生成稿,
须明确「生成即定稿」——两处真源不能长期并存(同一概念两处判据的老坑)。

## 二、排播与配额 —— 预算制,不是重试制

- 主表 `config/sg_schedule_master.json`:每日 19:00(+07:00)一期。
  现仅 1 行且指向已作废的 sg_toytune_ep1,**待用 sg_gold_001–008 重排**。
- `quota.py`(继承 RBR):上传一期约 **2150u**,SG 与 KAT 同属项目
  gothic-context-439714-t3,**共享 10,000u/天** → 每天最多安全传 4 期;
  can_afford() 不够即停,403 不重试(重试也计费)。
- 单链路锁 `~/Studio/Workspace/temp/_locks/upload_link.lock`(2026-07-17
  血的教训):非阻塞,拿不到即退出。⚠ KAT 的旧上传器**无锁**,SG 单方面
  持锁挡不住它 —— 两频道同日上传前先人工确认 KAT 空闲。

## 三、上传执行

```bash
python scripts/sg/sg_upload.py auth --secrets <client_secret>.json   # ← 唯一断点,需人工
python scripts/sg/sg_upload.py status                                # 凭证体检
python scripts/sg/sg_batch_upload.py …                               # 批量,走配额账本
python scripts/sg/sg_verify_uploads.py                               # 上架后核验
```

2026-08-14 实测:client_secrets 在位,refresh token **已被撤销**
(invalid_grant),必须重新 auth —— 这是全链路唯一需要人的步骤。
凭证按频道隔离(config/google/sg/),与 KAT 互不污染。

## 四、短视频线 —— TOYTUNE 就是 SG 的 shorts 管线(已建成)

`~/Projects/TOYTUNE`:三个系列共用一个引擎,**28.8s 完美循环**(几何、
和声、音频尾同时闭合,循环即观看时长)。S1 金线轨道与长视频金环同源 ——
观众从 short 到长片看到的是同一个世界。

- 策略:`SHORTS_GUIDE.md`(engaged view / 循环≈200% 观看 / 标题 45 字符
  截断 / y>1450 安全区 / 置顶评论驱动分发 / Related video 挂长片……
  每条机制都对应一个管线动作,这份文档本身就是可执行的 SEO 教材)
- 文案真源:`shorts_copy.py`(与长视频共用经文策展)
- 排期:`shorts_schedule.json` · 每晚一条,固定档位养习惯
- 发布:`publish.py package / verify / upload --dry-run / auth`
  (封面、清单、平台合规校验、断点续传、排期、Related video 全在)

**SG 短视频不需要新建管线,需要的是恢复运行**:TOYTUNE 的 OAuth 状态
待查(`publish.py auth`),shorts_schedule 与长片排播对齐即可。

## 五、恢复发布的行动清单(按序)

| # | 动作 | 谁 | 状态 |
|---|---|---|---|
| 1 | `sg_upload.py auth` 重授权(浏览器交互) | **用户** | ⛔ 唯一阻塞 |
| 2 | 排播主表重排:sg_gold_001–008,每日一期 | 管线 | 待做 |
| 3 | episode_meta 批量生成 8 期元数据 → 定稿入 EPISODE_TITLES | 管线+人审 | 待做 |
| 4 | 首日上传 ≤4 期(配额),sg_verify_uploads 核验 | 管线 | 等 #1 |
| 5 | TOYTUNE `publish.py verify` + auth 状态查验,shorts 排期对齐 | 管线 | 待做 |
| 6 | KAT 上传器加锁(挡共享配额踩踏) | 管线 | 记入待办 |
