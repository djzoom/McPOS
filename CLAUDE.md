# McPOS — 代码库工作规约

多频道 YouTube 内容生产系统。三个频道：**KAT**（LoFi 电台）· **RBR**（跑步音乐，
真代码不在本仓，见下）· **SG**（Sleep in Grace，睡前祷告冥想）。

本仓当前的活口是 **SG 长片线**（`scripts/sg/`）。

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

### 修复三层（尚未动手）

1. **止血**：让 `build_session` 消费白名单，可用原子 2214 → 827
2. **补料**：重跑那两支母带的 harvest（开 VAD / 调 no-speech 阈值压幻觉）；
   顺带审计从没查过的 453 个
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

## 待办

- [ ] 把 `config/google/` 与 `config/config.yaml` 加进 `.gitignore`（公开仓库，现在只靠「记得别 add -A」挡着）
- [ ] 原子库修复三层（见上）
- [ ] SG OAuth 重新授权
