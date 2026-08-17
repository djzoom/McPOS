# 🔄 Sleep in Grace — 下次启动读这里

> 接力棒,不是历史档案:现在到哪了 · 下一步做什么 · 哪些坑别再踩。
> 状态数字不写死(会过时)—— 跑 `sg_status.py` 现场读。

## 〇、2026-08-17 转向:原子 → 分子(必读)

用户裁定原子(句级拼接)成片的根本问题:**太碎**(单句不知所云)、
**太密**(每期塞太多、语句间距太近)、**太杂**(面面俱到)。处置:

- **平台已撤回全部未播长片**(Ep2–8 删除,Ep1 已公开保留);主表行标
  `hold`,上传器冻结,旧文件绝不重传。撤回没删完的由 daily_ops 步骤 2 自动续
- **新管线 = 分子**:母带按段落停顿(≥6s)整块入库,段内是 Locke 原声
  连续朗读,绝不切进段内。每期一处经文(= 一支主题母带),节制表达,
  块间 16–55s 稀疏呼吸
- **重新上传的前提**:分子管线出的成片稳定通过独立内容门(见下),
  品质确认优于旧片,才重新排播

## 一、开工三条命令

```bash
cd ~/Studio/Projects/McPOS

./.venv/bin/python scripts/sg/sg_status.py            # ① 现在到哪了
./.venv/bin/python scripts/sg/daily_ops.py --dry-run  # ② 今天该做什么
./.venv/bin/python scripts/sg/daily_ops.py            # ③ 做掉它(六步)
```

## 二、分子管线(2026-08-17 新建,联调中)

```
harvest_molecules.py        母带 →(≥6s 段落停顿)→ 分子库;悬空段自动并入下一段
molecule_quality.py         分子唯一权威判据(阈值全部来自实测分布,见模块头)
build_molecule_session.py   选主题(一期一经文)→ 选段(母带原序)→ 稀疏排布
content_gate.py             独立内容门:只转写成片音频判六项;放行时回填
                            plan + 产出 SRT —— 字幕来自成片,音画错位结构性不可能
```

出片即检:`build_molecule_session --minutes 30 --seed N`,门不放行换种子。
分子库:9 支主题母带 → 分子 191 条(`~/Studio/Library/sg/molecules/`)。

**已验证(2026-08-17)**:9/9 主题连排全部放行(4 个主题曾被拦,判据按
实测证据修正:头部双证+排比修辞三重判别、经文保底进选段闭环、库级
实测书卷声明);渲染器兼容确认(40s rings 样片)。判据修正的完整
过程见 molecule_quality.py 各常量旁的注释。

**待办(按序)**:① 与 release_gate 对接(R3 换内容门,R4 已被门覆盖)
② 每期中文字幕(译表按门产出的 en SRT 逐句翻译 → build_zh_srt 十门禁)
③ 定 30/60min 配比与封面,重制最大期数(9 主题 ≈ 9 期不重样)
④ 重新排播上传(sg_batch_upload 认新期次;hold 行是旧片,保持冻结)

## 三、旧原子管线(冻结,只服务短片线)

原子库与 PIPELINE_FREEZE.md v2 保留 —— TOYTUNE 短片线(28.8s 循环)
仍基于原子,50 期已渲齐、日更排播中,不受本次转向影响。
长片一律走分子管线,不再用 build_session.py 出新片。

## 四、补料(分子时代口径)

产能约束仍是素材:9 支主题母带 ≈ 9 个不重样的主题期。扩产按
`ATOM_SUPPLY_PLAN.md` 轨道 B(ElevenLabs Creator),但录制单位改为
**完整主题祷告母带**(15–25 分钟一支、一处经文、段落间留 ≥6s 呼吸),
不再录逐句清单 —— G1/G2 那种句级母带切不出分子。

## 五、别再踩的坑(每条都花过真代价)

| 坑 | 症状 | 现在的防线 |
|---|---|---|
| 先定判据后验分布 | **四**次把频道招牌判成缺陷(最近:分子头部电平斩台标) | 阈值取自对照组实测;上线前拿"必须活下来"的样本试 |
| 悬空当废品 | 句子跨 ≥6s 长停被切半,拒收损失 9% 供给 | 悬空段**合并**入下一段(仍是母带连续原声),不拒收 |
| 静默兜底 | probe 失败返 0.0 被吞,222 条时长漂移 | sg_media 返 None;量不出就不放行 |
| 判据两处定义 | 出片端与验收端各持同名常量 | 原子判据在 atom_quality,分子在 molecule_quality |
| 做了没送到 | 中文字幕本地有平台无(语言硬编码 en) | 三语轨 + backfill 幂等补挂 |
| 测试污染生产 | 连排冲掉 episode_history | stability_check 历史沙箱化 |
| 回执后置 | 评论 403 炸批,video_id 未落盘成孤儿 | publish.py 回执先行、评论挂起 |
| 配额踩踏 | SG 与 KAT 共享 10k/天 | 预算制 + 单链路锁 + daily_ops 逐步问预算 |

## 六、仓库红线

- `origin` 是 **public 仓**。**绝不 `git add -A`**,逐路径暂存。
- 提交身份 `0xGarfield <djwangzhong@gmail.com>`;**提交信息禁止任何 AI 署名**。
- 密钥 `config/config.yaml`、`config/google/`、`*.bak_*` 已入 `.gitignore`。
