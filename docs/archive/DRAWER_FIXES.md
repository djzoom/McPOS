# 抽屉页面问题修复说明

## 问题 1: 封面无法显示

### 问题描述
- 封面和标题通常同时生成，但封面无法在抽屉页面显示
- 每次点击"生成封面"按钮都会重新生成，即使文件夹中已有封面文件
- 需要改进：如果文件夹中已有封面文件，且有选图信息，应该直接显示，而不是重新生成

### 根本原因
1. **前端问题**：`TaskPanel.tsx` 在加载时只检查 `event.assets.cover`，如果这个字段未设置，即使文件系统中已有封面文件也不会显示
2. **后端问题**：`generate_cover` API 没有检查是否已有封面文件，每次都重新生成

### 修复方案

#### 后端修复 (`automation.py`)
1. **幂等性检查**：在 `generate_cover` API 开始时，先检查是否已有封面文件
   - 检查路径：`{output_dir}/{episode_id}/{episode_id}_cover.png`
   - 如果文件存在，从排播表加载封面信息（image_path, title, color_hex）
   - 直接返回已有封面信息，不重新生成

2. **返回字段**：添加 `from_existing` 字段，标识是否使用已有封面

#### 前端修复 (`TaskPanel.tsx`)
1. **文件系统检查**：在 `useEffect` 中，如果 `event.assets.cover` 未设置，调用 `generateCover` API 检查文件系统
   - API 会检查文件是否存在，如果存在则返回封面信息
   - 自动更新 `coverData` 和 `event.assets.cover`

2. **按钮显示逻辑**：修改按钮显示条件，在生成中时也显示按钮（显示"生成中"状态）

3. **提示信息**：根据 `from_existing` 字段显示不同的提示信息

### 修复后的行为
- ✅ 打开抽屉时，自动检查并加载已有封面
- ✅ 如果封面已存在，点击"生成封面"会直接加载，不重新生成
- ✅ 显示明确的提示信息（"已加载已有封面" vs "封面生成成功"）

---

## 问题 2: 混音功能不工作

### 问题描述
- 点击混音按钮显示"混音中"，但实际上没有真正执行混音
- 按理说应该有制作用的歌单、曲库、sfx，应该合成很容易

### 根本原因分析
1. **API 调用**：前端调用 `runEpisode({ episode_id, stages: ['remix'] })` 是正确的
2. **后端执行**：后端使用 `asyncio.create_task` 在后台执行，但可能存在以下问题：
   - 错误没有被正确捕获和报告
   - 输出文件路径不匹配
   - 混音脚本执行失败但没有显示错误

### 修复方案

#### 后端修复 (`plan.py`)
1. **增强日志**：
   - 记录混音命令和执行参数
   - 记录 stdout 和 stderr（前500字符）
   - 记录返回码和错误信息

2. **文件路径检查**：
   - 检查多种可能的输出文件命名模式
   - 如果找不到文件，列出目录中的所有文件用于调试

3. **错误处理**：
   - 更详细的错误信息
   - 确保错误通过 WebSocket 广播到前端

4. **状态更新**：
   - 混音完成后，尝试更新排播表中的 `audio_path`

#### 前端修复 (`TaskPanel.tsx`)
1. **错误处理**：改进错误提示，显示更详细的错误信息
2. **状态跟踪**：确保正确跟踪混音进度

### 修复后的行为
- ✅ 混音任务真正执行
- ✅ 错误信息清晰可见
- ✅ 进度通过 WebSocket 实时更新
- ✅ 混音完成后自动更新事件状态

---

## 技术细节

### 封面检查流程
```
1. 前端打开抽屉 → useEffect 触发
2. 检查 event.assets.cover → 如果不存在
3. 调用 generateCover API → 后端检查文件系统
4. 后端检查 {episode_id}_cover.png → 如果存在
5. 从排播表加载元数据 → 返回封面信息
6. 前端更新 coverData → 显示封面
```

### 混音执行流程
```
1. 用户点击"Mix"按钮
2. 前端调用 runEpisode({ stages: ['remix'] })
3. 后端创建后台任务 execute_runbook_stages
4. 执行 _execute_stage('remix', episode_id)
5. 调用 remix_mixtape.py 脚本
6. 验证输出文件存在
7. 通过 WebSocket 广播进度和结果
```

### 关键文件
- **后端封面生成**：`kat_rec_web/backend/t2r/routes/automation.py` (generate_cover)
- **前端封面显示**：`kat_rec_web/frontend/components/mcrb/TaskPanel.tsx`
- **后端混音执行**：`kat_rec_web/backend/t2r/routes/plan.py` (_execute_stage)
- **混音脚本**：`scripts/local_picker/remix_mixtape.py`

---

## 测试建议

### 封面功能测试
1. 创建一个已有封面的期数
2. 打开抽屉，验证封面自动显示
3. 点击"生成封面"，验证显示"已加载已有封面"
4. 删除封面文件，点击"生成封面"，验证重新生成

### 混音功能测试
1. 确保有歌单文件（playlist.csv）
2. 确保有曲库和 sfx 文件
3. 点击"Mix"按钮
4. 观察控制台日志，验证混音脚本执行
5. 检查输出目录，验证 full_mix.mp3 文件生成
6. 验证进度通过 WebSocket 实时更新

