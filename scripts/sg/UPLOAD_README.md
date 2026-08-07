# Sleep in Grace 上传管线(六组件)

对齐 RBR 参考实现命名,继承 kat playbook 全部教训。详见
`docs/upload_pipeline_playbook.md`。

| # | 组件 | 文件 |
|---|---|---|
| ① | 排播主表(唯一真源,title 仅展示) | `config/sg_schedule_master.json` |
| ② | 每频道独立 OAuth | `scripts/sg/sg_upload.py auth/status` → `config/google/sg/` |
| ③ | 元数据构建器(标题真源 EPISODE_TITLES) | `scripts/sg/upload_meta.py` |
| ④ | 配额账本(2100u/期,预算制) | `scripts/sg/quota.py` → `config/sg_quota_ledger.json` |
| ⑤ | 批量上传器(幂等/门禁/回执双写) | `scripts/sg/sg_batch_upload.py` |
| ⑥ | 独立验证器(flag=验证结论) | `scripts/sg/sg_verify_uploads.py` |

状态一览:`scripts/sg/sg_batch_status.sh`

## 标准工作流

```bash
cd ~/Studio/Projects/McPOS
python3 scripts/sg/upload_meta.py --sync-check        # 真源→主表(自动备份+回滚收据)
python3 scripts/sg/upload_meta.py --build-srt 1       # 成片渲出后生成 SRT(读 manifest 的 vo_atempo)
python3 scripts/sg/sg_batch_upload.py --dry-run --limit 1   # 全门验证,零上传
python3 scripts/sg/sg_batch_upload.py --limit 1       # 真跑:private+publishAt,串行
python3 scripts/sg/sg_verify_uploads.py               # 验证通过才落 upload_complete.flag
git add config/sg_schedule_master.json && git commit  # 主表变更入库
```

## 首次接入(一次性)

1. Google Cloud 建 OAuth 客户端(桌面型),下载 client_secret JSON
2. `python3 scripts/sg/sg_upload.py auth --secrets ~/Downloads/client_secret_*.json`
3. **确认配额池**:若与 kat/RBR 同一 Google Cloud project,配额共享——
   `quota.py` 的预算要与其他频道当日合计 ≤10000u,且上传锁天然共享
   (`~/Studio/Workspace/temp/_locks/upload_link.lock`,非阻塞,拿不到即退出)

## 继承的教训(不可违背)

- **publish_at 未来排播**,绝不即时公开(门禁强制校验)
- **非阻塞单链路锁**:拿不到锁立即退出,绝不排队(2026-07-17 双链路重复上传事故)
- **配额预算制**:上传前 can_afford 一整期,403 不重试(重试也计费)
- **字幕/封面是门禁不是选项**;封面缩略图 ≤2MB 硬上限
- **SEO 改版只动未发布期**,回写留 `sg_meta_rollback_*.json` 回滚收据
- **flag 是验证结论**:sg_verify_uploads 全项通过才落,不是上传副产品

## 每期产物契约

`~/Studio/Workspace/outputs/sg/sessions/<ep>/` 下:
`<ep>_toytune_1h.mp4`(成片)、`<ep>_youtube.srt`、`<ep>_cover.png`、
`<ep>_toytune_1h_manifest.json`(vo_start/vo_atempo/选曲,SRT 与章节的时基来源)、
`<ep>_youtube_upload.json`(回执)、`<ep>_upload_complete.flag`(验证结论)。
