# 🔄 Sleep in Grace — 下次启动读这里

> 这份文件是**接力棒**,不是历史档案。它只回答三件事:
> 现在到哪了 · 下一步做什么 · 哪些坑别再踩。
> 状态数字不写死在这里(会过时)—— 跑 `sg_status.py` 现场读。

## 一、开工三条命令

```bash
cd ~/Studio/Projects/McPOS

./.venv/bin/python scripts/sg/sg_status.py            # ① 现在到哪了(30 秒)
./.venv/bin/python scripts/sg/daily_ops.py --dry-run  # ② 今天该做什么
./.venv/bin/python scripts/sg/daily_ops.py            # ③ 做掉它
```

`sg_status.py` 会现场汇总素材库、成品、发布、配额、以及**下一步建议**。
不必读旧对话,那一屏就是全部上下文。

## 二、频道现状（2026-08-16 开播）

- **已开播**:长片 Ep1 与短片 ep001 于 08-15 公开
- **长片**:8 期全部上线,每周六 19:00 ET,排至 **2026-10-03**
- **短片**:50 期已渲齐,每天 21:00 ET,排至 **2026-10-03**
- **两条线同日耗尽库存** → 九月中前必须补料(见第四节)

## 三、管线状态（冻结 v2）

`PIPELINE_FREEZE.md` 是权威清单。核心链路 17 个脚本 + 发布线,判据全部有实测依据。

**每次改动核心链路后,必跑三项验收**:

```bash
./.venv/bin/python scripts/sg/inventory.py                    # 库存与瓶颈
./.venv/bin/python scripts/sg/stability_check.py --episodes 8 # 须判定「稳定」
./.venv/bin/python scripts/sg/release_gate.py --all           # 八期须全绿(不加 --fast)
```

## 四、下一件大事：补料（唯一的硬约束）

产能受**素材**限制,不受算法限制。自由可用唯一文案约 770 条,只够 8 期不重样。

按 `ATOM_SUPPLY_PLAN.md` 轨道 B:订 ElevenLabs Creator($22/月,首月 $11),
三批录完约 660 句 → 唯一文案 ≥1400,12 期窗口不重样。**九月中前动手**即可接上档期。

新母带入库一律走 `harvest_whisper.py --span-mode`(按静音切段逐段转写)。
词级路径在长静默母带上必然幻觉,`--vad` 会毁掉粒度,`-nth` 无效 —— 三条路都试过。

## 五、别再踩的坑（每条都花过真代价）

| 坑 | 症状 | 现在的防线 |
|---|---|---|
| 静默兜底 | `probe_duration` 失败返 0.0 被 `or` 吞掉,222 条时长漂移 | `sg_media` 返 None;要兜底就写出来 |
| 判据两处定义 | 出片端与验收端各持一份同名常量 | 间隔常量只在 `atom_quality` |
| 只剪不除名 | 剪掉的坏句下一期又被选回来 | `repair_session` 默认同步隔离 |
| 先定判据后验分布 | 三次把频道招牌判成缺陷 | 阈值取自对照组实测;上线前拿"必须活下来"的样本试 |
| 测试污染生产 | 连排冲掉 `episode_history` | `stability_check` 历史沙箱化 |
| 做了没送到 | 中文字幕本地有、平台无(语言硬编码 en) | 三语轨 + `backfill_captions` 幂等补挂 |
| 回执后置 | 评论 403 炸掉整批,video_id 未落盘成孤儿 | `publish.py` 回执先行、评论挂起 |
| 配额踩踏 | SG 与 KAT 共享 10k/天,KAT 上传器无锁 | 预算制 + 单链路锁;同日上传前人工确认 |

## 六、仓库红线

- `origin` 是 **public 仓**。**绝不 `git add -A`**,逐路径暂存。
- 提交身份 `0xGarfield <djwangzhong@gmail.com>`;**提交信息禁止任何 AI 署名**
  (无 `Co-Authored-By`,无 `Generated with`)——2026-07-20 用户令,全库史已清洗。
- 密钥 `config/config.yaml`、`config/google/` 已入 `.gitignore`(2026-08-12 补)。
