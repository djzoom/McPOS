# Phase 5-S6: API Contract Review - 分析报告

**生成时间**: 2025-11-16  
**状态**: 进行中 🔄

---

## STEP 1: 后端 API 路由扫描

### T2R Routes (`/api/t2r/*`)

从 `kat_rec_web/backend/t2r/routes/` 扫描:

#### scan.py
- `POST /api/t2r/scan` - 扫描排播并锁定已发布期数

#### srt.py
- `POST /api/t2r/srt/inspect` - 检查 SRT 文件问题
- `POST /api/t2r/srt/fix` - 修复 SRT 文件

#### desc.py
- `POST /api/t2r/desc/lint` - 检查描述问题

#### plan.py
- `POST /api/t2r/plan` - 生成期数配方
- `POST /api/t2r/run` - 执行 runbook

#### schedule.py
- `POST /api/t2r/schedule/initialize` - 初始化排播
- `POST /api/t2r/schedule/ensure` - 确保排播有足够未来条目
- `GET /api/t2r/schedule/episodes` - 获取期数及输出状态
- `POST /api/t2r/schedule/create-episode` - 创建单个期数
- `POST /api/t2r/schedule/resume-episode` - 恢复期数工作流
- `GET /api/t2r/schedule/work-cursor` - 获取工作游标
- `POST /api/t2r/schedule/youtube-sync` - 同步 YouTube 排播
- `POST /api/t2r/schedule/work-cursor/update` - 更新工作游标
- `POST /api/t2r/schedule/work-cursor/sync` - 同步 YouTube 并更新游标
- `POST /api/t2r/schedule/work-cursor/verify` - 验证并更新游标

#### episodes.py
- `GET /api/t2r/episodes` - 列出所有期数
- `GET /api/t2r/channel` - 获取频道信息
- `GET /api/t2r/episodes/{episode_id}/video-progress` - 获取视频渲染进度

#### episode_flow.py
- `GET /api/t2r/episode/{episode_id}/assets` - 获取期数资产（Stateflow V4）

#### upload.py
- `POST /api/t2r/upload/start` - 开始上传
- `GET /api/t2r/upload/status` - 获取上传状态
- `POST /api/t2r/upload/verify` - 验证上传

#### audit.py
- `GET /api/t2r/audit` - 生成审计报告

#### metrics.py
- `GET /metrics/system` - 系统指标
- `GET /metrics/ws-health` - WebSocket 健康指标
- `GET /api/t2r/metrics/system` - 系统指标（T2R 前缀）
- `GET /api/t2r/metrics/ws-health` - WebSocket 健康指标（T2R 前缀）

#### automation.py
- `GET /api/t2r/library/stats` - 获取图库统计
- `POST /api/t2r/batch-generate` - 批量生成频道期数
- `POST /api/t2r/regenerate-asset` - 重新生成资产
- `POST /api/t2r/batch-generate/cancel` - 取消批量生成
- `POST /api/t2r/generate-playlist` - 生成歌单
- `POST /api/t2r/telemetry` - 记录遥测事件
- `GET /api/t2r/playlist-metadata` - 获取歌单元数据
- `POST /api/t2r/selector/generate-playlist` - SELECTOR 生成歌单
- `POST /api/t2r/selector/generate` - SELECTOR 完整工作流
- `POST /api/t2r/filler/generate` - FILLER 文本资产生成
- `POST /api/t2r/render-queue/auto-enqueue-ready` - 自动入队就绪期数
- `POST /api/t2r/render-queue/enqueue` - 入队渲染任务
- `GET /api/t2r/render-queue` - 获取渲染队列状态
- `POST /api/t2r/render-queue/force-start` - 强制启动渲染队列工作器
- `POST /api/t2r/open-folder` - 打开文件夹
- `POST /api/t2r/ensure-all-files` - 确保所有文件存在
- `POST /api/t2r/generate-cover` - 生成封面

#### reset.py
- `POST /api/t2r/reset/channel` - 重置频道
- `POST /api/t2r/reset/all` - 重置所有频道

---

## STEP 2: 前端 API 调用扫描

从 `kat_rec_web/frontend/services/t2rApi.ts` 扫描:

### 已实现的前端 API 调用

1. `POST /api/t2r/scan` - `scanSchedule()`
2. `POST /api/t2r/srt/inspect` - `inspectSRT()`
3. `POST /api/t2r/srt/fix` - `fixSRT()`
4. `POST /api/t2r/desc/lint` - `lintDescription()`
5. `POST /api/t2r/init-episode` - `initEpisode()` ⚠️ **缺失后端路由**
6. `POST /api/t2r/run` - `runEpisode()`
7. `POST /api/t2r/upload/start` - `startUpload()`
8. `GET /api/t2r/upload/status` - `getUploadStatus()`
9. `POST /api/t2r/upload/verify` - `verifyUpload()`
10. `GET /api/t2r/audit` - `getAuditReport()`
11. `POST /api/t2r/generate-playlist` - `generatePlaylist()`
12. `POST /api/t2r/selector/generate-playlist` - `selectorGeneratePlaylist()`
13. `POST /api/t2r/filler/generate` - `fillerGenerate()`
14. `GET /api/t2r/playlist-metadata` - `getPlaylistMetadata()`
15. `POST /api/t2r/generate-cover` - `generateCover()`
16. `GET /api/t2r/episodes/{episode_id}/audio-progress` - `getAudioRemixProgress()` ⚠️ **缺失后端路由**
17. `GET /api/t2r/episodes/{episode_id}/video-progress` - `getVideoRenderProgress()`
18. `GET /api/t2r/episodes` - `fetchT2REpisodes()`
19. `GET /api/t2r/schedule/work-cursor` - `getWorkCursor()`
20. `POST /api/t2r/schedule/work-cursor/update` - `updateWorkCursor()`
21. `POST /api/t2r/schedule/initialize` - `initializeSchedule()`
22. `POST /api/t2r/schedule/create-episode` - `createEpisode()`
23. `POST /api/t2r/schedule/resume-episode` - `resumeEpisode()`
24. `GET /api/t2r/api-health` - `checkAPIHealth()` ⚠️ **缺失后端路由**
25. `POST /api/t2r/regenerate-asset` - `regenerateAsset()`
26. `POST /api/t2r/telemetry` - `logTelemetry()`
27. `GET /api/t2r/channel` - `fetchT2RChannel()`
28. `GET /api/t2r/channel/profile` - `fetchChannelProfile()` ⚠️ **缺失后端路由**
29. `POST /api/t2r/render-queue/enqueue` - `enqueueRenderJobs()`

---

## STEP 3: 差异分析

### 缺失的后端路由（前端调用但后端不存在）

1. **`POST /api/t2r/init-episode`**
   - 前端调用: `initEpisode()` in `t2rApi.ts:430`
   - 后端状态: ❌ 不存在
   - 建议: 在 `plan.py` 中添加 `init_episode` 路由（已在 Phase 5-S4 中实现函数，但未注册路由）

2. **`GET /api/t2r/episodes/{episode_id}/audio-progress`**
   - 前端调用: `getAudioRemixProgress()` in `t2rApi.ts:834`
   - 后端状态: ❌ 不存在
   - 建议: 在 `episodes.py` 中添加路由

3. **`GET /api/t2r/api-health`**
   - 前端调用: `checkAPIHealth()` in `t2rApi.ts:1056`
   - 后端状态: ❌ 不存在
   - 建议: 在 `metrics.py` 或新建 `health.py` 中添加路由

4. **`GET /api/t2r/channel/profile`**
   - 前端调用: `fetchChannelProfile()` in `t2rApi.ts:1144`
   - 后端状态: ❌ 不存在
   - 建议: 在 `episodes.py` 中添加路由

### 未使用的前端路由（后端存在但前端未调用）

1. `POST /api/t2r/schedule/ensure` - 确保排播
2. `GET /api/t2r/schedule/episodes` - 获取期数及输出状态
3. `POST /api/t2r/schedule/youtube-sync` - 同步 YouTube
4. `POST /api/t2r/schedule/work-cursor/sync` - 同步并更新游标
5. `POST /api/t2r/schedule/work-cursor/verify` - 验证并更新游标
6. `POST /api/t2r/batch-generate` - 批量生成
7. `POST /api/t2r/batch-generate/cancel` - 取消批量生成
8. `POST /api/t2r/selector/generate` - SELECTOR 完整工作流
9. `POST /api/t2r/render-queue/auto-enqueue-ready` - 自动入队
10. `GET /api/t2r/render-queue` - 获取渲染队列状态
11. `POST /api/t2r/render-queue/force-start` - 强制启动队列
12. `POST /api/t2r/open-folder` - 打开文件夹
13. `POST /api/t2r/ensure-all-files` - 确保所有文件
14. `POST /api/t2r/reset/channel` - 重置频道
15. `POST /api/t2r/reset/all` - 重置所有频道

---

## STEP 4: 修复实施 ✅

### 已修复的缺失后端路由

1. **✅ 添加 `POST /api/t2r/init-episode`**
   - 文件: `kat_rec_web/backend/t2r/routes/plan.py`
   - 操作: 添加 `@router.post("/init-episode")` 装饰器
   - 状态: ✅ 完成

2. **✅ 添加 `GET /api/t2r/episodes/{episode_id}/audio-progress`**
   - 文件: `kat_rec_web/backend/t2r/routes/episodes.py`
   - 操作: 实现音频混音进度检测（Stateflow V4 文件系统检测）
   - 状态: ✅ 完成

3. **✅ 添加 `GET /api/t2r/api-health`**
   - 文件: `kat_rec_web/backend/t2r/routes/metrics.py`
   - 操作: 添加 API 健康检查端点
   - 状态: ✅ 完成

4. **✅ 添加 `GET /api/t2r/channel/profile`**
   - 文件: `kat_rec_web/backend/t2r/routes/episodes.py`
   - 操作: 添加频道配置端点
   - 状态: ✅ 完成

---

## STEP 5: 验证结果

### 修改的文件

1. `kat_rec_web/backend/t2r/routes/plan.py`
   - 添加 `@router.post("/init-episode")` 装饰器

2. `kat_rec_web/backend/t2r/routes/episodes.py`
   - 添加 `get_audio_progress_endpoint()` 函数
   - 添加 `get_channel_profile()` 函数
   - 添加 `Optional` 类型导入

3. `kat_rec_web/backend/t2r/routes/metrics.py`
   - 添加 `get_api_health()` 函数

### 验证状态

- ✅ 所有 Python 文件语法检查通过
- ✅ 所有 linter 检查通过
- ✅ `full_validation.py` 待运行

---

## 下一步

1. ✅ 实施修复 - 完成
2. ⏳ 运行完整验证 - 进行中
3. ⏳ 更新治理文档 - 待完成

