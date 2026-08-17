# SiG 长片管线 — 冻结版 v2（2026-08-13）

> **⚠ 2026-08-17 起本文档只是原子时代的存档。** 用户裁定原子拼接成片
> 太碎太密,长片一律改走**分子管线**(段落级整块,见 `RESUME.md` 第〇/二节):
> `harvest_molecules → molecule_quality → build_molecule_session → content_gate`。
> 原子库与本清单仍服务 TOYTUNE 短片线;`build_session.py` 不再出新长片。

冻结依据：`sg_gold_001`–`004` 四期全部通过 `release_gate.py` 七关（含 whisper
音画反查，WER 0.0–0.3%、零漏句零多出）；8 期连排判定「稳定」（平均重叠 7.0%、
最高 56.3%、门禁零拦下）。

与 v1（2026-08-06）的区别：v1 冻结的是**编排逻辑**；v2 冻结的是**一条带门禁的
生产线** —— 出片、验收、字幕、发布裁决各有其位，且每道判据都有实测依据。

---

## 一、核心链路（冻结范围）

按运行顺序。**这十一个是生产线本体，改动需重跑第五节的验收。**

| 阶段 | 脚本 | 职责 |
|---|---|---|
| 采集 | `harvest_whisper.py` | 母带 → 原子（whisper 词级切分 + 分组） |
| 源头审计 | `verify_atom_texts.py` | 逐条转写复核，产出白名单（唯一权威） |
| 源头审计 | `audit_boundaries.py` | 母带包络 → `head_cut` / `tail_cut` |
| 源头审计 | `audit_atom_edges.py` | 原子自身尾部电平 → `tail_hard_cut`；兼查时长漂移 |
| 源头审计 | `audit_fragment_artifacts.py` | 统计指纹 → 等长切割 / 截断重复 |
| 判据 | `atom_quality.py` | **原子可用性的唯一权威**，所有脚本一律 import 它 |
| 盘点 | `inventory.py` | 槽位供需、能出几期不重样 |
| 编排 | `build_session.py` | 选片、停顿曲线、混音；内建内容门禁 + VO 检测门 |
| 编排 | `build_until_pass.py` | 换种子重排直到过 95 分 —— 保标准，不降标准 |
| 修复 | `repair_session.py` | 对既有成片只做 DROP，**并同步逐出素材库** |
| 打分 | `vo_score.py` | 时序 40 / 清晰 30 / 结构 30，≥95 放行 |
| 验收 | `qc_session.py` | A 文案六项 + B 音频三项（whisper 反查） |
| 字幕 | `build_zh_srt.py` | 译表 + 英文 SRT → 简繁中文，十道门禁；**不做翻译** |
| 视觉 | `render_rings_long.py` | 金环层，事件从既有音频反导 |
| 裁决 | `release_gate.py` | **发布前唯一入口**，七关全过才可发 |
| 稳定性 | `stability_check.py` | 连排 N 期，报重叠度与供给压力 |
| 公共 | `sg_media.py` | ffprobe 封装、备份保留 —— 时长探测只此一份 |

## 二、辅助线（不在冻结范围，但仍在用）

- **补料（G3 录制）**：`build_g3_script.py` · `build_tts_batch.py` · `preflight_tts.py`
- **标注维护**：`reclassify_roles.py` · `tag_addressee.py` · `trim_atom_edges.py`
- **专项筛查**：`screen_blasphemy.py` · `screen_pronunciation.py` · `screen_truncation.py`
- **覆盖率**：`audit_master_coverage.py` · `audit_atom_health.py` · `purge_empty_atoms.py`
- **上传**：`sg_upload.py` · `sg_batch_upload.py` · `sg_verify_uploads.py` · `upload_meta.py` · `quota.py` · `episode_meta.py`
- **其它频道**：`toytune_episode.py` · `render_video_slow.py`
- **已废弃**：`legacy/`（12 个）· `translate_polished.py` · `translate_text_batch.py`
  （text_batch_10 那条 TTS 稿件线，2026-08-04 翻译事故后停用）

## 三、判据一览（每条都有实测依据）

> 间隔常量（`MAX_OVERLAP` / `WAVEFORM_REPAIR_GAP` / `SYNTAX_REPAIR_GAP` /
> `FLOW_GAP`）**只定义在 `atom_quality.py`**。出片端与验收端互不能 import
> （会成环），曾各持一份同名常量 —— 那是「同一概念两处判据」的标准起手式。
> 改阈值只改 atom_quality 一处，两端同时生效。

| 判据 | 阈值 | 依据 |
|---|---|---|
| 语速上界 | 3.5 词/秒 | 只设上界；下界当年已证明是误判（慢读是设计） |
| 尾词被削 | `tail_cut` **且** `tail_hard_cut` | 584 条干净原子尾部电平上界 −2.6 dB → 阈值取 −3.0 |
| 波形修复容差 | 0.35s | 被削的半个词只可能在紧挨着的下一条里 |
| 语法续句容差 | 8.0s | 已交付三期 15 对真实续句，间隔 −0.09～6.63s |
| 语流衔接容差 | 18.0s | 刻意的长停顿，两句各自完整 |
| 等长切割 | 某时长条数 > 中位数 ×20 | 1.09s 上堆 156 条，次高仅 17 条 |
| VO 检测门 | ≥95 | 悬空句扣 8（扣 5 会让坏片正好卡 95.0 擦边） |
| 连排稳定 | 均<25% · 峰<60% | 8 期实测 7.0% / 56.3% |

## 四、两条铁律（v1 起未变）

1. **文本迁就音频**。原录音里没说过的词，一律不得出现在剧本里。
   允许的操作只有 **DROP** 与**排版修正**（标点、大小写）。
2. **禁止**：加词改词、跨原子合并、原子内部再切（边车没有词级时间戳，
   而 whisper 会在静音上脑补熟悉的经文）。

## 五、冻结验收（改动核心链路后须全部重跑）

```bash
cd ~/Studio/Projects/McPOS

./.venv/bin/python scripts/sg/inventory.py                      # 库存与瓶颈
./.venv/bin/python scripts/sg/stability_check.py --episodes 8   # 须判定「稳定」
./.venv/bin/python scripts/sg/release_gate.py --all             # 四期须全绿（不加 --fast）
```

三项全过才算冻结成立。`--fast` 只用于迭代中途自查 —— 只有 R4 能发现音频与
字幕对不上。

## 五点五、冻结复审记录（2026-08-13 细查）

- ✅ 间隔常量收归 `atom_quality`（曾在编排/打分两端各一份，漂移隐患）
- ✅ `stability_check` 历史沙箱化：此前每跑一次连排，`episode_history` 里
  正式成片的记录就被 day00x 测试数据覆盖 —— 下一期真实出片会忘了已交付
  期次用过什么。现在备份→跑→finally 恢复；生产历史已按四期成片重建。
- ✅ `session.json` 新增 `grammar_path`：release_gate R2 与 repair_session
  现场重算门禁时不再只能猜默认语法。
- ✅ `_DANGLING` 词表在 1290 条全库上实测：13 处命中全部真悬空，零误报。
- ✅ `audit_plan_content`（18s 单一容差）比 vo_score（三档）宽松 ——
  方向安全：两道门都要过，严的兜底。刻意不同步,避免改两处。

## 六、已知边界

- **产能受素材限制，不受算法限制**：自由可用唯一文案约 770 条，只够 7–8 期
  不重样；连排 20 期需约 1200 条。这是缺口，调任何参数都补不上。
- 库里仍有一条已知坏原子未除名：`Psalm 34, verse 18. Psalm 34, verse 18.`
  （出处重复）。它不在任何成片里，走不到「剪除即除名」的路径。
- `head_cut` 只有母带证据，没有像 `tail_hard_cut` 那样的直接测量 ——
  语音起音本来就陡，按同样方法量首部会把频道招牌判成「首词被削」。
