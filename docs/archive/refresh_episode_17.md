# 刷新 17 日排播

## 当前状态

2025-11-17 的排播已经存在于系统中：
- Episode ID: `20251117`
- 状态: `pending`
- 已完成: remix（混音完成）
- 已有文件: 封面、字幕、音频

## 解决方案

### 方案 1: 在前端刷新数据

1. 打开排播总览页面
2. 刷新页面（F5 或 Cmd+R）
3. 检查 17 日的单元格是否显示

### 方案 2: 重新启动生成流程

如果前端仍然不显示，可以通过以下方式重新启动：

```bash
# 使用 curl 调用 API 重新创建（会更新现有记录并启动生成）
curl -X POST http://localhost:8000/api/t2r/schedule/create-episode \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "kat_lofi",
    "date": "2025-11-17",
    "start_generation": true
  }'
```

### 方案 3: 检查前端数据同步

前端可能没有正确加载数据。检查：
1. 浏览器控制台是否有错误
2. WebSocket 连接是否正常
3. 数据是否正确从后端加载

## 文件位置

- Schedule: `channels/kat_lofi/schedule_master.json`
- Output: `channels/kat_lofi/output/20251117/`
- Manifest: `channels/kat_lofi/output/20251117/20251117_manifest.json`

