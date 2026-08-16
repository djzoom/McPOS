# McPOS — 代码库工作规约

多频道 YouTube 内容生产系统。三个频道：**KAT**（LoFi 电台）· **RBR**（跑步音乐，
真代码不在本仓，见下）· **SG**（Sleep in Grace，睡前祷告冥想）。

本仓当前的活口是 **SG 长片线**（`scripts/sg/`）。**频道已于 2026-08-15 开播。**

> ## 🔄 新会话从这里开始
> ```bash
> ./.venv/bin/python scripts/sg/sg_status.py            # 现在到哪了(一屏)
> ./.venv/bin/python scripts/sg/daily_ops.py --dry-run  # 今天该做什么
> ```
> 交接文档 **`scripts/sg/RESUME.md`**（现状 / 下一件大事 / 八个别再踩的坑）。
> 状态一律现场读，不看写死的数字。管线冻结清单见 `scripts/sg/PIPELINE_FREEZE.md`。

## ⚠️ 三条会出事的红线

### 1. `origin` 是**公开仓库**，而工作区里躺着密钥

`origin` = `github.com/djzoom/McPOS`（**public**）。工作区常年有 60+ 未提交项，其中：

- `config/google/` —— OAuth token 与 client_secrets
- `config/config.yaml` —— Claude API key

**它们没有被 .gitignore 挡住。** 在这个仓库里**永远不要 `git add -A` / `git add .`**，
逐路径暂存。（该加进 .gitignore，但一直没加——见第三节待办。）

### 2. 本地有一条**脏历史分支**，别拿它覆盖远端

`backup/pre-graft-20260808` 是 2026-07-20「全仓清洗 AI 署名」**之前**的旧历史，
带 7 处 `Co-Authored-By: Claude`。远端 `origin/cleanup/modularization` 是干净的那份。
**force-push 会把 AI 署名推回远端，撤销那次清洗。**
2026-08-08 入库 `scripts/sg/` 时是靠「把提交嫁接到 origin 干净历史上快进推送」解决的，没用 force。

### 3. `legacy` remote 指向的 `djzoom/Kat_Rec` 是 **private + archived（只读）**

那是本仓的旧仓库，不能作为推送目标。要推得先解归档。

## 🔴 原子音频库的健康危机（2026-08-08 全量体检）

**成片里能听到语音与文字对不上——这不是错觉，是 65% 的原子有问题。**

```
2271 个 mp3 · 完全健康仅 782（34.4%）
  句中切断 583   有人声但与 text 不符 ← 语音文字混乱主因
  固定切长 713   时长恰好 1.09s，按长度切而非按语音边界
  文字塌缩 469   403 个原子共享同一句 text，另 328 个共享另一句
  静音     405   max < -40 dB
  从未复核 453   G1/G2 三支母带的原子，审计根本没覆盖
```

### 故障链（三段，每段都有实测证据）

**① whisper 在两支母带上产生大量幻觉词。** `atoms/harvest_whisper.log` 的 `words=`：

| 母带 | 时长 | words | 词/分钟 |
|---|---|---|---|
| `Rest_Secure…` | 13.4 min | 4086 | **305** ⚠ |
| `0906Fall…` | 16.3 min | 3109 | **191** ⚠ |
| 其余 8 支 | — | — | 58–124（正常） |

睡前祷告正常是 58–75 词/分钟。whisper 把静音段听成成串的 `you` / `Thank you.`
（它在静音上的经典幻觉，`sg_atom_audit.json` 的 `heard` 字段里到处都是）。
**日志里 error/fail/warn 命中 0 行——整个过程没有任何报错。**

**② 词级切分照幻影词切，切出 ~1.09s 的碎片。** 780/986 病态原子只来自那两支母带。

**③ 选曲门禁根本不看音频。** `build_session.py` 只导入了 `reject_reason`：

```python
from atom_quality import reject_reason   # 判据仅三条：是否隔离 / 有无文本 / 词数>=3
```

**它只检查 text，不检查音频与 text 是否一致。** 病态原子的 text 是完整句子（8 个词），
轻松过关。白名单 `config/sg_atom_whitelist.json`（827 个通过 whisper 复核）
**08-05 04:55 就生成好了，但没有任何代码消费它**——qc01~qc08 都建于其后，照样用了 42–46% 病态原子。

> `atom_quality.py` 里其实还有 `fragment_reason()`（查波形切穿、句末标点、虚词结尾）
> 和 `standalone()`，能拦住一部分碎片——**但 build_session 没导入它们**。

### 受影响的成片（都还没上传，万幸）

`qc07 46%` · `qc03 45.6%` · `qc04 44.5%` · `qc06 44.4%` · `qc08 43.2%` · `qc05 42.4%` ·
`qc01 31.8%` · `qc02 29.6%` · `sg_toytune_ep1 26.3%`
干净的：`sg_locke_demo_001/002/003`、`sg_locke_v2_001`（7 月底建，坏母带入库之前）

### 体检工具

`scripts/sg/audit_atom_health.py` —— 可重复跑，对齐 manifest / 审计 / 文件系统三个来源。

```bash
python scripts/sg/audit_atom_health.py                # 全量（约 3 分钟）
python scripts/sg/audit_atom_health.py --limit 200    # 快速抽查
python scripts/sg/audit_atom_health.py --json out.json
```

### 修复三层

1. ~~**止血**~~ ✅ 2026-08-10 完成：白名单成为 `atom_quality.reject_reason` 的
   显式第三道门（选片/盘点侧传入 `load_whitelist()`，审计侧不传——它们是
   产出复核数据的一环，卡白名单是循环依赖）。消费方：`build_session` /
   `inventory` / `build_tts_batch`。可用原子 2214 → **728**（白名单 827 中
   99 条另被隔离/词数门拒）。验收：试排一期 68 原子全部在白名单内；
   20 期连排 20/20 出片、A 层零失败。**但平均重叠 24.9%、最高 85.7%，
   未达稳定标准——池子太小，靠补料解决，不是代码问题。**
   顺带修复：`build_session.py` 的 `a.minutes` NameError（08-08 入库时的
   笔误，之后编排器从未成功跑通过）。
   另发现：盘点槽位模型说 BLESS 池=0/可出 0 期，但编排器用 close 角色
   回退填了 BLESS——两者对 BLESS 槽位角色的判据不一致，待对齐。
2. **补料**：重跑那两支母带的 harvest（开 VAD / 调 no-speech 阈值压幻觉）；
   顺带审计从没查过的 453 个（复核通过即可扩充白名单，直接缓解重叠率）
3. **重建**：8 支 qc0x + `sg_toytune_ep1` 作废重建

## SG 线的其它现状

- **一期都没上传过**：`config/sg_quota_ledger.json` 的 `spent: 1`（仅一次身份确认）
- 排播主表只有 **1 期**（`sg_toytune_ep1`），发布日 2026-08-05 **已逾期**
- SG 的 OAuth token expiry `2026-08-03`，已过期（有 refresh_token）
- 产出在 `~/Studio/Workspace/outputs/sg/sessions/`（33 个 session，5.7G）

## 关键文件

| 文件 | 行 | 职责 |
|---|---|---|
| `scripts/sg/build_session.py` | 1658 | 会话编排器（冻结 v1）。原子选择、静默曲线、混音 |
| `scripts/sg/harvest_whisper.py` | 516 | 母带 → 原子采集（whisper 词级切分 + 分组）← **故障源头** |
| `scripts/sg/render_rings_long.py` | 483 | 金环层渲染器。事件从既有音频**反导** |
| `scripts/sg/qc_session.py` | 311 | 验收层（A 文案 6 项 / B 音频 3 项） |
| `scripts/sg/vo_score.py` | — | VO 检测门（时序/清晰度/结构打分，≥95 放行，2026-08-10 新增，内建于 build_session） |
| `scripts/sg/audit_atom_edges.py` | — | 量原子**自身**尾部电平 → `tail_hard_cut`；兼查 manifest 时长漂移（2026-08-11 新增） |
| `scripts/sg/repair_session.py` | — | 对既有成片只做 DROP：剪掉坏原子后原地重出 VO/字幕/混音（2026-08-11 新增） |
| `scripts/sg/audit_fragment_artifacts.py` | — | 靠统计指纹揪采集痕迹：等长切割 + 截断重复（2026-08-12 新增） |
| `scripts/sg/release_gate.py` | — | **单一发布裁决**：R1 产物齐全 / R2 内容 / R3 VO≥95 / R4 音画 / R5 边界 / R6 中文字幕 / R7 时长（2026-08-12 新增） |
| `scripts/sg/build_until_pass.py` | — | 换种子重排直到过 95 分门槛——保标准，不降标准（2026-08-12 新增） |
| `scripts/sg/build_zh_srt.py` | 193 | 译表 + 英文 SRT → 简繁中文 SRT，十道门禁；**不做翻译** |
| `scripts/sg/atom_quality.py` | 96 | 选曲判据 ← **只看文本，不看音频，是漏网的地方** |
| `scripts/sg/audit_atom_health.py` | — | 全量健康体检（2026-08-08 新增） |

**文档**：`scripts/sg/VO_PIPELINE.md`(211) 冻结版 v1 + 七条铁律 · `UPLOAD_README.md`

**跨仓依赖**：`render_rings_long.py` 的背景图 hardcode 读 **TOYTUNE 的**
`~/Projects/TOYTUNE/assets/backgrounds`（384 张）。动那个图库会静默改掉长片画面。

## Git 纪律

- 提交身份：`user.name=0xGarfield` `user.email=djwangzhong@gmail.com`
- **绝不添加任何 AI 署名**（2026-07-20 用户令，全仓库史已清洗）：提交信息里禁止
  `Co-Authored-By: Claude` 尾注与 `Generated with Claude Code` 行。Claude 是工具，不是贡献者。
- 当前分支 `cleanup/modularization`，与 `origin/cleanup/modularization` 同步。

## 冻结状态

SG 长片线已冻结为 **v2（2026-08-13）**，清单见
`scripts/sg/PIPELINE_FREEZE.md`：核心链路 17 个脚本、辅助线与废弃线的分类、
每条判据的实测依据、以及改动后必须重跑的三项验收。

## 发布前必过：`release_gate.py`

```bash
./.venv/bin/python scripts/sg/release_gate.py --session sg_gold_001   # 单期，含 R4
./.venv/bin/python scripts/sg/release_gate.py --all --fast            # 全部，跳过 whisper
```

七关任一不过即不可发布。**`--fast` 只用于迭代中途自查**——只有 R4 能发现
音频与字幕对不上，发布前必须跑全套。门禁一律现场重算，不读 session.json
里存的旧结论（qc03 实测：读快照会把 45.6% 病态原子的一期判成全绿）。

## 原子库现状（2026-08-12 全量复核后）

```
2214 条 · 可用约 1290（此前白名单只放行 728）
  逐条转写复核 1396 条：完全一致 98.4% · 仅转写差异 1.6% · 不符 5 条已隔离
  隔离：no_speech 432 · fixed_length_cut 85 · text_mismatch 69
        truncated_duplicate 11 · self-deification 11 · dropped_in_review 10
        misread_negation_lost 1
  自由可用唯一文案约 770 → 瓶颈槽位 CLOSE（仅 7 条唯一强结尾）
```

**剪掉即除名**：`repair_session.py` 从成片剪掉的原子，默认同时写入
`quarantined=dropped_in_review`。此前只剪不除名，导致第 1/2/3 期各自剪掉的
坏句在第 4 期又被选了回来，一轮轮重演。

**连排能力受素材而非算法限制**：cooldown 窗口 12 期 × 每期约 100 句 = 需要
1200 条不同文案，实有 771。8 期连排平均重叠 5.5%、最高 12.9%（门槛 25%/60%）；
20 期则必然超标——`stability_check.py` 现在会明确指出这是供给不足而非编排缺陷。

## 待办

- [ ] 把 `config/google/` 与 `config/config.yaml` 加进 `.gitignore`（公开仓库，现在只靠「记得别 add -A」挡着）
- [ ] 原子库修复：~~① 止血~~ ✅ → ② 补料 → ③ 重建（见上）
- [ ] SG OAuth 重新授权
- [ ] 盘点与编排器对 BLESS 槽位角色回退的判据对齐（止血验收时发现）
- [x] 尾词被削的源头治理（2026-08-11）：`tail_cut`（母带丢词）与 `tail_hard_cut`
      （自身满音量）两项独立证据**双证**才算确凿；补救容差从 18s 收到 0.35s。
      顺带修掉 222 条 manifest 时长漂移。详见 VO_PIPELINE 第 2′/2″ 节。
- [x] 英文 SRT 排版修正（2026-08-12）：`subtitle_typography()`，烧录字幕与外挂
      SRT 共用同一函数，不会分头演化。
- [ ] 库里仍有一条已知坏原子未除名：`Psalm 34, verse 18. Psalm 34, verse 18.`
      （出处重复）。它不在任何成片里，故没走「剪除即除名」的路径。
- [ ] 补料（G3 录制）：按 `scripts/sg/ATOM_SUPPLY_PLAN.md` 执行——三条轨道
      （零成本回收 → 按杠杆装箱录制 → 结构杠杆），每批五道验收门。
      现状 7 期不重样，瓶颈 CLOSE（仅 7 条唯一收尾）；4 个月到供需比 ≥1.0。
- [x] VO 检测门（2026-08-10）：`vo_score.py` 内建于 build_session，六个编排
      缺陷修复后 30 个种子（含 20 个未调参的）连过 95+，其中 26 个满分。
      细节见 `scripts/sg/VO_PIPELINE.md`「VO 检测门」一节。
