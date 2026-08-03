# 上传管线 Playbook（从 kat 频道抽象，供新频道复制）

**来源**：Kat Records（`channels/kat/`）跑通 700+ 期的实际管线，2026-08-03 抽象。
所有条目都对应磁盘上可核查的真实产物，不是设想。

---

## 一、逐期产物契约（管线的接口）

每期一个目录 `Workspace/outputs/<ch>/<ch>_<yyyymmdd>/`，上传器只认这份契约：

| 文件 | 作用 | 备注 |
|---|---|---|
| `<ep>_youtube.mp4` | 成片 | 上传主体 |
| `<ep>_cover.png` | 封面源图 | 缩略图另生成 ≤2MB 的 `temp/<ch>/thumbs/<ep>_cover_thumb.jpg` |
| `<ep>_youtube_title.txt` | 标题 | ≤100 字符 |
| `<ep>_youtube_description.txt` | 描述 | ≤5000 字节，含固定链接/署名模板 |
| `<ep>_youtube_tags.txt` | 标签 | 总长 ≤500 字符 |
| `<ep>_youtube.srt` | 字幕 | 可选 |
| `<ep>_final_mix.mp3` + `_timeline.csv` | 混音与时间轴 | 溯源用，上传不需要 |
| `recipe.json` | 生成配方 | 可复现该期 |
| `metadata_v1/` | 元数据历史版本 | 改元数据时旧版进版本目录，不覆盖 |
| **`<ep>_render_complete.flag`** | 渲染完成标记 | 上传器的**前置门** |
| **`<ep>_upload_complete.flag`** | 上传完成标记 | **幂等门**：存在即跳过，重跑安全 |
| `<ep>_youtube_upload.json` | 上传回执 | `{episode_id, channel_id, video_id, video_url, status, uploaded_at}` |

## 二、工作流（六个阶段，每阶段有验收）

```
产物就绪 → 元数据验收 → 排播 → 上传执行 → 回执验证 → 对账监控
```

1. **产物就绪**：契约文件齐全 + `render_complete.flag` 存在。缺任何一项不进下一步。
2. **元数据验收**：标题/描述/标签长度合规；描述模板变量已替换（无 `{placeholder}` 残留）。
3. **排播**：`channels/<ch>/schedule_master.json` 是**唯一真源**；任何写入前先落
   `schedule_master.json.bak_<yyyymmdd>`（kat 现行做法）。发布时间由它决定，不由上传时刻决定。
4. **上传执行**：
   - OAuth 凭证在 `config/google/`，token 过期自动刷新，刷新失败要报警而不是静默跳过。
   - **单链路锁（血的教训）**：上传链路必须持 `upload_link_lock`，且语义是**非阻塞——
     拿不到锁立刻退出**。排队语义会让第二条链路在第一条结束后把同一批再传一遍：
     2026-07-17 双链路并发把 193–207 期传成两份并打爆当日 API 配额
     （RBR `render_lock.py` 注释与 `docs/yellow_publish_freeze.md` 有完整事故记录）。
   - **配额预算**：YouTube Data API 默认 10,000 units/天；`videos.insert` 1600、
     `thumbnails.set` 50、`captions.insert` 400、`videos.update` 50。
     一期全流程 ≈ 2100 units → 每天上限 ~4 期。上传前检查当日已用量，不够就停，
     不要撞 403 之后重试（重试也计费）。
5. **回执验证**：写 `youtube_upload.json`（含 `video_id`）→ 校验视频可访问、排期时间
   与排播表一致、缩略图已挂上 → 最后才落 `upload_complete.flag`。
   **flag 是验证通过的结论，不是上传动作的副产品。**
6. **对账监控**：状态脚本一眼看全批次（`kat_batch_status.sh` 模式：每期
   渲染/上传/排期三列）；`production_log.json` 记录史；低表现期回补有据可查
   （`regen_kat_low_view_backlog.py` 模式）。

## 三、新频道接入检查清单

**身份与授权**
- [ ] `channels/<ch>/channel_profile.json`：id/name/handle/channel_url/描述（照 kat 的字段）
- [ ] OAuth：同一 Google Cloud project 则**共享配额**——上传锁与配额预算必须跨频道共享；
      新 project 则单独申请、单独存 token，路径按频道隔离
- [ ] YouTube 频道默认设置：分类、语言、可见性（先 private/scheduled，验证后转)

**目录与命名**
- [ ] `Library/<ch>/`（songs/images/catalog）、`Workspace/outputs/<ch>/`、`Workspace/temp/<ch>/thumbs/`
- [ ] `channels/<ch>/output` → 符号链接到 outputs 目录（kat 现行做法）
- [ ] 命名前缀 `<ch>_<yyyymmdd>` 全线一致

**排播与执行**
- [ ] `schedule_master.json` 初始化 + 备份策略
- [ ] 上传锁：确认与现有频道**共用同一把锁文件**（同一配额池）
- [ ] 配额预算表：本频道每日期数 × 2100 units，与其他频道合计 ≤ 10000
- [ ] 元数据模板：标题格式、描述模板（固定链接/版权署名）、标签池

**验证与恢复**
- [ ] 幂等标记 + 回执 JSON 格式与 kat 一致（工具可复用）
- [ ] 状态脚本复制改造（`<ch>_batch_status.sh`）
- [ ] 失败演练：token 过期 / 配额耗尽（403 quotaExceeded）/ 网络中断重跑——
      三种情形都必须**不产生重复上传**（靠 flag 幂等 + 非阻塞锁）
- [ ] 首播 3 期人工核对：标题渲染、缩略图、排期时区、字幕挂载

## 四、经验迁移 Prompt（交给建新频道管线的会话）

见 README 同目录，或直接复制下方全文。

```
任务：为频道 <频道名>（代号 <ch>）建立 YouTube 上传管线，复用 McPOS 中 kat 频道的成熟实现。

背景与参考实现（先读再动手）：
- 仓库 ~/Studio/Projects/McPOS，kat 频道在 channels/kat/：channel_profile.json 是频道
  身份档案，schedule_master.json 是排播唯一真源（注意 .bak_ 备份惯例），output 是指向
  ~/Studio/Workspace/outputs/kat 的符号链接。
- 每期产物契约看一个实例即可：~/Studio/Workspace/outputs/kat/kat_20260901/ ——
  重点理解 render_complete.flag（上传前置门）、upload_complete.flag（幂等门，验证通过
  才落）、youtube_upload.json（回执含 video_id）。
- 上传代码在 mcpos/upload/ 与 scripts/uploader/，OAuth 凭证在 config/google/。
- 两条不可违背的教训：
  1) 上传链路必须持非阻塞单链路锁（拿不到就退出，绝不排队）。排队语义在 2026-07-17
     造成双链路把 193–207 期重复上传并打爆当日配额，事故记录见 RBR 仓库
     docs/yellow_publish_freeze.md 与 run_baby_run/render_lock.py 的 upload_link_lock 注释。
     若新频道与 kat 同一 Google Cloud project（共享配额），必须共用同一把锁文件。
  2) 配额是预算制不是重试制：videos.insert 1600 + thumbnails.set 50 + captions 400 +
     update 50 ≈ 2100 units/期，全 project 每日 10000。上传前查当日用量，不足即停；
     403 quotaExceeded 不重试（重试也计费）。
交付标准：
  a) channels/<ch>/ 完整落地（profile/排播表/output 链接），目录命名 <ch>_<yyyymmdd> 全线一致；
  b) 用一期真实产物走通全流程：契约校验 → 元数据长度校验 → 排播 → 上传（先 private）→
     回执验证（video_id 可访问、排期正确、缩略图挂上）→ 落 flag；
  c) 三个失败演练全部通过且零重复上传：token 过期、配额耗尽、中断后重跑；
  d) <ch>_batch_status.sh 状态脚本可用；
  e) 全程不修改 kat 频道的任何文件。
按 ~/Studio/Projects/McPOS/docs/upload_pipeline_playbook.md 的检查清单逐项验收。
```
