# YouTube API 配额限制解决方案

## 当前情况

根据实测：
- **一个 OAuth token 一天只能上传 10 期**
- 当前配置：`quota_limit_daily: 9000` units
- 每次上传消耗：`1600` units
- 理论上限：9000 / 1600 ≈ 5.6 个视频

**实测与理论不符的原因**：
1. 实际配额可能更高（如 20,000 units，可上传 12-13 个）
2. 实际消耗可能低于 1600 units（如 1000-1200 units）
3. YouTube 账户本身可能有每日上传限制（如 10 个/天）

## 解决方案

### 方案 1：根据实测调整配额配置（推荐）

如果实测能上传 10 期，建议调整配置：

```yaml
# config/config.yaml
youtube:
  quota_limit_daily: 16000  # 调整为实测值（10 期 × 1600）
  # 或者如果实际消耗更少：
  # quota_limit_daily: 10000  # 10 期 × 1000
```

**优点**：
- 简单直接
- 符合实测数据
- 无需额外开发

**缺点**：
- 仍然受限于单个 OAuth token
- 无法突破 10 期/天的限制

### 方案 2：多 OAuth Token 轮换（突破限制）

如果有多個 Google 账户，可以实现 Token 轮换：

1. **配置多个 Token**：
   ```yaml
   youtube:
     tokens:
       - token_file: config/google/youtube_token_1.json
         quota_limit_daily: 16000
       - token_file: config/google/youtube_token_2.json
         quota_limit_daily: 16000
   ```

2. **实现轮换逻辑**：
   - 当 Token 1 配额用尽时，自动切换到 Token 2
   - 每个 Token 独立跟踪配额
   - 自动选择有可用配额的 Token

**优点**：
- 可以突破 10 期/天的限制
- 如果有 2 个账户，可以上传 20 期/天
- 自动故障转移（一个账户出问题时使用另一个）

**缺点**：
- 需要多个 Google 账户
- 需要实现 Token 轮换逻辑
- 需要管理多个 Token 文件

### 方案 3：申请配额提升（长期方案）

在 Google Cloud Console 申请更高的配额：

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 选择项目 → APIs & Services → Quotas
3. 找到 YouTube Data API v3
4. 申请提升每日配额（如从 10,000 提升到 50,000 或更高）

**优点**：
- 从根本上解决问题
- 无需代码改动
- 适合长期使用

**缺点**：
- 需要 Google 审核（可能需要几天）
- 可能需要付费（取决于配额提升幅度）
- 不保证一定批准

### 方案 4：优化配额使用（减少浪费）

检查是否有不必要的 API 调用：

1. **减少验证调用**：
   - 当前 `verify_delay_seconds: 180` 可能触发多次验证
   - 优化验证逻辑，减少 API 调用

2. **批量操作**：
   - 如果可能，使用批量 API（减少配额消耗）

3. **缓存结果**：
   - 缓存视频元数据，避免重复查询

## 当前实现状态

### ✅ 已实现

1. **配额管理器** (`oauth_quota_manager.py`)：
   - 跟踪每日配额使用
   - 配额用尽后自动暂停
   - 每日 UTC 00:00 自动重置

2. **配额错误检测** (`upload_queue.py`)：
   - 自动检测配额错误（403, quotaExceeded）
   - 配额错误时暂停上传

3. **配额状态查询**：
   - 可以通过 API 查询当前配额状态

### ⏳ 待实现

1. **多 Token 轮换**：
   - 需要实现 Token 选择逻辑
   - 需要独立跟踪每个 Token 的配额

2. **配额预警**：
   - 配额使用超过 80% 时发送警告
   - 前端显示配额使用情况

3. **配额配置优化**：
   - 根据实测数据调整默认配额
   - 支持动态调整配额限制

## 建议

### 短期（立即）

1. **调整配额配置**：
   ```yaml
   youtube:
     quota_limit_daily: 16000  # 根据实测 10 期调整
   ```

2. **监控配额使用**：
   - 查看 `data/youtube_quota_state.json` 了解实际使用情况
   - 根据实际消耗调整配置

### 中期（1-2 周）

1. **实现多 Token 轮换**（如果有多个账户）
2. **添加配额预警**（前端显示配额状态）
3. **优化配额使用**（减少不必要的 API 调用）

### 长期（1-3 个月）

1. **申请配额提升**（Google Cloud Console）
2. **建立配额监控仪表板**（实时查看配额使用）
3. **实现智能调度**（根据配额情况自动调整上传计划）

## 相关文件

- `kat_rec_web/backend/t2r/services/oauth_quota_manager.py` - 配额管理器
- `kat_rec_web/backend/t2r/services/upload_queue.py` - 上传队列（包含配额错误处理）
- `config/config.yaml` - 配额配置
- `data/youtube_quota_state.json` - 配额状态文件（SSOT）

## 配额计算公式

```
每日可上传视频数 = quota_limit_daily / upload_quota_cost

例如：
- quota_limit_daily = 16000
- upload_quota_cost = 1600
- 每日可上传 = 16000 / 1600 = 10 个视频
```

## 注意事项

1. **配额重置时间**：每日 UTC 00:00（不是本地时间）
2. **配额跟踪**：基于文件系统（`data/youtube_quota_state.json`）
3. **配额错误**：会自动暂停 24 小时，直到配额重置
4. **多账户**：如果使用多个账户，需要独立跟踪每个账户的配额

