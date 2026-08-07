# SiG 原子音频管线 — 冻结版 v1(2026-08-06)

冻结依据:20 期连排全部出片、A 层零失败、期间平均重叠 12.3%;
渲染样片 qc03 两层验收全过(WER 1.7%、漏句 0、多出片段 0)。

**这条线没有 TTS。** 每一句台词都是 Locke 真实录音的片段(原子),VO 是把
原子按剧本顺序拼起来、中间插入分级静默。因此:

> 文本必须迁就音频,不能反过来。凡是原录音里没说过的词,一律不能出现在剧本里。

允许的操作只有 **DROP**(剔除坏原子)与**排版修正**(标点、大小写)。
禁止:加词改词、跨原子合并、原子内部再切(边车没有词级时间戳)。

---

## 一、门禁全景

### 原子层 —— `atom_quality.py` 是唯一权威

| 判据 | 说明 |
|---|---|
| 词数 ≥3 | 更短的切片没有独立语义 |
| 未被隔离 | `no_speech` / `text_mismatch` / `self-deification` / `misread_negation_lost` |
| `fragment_reason` | **波形证据优先于句法证据**,决定「自由可用」还是「仅可作续接」 |

此前这套判据被抄在五个脚本里各自演化,盘点数字互相矛盾。现在一律
`from atom_quality import ...`。

**不设语速/密度门禁。** 这是助眠频道,缓慢朗读与超大间隔是刻意效果。
曾用 0.9–4.0 词/秒的上下界发现了 418 条「静音挂着别句文本」的原子
(已按 `no_speech` 永久隔离,靠隔离标记即可挡住),但下界是彻底的误判——
"Take a deep breath in." 读满 9 秒是设计,不是缺陷。

### 编排层 —— `build_session.py`

- 加载时按 `reject_reason` 过滤,隔离的原子进不了候选池
- **addressee 一致性**:祷告句(you=上帝)与旁白句(you=听者)不能硬切,
  只能经中性句或静默过渡
- **正向句子闭合**:切在句中的原子必须能被母带后继补完,且后继本身合格
- 祝福/收尾必须自足(不依赖后继补完)且符合语言形态
- **cooldown**:近 12 期用过的原子重罚 40 分

### 验收层 —— `qc_session.py`

A 文案层(秒级,不过不渲染音频):
A1 半截句 · A2 指代硬切 · A3 隔离泄漏 · A4 重复 · A5 CTA · A6 角色错位

B 音频层(分钟级):B1 WER ≤6% · B2 漏句 · B3 多出片段

---

## 二、七条血的教训

### 1. 幻听 ≠「转写失败,沿用旧文本」

`--relabel` 检测到 whisper 幻听("you"/"Thank you.")后选择保留原文本,
于是 **418 条静音永久钉着相邻句子的文本**,合成时渲染成有字幕却无声。
两句文本分别被复制了 217 次和 159 次。

发现它的唯一途径是**出一期 VO 再逆向转录** —— 只看文本永远看不出来。

### 2. 边界问题只能看波形,不能问 whisper

约翰福音 14:1 的原子入库文本是 "Let your hearts be troubled."(与原文
意思相反)。我用「向前多听 2 秒再转写」去找被切掉的前导词,whisper 在
**一段纯数字静音(−99 dBFS)** 上补出了 "Do not" —— 它脑补了熟悉的经文。
照那个结论去修,会把 2 秒静音接进原子里。

波形显示 165.45–168.45 根本没有音频。真相是 **ElevenLabs 漏读了 not**,
按 `misread_negation_lost` 销毁,不可修复。

> **whisper 会脑补它熟悉的文本;波形不会。**

配套工具:`audit_boundaries.py`(RMS 包络判 head_cut/tail_cut)、
`audit_master_coverage.py`(找从未被采集的语音)。

### 3. 加了字段不等于设了门禁

`quarantined` 与 `addressee` 字段都建好了,但编排器加载原子时**不做任何
过滤** —— 11 条已判定「自比上帝」的原子照样能被选进节目。
字段是数据,门禁是代码。

### 4. 按位置/时长兜底分类,必然错

`dur >= 3.0 → poetic` 把 83 条内容倒进 poetic;`bless` 曾只在 `pos>0.75`
才判定,导致 57 条祝福语散落到 7 个角色。分类必须按**语言形态**;
没有语言证据就落 `misc`(显式可见),不要兜底进某个真实角色 ——
错标的 deepen 是隐形毒药,拼进节目才发现语义不对。

顺带发现:331 条好内容原本全落在 misc,因为语法没有能装它们的槽。
主题盘点说「悲伤/失丧 11 条 🔴」,但 misc 里躺着 "Lord, you know the loss
I carry." —— 内容一直都在。新增 `comfort`(旁白安慰)与 `petition`
(祷告祈求)两个角色后归位。

### 5. 同一个概念在两处用不同判据,一定出事

「相邻」这一个概念,踩了四次:

| # | 分歧 | 后果 |
|---|---|---|
| 1 | `successor_of` 按时间找 vs 审计按序号 | 补出的句子中间缺一块 |
| 2 | 重叠容差 −0.15s vs 实测最深 −0.210s | 真续接被判成孤立碎片 |
| 3 | 补句链绕过资格检查 | 复数人称混进单数人称的一期 |
| 4 | 选择端允许祝福位换指代,审计端不允许 | 16 期全报硬切 |

第 4 次之后改了做法:**不再加隐藏规则去同步多处,而是改结构** ——
祝福前插一段静默(`REST_BEFORE_BLESS`)。静默本就是规则认可的切换点,
两端天然一致,而且助眠节目祝祷前本该有停顿。

现在「相邻」只有一个定义:`sequence_index + 1` 且间隔在 `[MAX_OVERLAP, 18.0]`。
下界 −0.25 有实测依据:全库 1388 对相邻原子中 18.5% 有重叠,幅度只有
0.090s 和 0.210s 两档,是采集切分的固定伪影。

### 6. 单期合格 ≠ 稳定

12 期两两**平均重叠 74.4%**,6 句每期都出现 —— 每期单独看都过门禁,
但连看两晚是同一篇稿子。两个根因:

- `score += random.random() * 0.8`,而角色匹配 +5.0、续接 +12.0,
  **抖动量级排不动名次**,每次都是同一批原子胜出
- 语法里的 `cooldown.same_atom_days` 写了但**代码从未读过它**

修复后平均重叠 12.3%,用到的唯一文案从 166 涨到 910。

### 7. 检查脚本必须能发现被测程序崩溃

批量测试用 shell 循环 grep "gate failed" 判定通过 —— 程序崩溃时既没有
这个字符串、也没生成方案,于是报「20/20 全过」。
`stability_check.py` 现按**退出码 + 方案文件是否真的产出**双重判定。

同类:zsh 不做单词分割,`for seed in $SEEDS` 把整串当成一个种子;
`rm -f dir/*.json` 在空目录会因通配符无匹配而中断整条命令。

> **一个检不出自己失效的检查,比被检代码的 bug 更危险。**

---

## 三、脚本与运行顺序

```bash
cd ~/Studio/Projects/McPOS

# —— 采集新母带(采集器是全量覆写,先备份 manifest!)——
./.venv/bin/python scripts/sg/harvest_whisper.py --only <关键词>
./.venv/bin/python scripts/sg/reclassify_roles.py        # 按语言形态重跑角色
./.venv/bin/python scripts/sg/tag_addressee.py           # 「你」指谁
./.venv/bin/python scripts/sg/screen_blasphemy.py --quarantine
./.venv/bin/python scripts/sg/audit_boundaries.py        # 波形 head_cut/tail_cut
./.venv/bin/python scripts/sg/verify_atom_texts.py --mark  # 逐条核对文本与音频
./.venv/bin/python scripts/sg/audit_master_coverage.py --transcribe

# —— 盘点 ——
./.venv/bin/python scripts/sg/inventory.py

# —— 出片与验收 ——
./.venv/bin/python scripts/sg/build_session.py --episode-id ep01 --seed 1
./.venv/bin/python scripts/sg/qc_session.py --session ep01
./.venv/bin/python scripts/sg/stability_check.py --episodes 20
```

产物落在 `~/Studio/Workspace/outputs/sg/sessions/<id>/`:
`_vo.mp3`(人声)、`_bed.mp3`(音乐床)、`_final_mix.mp3`、`_session.json`(含 plan)。
内容门禁未过时会落盘 `_FAILED_plan.json` 并列出触发条目。

出片历史记在 `~/Studio/Library/sg/catalog/episode_history.json`,
供 cooldown 回避;试排请加 `--no-history` 免得污染。

---

## 四、库存现状(2026-08-06)

| 项 | 数量 |
|---|---:|
| 原子总数 | 2,214 |
| 隔离 no_speech | 432 |
| 隔离 text_mismatch | 64 |
| 隔离 self-deification | 11 |
| 隔离 misread_negation_lost | 1 |
| 词数不足 | 305 |
| **可用原子** | **1,401** |
| 唯一文案 | 1,284 |
| — 自由可用 | 773 |
| — 仅可作续接 | 511 |

**可出 17 期完全不重样,瓶颈槽位 = CLOSE(17 条唯一结尾句)。**

全库文本与音频核对:93.3% 完全一致 · 1.4% 仅转写差异 ·
4.3% 文本不符(已隔离)· 0.9% 听不出内容(已隔离)。

### 下一批补录(G3)优先级

| 内容 | 句数 | 效果 |
|---|---:|---|
| close | 40 | 17 → 57,**解开唯一瓶颈** |
| breath | 40 | 76 → 116,第二瓶颈 |
| 愧疚/羞耻 | 15 | 8 → 23 🔴 |
| 关系/家庭 | 15 | 9 → 24 🔴 |
| 悲伤/失丧 | 15 | 11 → 26 🔴 |
| 失眠本身 | 15 | 12 → 27 🔴 |
| bless | 20 | 53 → 73 |

约 160 句 / 6,500 字符 = 一个月 ElevenLabs 预算。录完预计到 55 期。

---

## 五、待办

- G3 待录文本尚未生成
- 30 条发音可疑原子待人工试听(`config/sg_pronunciation_review.md`)
- 55 条 misc 仍无槽位
- kat 的上传器没有并发锁(SG 单方面加锁拦不住它),两者共用同一配额池
