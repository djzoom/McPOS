# T2R (Trip to Reality) - Action Plan

**版本**: v1.0  
**创建日期**: 2025-11-10  
**状态**: 🚧 **进行中**

---

## 📋 项目概览

**Mission Control: Reality Board (MCRB)** 是将 Kat Records 内容生命周期从 CLI 迁移到 Web 控制中心的全面系统。

### 核心目标

- ✅ 实时同步排播表 (`config/schedule_master.json`)
- ✅ 管理真实文件状态 (`/library`, `/output`, `/config`)
- ✅ 自动扫描、修复、锁定已发布内容
- ✅ 识别重复素材、冲突、脏数据
- ✅ SRT 体检与修复、描述 Lint、SEO 规范化
- ✅ 动态生成节目计划 Recipe 与一键执行 Runbook
- ✅ 全链路上传与校验可视化
- ✅ 并行任务管理（100 频道规模）

---

## ✅ 已完成部分

### 后端架构

1. **目录结构** ✅
   ```
   backend/t2r/
   ├── __init__.py
   ├── router.py              # 主路由聚合
   ├── routes/
   │   ├── scan.py            # 扫描与锁定
   │   ├── srt.py             # SRT 体检与修复
   │   ├── desc.py            # 描述规范化
   │   ├── plan.py            # 计划与执行
   │   ├── upload.py          # 上传与核验
   │   └── audit.py           # 审计与导出
   └── services/
       └── schedule_service.py # 排播服务
   ```

2. **API 端点** ✅
   - `POST /api/t2r/scan` - 扫描与锁定
   - `POST /api/t2r/srt/inspect` - SRT 检查
   - `POST /api/t2r/srt/fix` - SRT 修复
   - `POST /api/t2r/desc/lint` - 描述检查
   - `POST /api/episodes/plan` - 生成 Recipe
   - `POST /api/episodes/run` - 执行 Runbook
   - `POST /api/upload/start` - 开始上传
   - `GET /api/upload/status` - 上传状态
   - `POST /api/upload/verify` - 验证上传
   - `GET /api/t2r/audit` - 审计报告

### 前端架构

1. **Zustand Stores** ✅
   - `t2rScheduleStore` - 排播表状态
   - `t2rAssetsStore` - 资产使用索引
   - `t2rSrtStore` - SRT 检测与修复
   - `t2rDescStore` - 描述规范化
   - `runbookStore` - 执行阶段与日志

2. **页面与组件** ✅
   - `/t2r` - Reality Board 主页面
   - `ChannelOverview` - 频道总览
   - `ScheduleDoctor` - 排播医生
   - `AssetHealth` - 资产健康
   - `SRTDoctor` - SRT 医生
   - `DescriptionLinter` - 描述检查
   - `PlanAndRun` - 计划与执行
   - `PostUploadVerify` - 上传验证
   - `AuditTrail` - 审计报告

3. **API 服务** ✅
   - `t2rApi.ts` - T2R API 客户端封装

4. **WebSocket Hook** ✅
   - `useT2RWebSocket.ts` - T2R 事件处理

---

## 🚧 待完成部分

### 后端增强

1. **SRT 解析与修复** - 需要实现实际的 SRT 文件解析
2. **描述模板注入** - 实现 CC0 模板和 SEO 元数据注入
3. **Recipe 生成逻辑** - 实现真实的避重规则和模板生成
4. **Runbook 执行** - 集成实际的混音/渲染/上传流程
5. **上传验证** - 实现 YouTube API 集成验证

### 前端增强

1. **组件交互** - 连接 API 调用和状态更新
2. **文件上传** - SRT 文件上传功能
3. **实时更新** - WebSocket 事件处理完整实现
4. **错误处理** - 完善的错误提示和重试机制
5. **数据可视化** - 图表展示资产使用情况

### WebSocket 事件扩展

需要在后端广播 T2R 事件时使用新的函数：
- `broadcast_t2r_event('scan_progress', data)`
- `broadcast_t2r_event('fix_applied', data)`
- `broadcast_t2r_event('runbook_stage_update', data)`
- `broadcast_t2r_event('upload_progress', data)`
- `broadcast_t2r_event('verify_result', data)`

---

## 📁 文件清单

### 后端文件

✅ `backend/t2r/__init__.py`
✅ `backend/t2r/router.py`
✅ `backend/t2r/routes/scan.py`
✅ `backend/t2r/routes/srt.py`
✅ `backend/t2r/routes/desc.py`
✅ `backend/t2r/routes/plan.py`
✅ `backend/t2r/routes/upload.py`
✅ `backend/t2r/routes/audit.py`
✅ `backend/t2r/services/schedule_service.py`

### 前端文件

✅ `frontend/stores/t2rScheduleStore.ts`
✅ `frontend/stores/t2rAssetsStore.ts`
✅ `frontend/stores/t2rSrtStore.ts`
✅ `frontend/stores/t2rDescStore.ts`
✅ `frontend/stores/runbookStore.ts`
✅ `frontend/services/t2rApi.ts`
✅ `frontend/hooks/useT2RWebSocket.ts`
✅ `frontend/app/(t2r)/t2r/page.tsx`
✅ `frontend/components/t2r/ChannelOverview.tsx`
✅ `frontend/components/t2r/ScheduleDoctor.tsx`
✅ `frontend/components/t2r/AssetHealth.tsx`
✅ `frontend/components/t2r/SRTDoctor.tsx`
✅ `frontend/components/t2r/DescriptionLinter.tsx`
✅ `frontend/components/t2r/PlanAndRun.tsx`
✅ `frontend/components/t2r/PostUploadVerify.tsx`
✅ `frontend/components/t2r/AuditTrail.tsx`

---

## 🧪 验证步骤

### 1. 后端 API 测试

```bash
# 扫描与锁定
curl -X POST http://localhost:8000/api/t2r/scan

# SRT 检查
curl -X POST http://localhost:8000/api/t2r/srt/inspect \
  -H "Content-Type: application/json" \
  -d '{"episode_id": "20251102"}'

# 描述检查
curl -X POST http://localhost:8000/api/t2r/desc/lint \
  -H "Content-Type: application/json" \
  -d '{"episode_id": "20251102", "description": "Test description with Vibe Coding"}'
```

### 2. 前端页面测试

1. 启动后端和前端
2. 访问 `http://localhost:3000/t2r`
3. 测试各个标签页功能

---

## 📝 下一步工作

### 优先级 1: 核心功能完善

1. 实现真实的 SRT 解析（使用 `pysrt` 或类似库）
2. 完善描述模板注入逻辑
3. 实现 Recipe 生成的避重规则
4. 集成真实的混音/渲染脚本

### 优先级 2: 前端交互

1. 连接所有组件到 API
2. 实现文件上传功能
3. 完善错误处理和加载状态
4. 添加数据可视化

### 优先级 3: 测试与文档

1. 创建验证脚本
2. 编写完整测试用例
3. 更新 API 文档
4. 创建用户指南

---

**最后更新**: 2025-11-10  
**当前进度**: 🚧 框架已搭建，待完善实现细节

