# 系统改进路线图

**基于**: 系统体检报告  
**日期**: 2025-11-02  
**优先级**: P0 > P1 > P2

---

## 🎯 P0 任务（1-2周内，必须完成）

### ✅ 1. DEMO逻辑移除（已完成）

- ✅ 移除所有DEMO相关代码
- ✅ 统一输出目录结构
- ✅ 更新所有引用

**状态**: ✅ 已完成

---

### 2. YouTube上传MVP（进行中）

**目标**: 实现完整的YouTube上传链路，完成发布闭环

**功能需求**:
- [ ] OAuth本地回调流程
- [ ] Token持久化与自动刷新
- [ ] 分块上传（支持大文件）
- [ ] 失败重试机制（指数退避）
- [ ] 配额感知与限流
- [ ] 上传队列管理
- [ ] 状态跟踪（写回schedule_master.json）

**交付物**:
- `scripts/local_picker/youtube_upload.py`
- `config/youtube_config.yaml`
- `docs/YOUTUBE_UPLOAD_GUIDE.md`
- 更新状态机：添加`uploading`状态处理

**技术栈**:
- Google API Client Library
- OAuth2.0
- 分块上传（Resumable Upload）

---

### 3. 日志与异常统一（进行中）

**目标**: 统一所有模块的日志和异常处理为JSON结构化输出

**功能需求**:
- [ ] 统一logger工厂（扩展`src/core/logger.py`）
  - JSON格式输出
  - 字段：`level, ts, module, episode_id, action, latency, err_code`
- [ ] 按天滚动
- [ ] 控制台与文件双通道
- [ ] 致命错误触发"回滚 + 标注error"
- [ ] 统一异常处理模式

**交付物**:
- 更新`src/core/logger.py`
- `config/logging.yaml`
- 迁移所有模块使用统一logger

---

### 4. 配置收敛（进行中）

**目标**: 所有脚本使用统一的配置入口

**当前状态**:
- ✅ 已有`src/configuration.py`统一配置框架
- ✅ 支持`config/config.yaml`
- ⚠️ 需要确保所有脚本迁移到统一配置

**任务**:
- [ ] 创建`config/config.example.yaml`模板
- [ ] 创建`scripts/install.sh`一键初始化脚本
- [ ] 迁移所有脚本使用`AppConfig.load()`
- [ ] 文档更新

---

### 5. 核心冒烟用例（进行中）

**目标**: 关键工作流路径的测试覆盖

**测试需求**:
- [ ] 单期生成完整流程（标题→封面→混音→渲染）
- [ ] 批量生成流程
- [ ] 恢复/重跑流程
- [ ] 状态机转移测试（pending→remixing→rendering→completed/error）

**交付物**:
- `tests/test_workflow_golden_paths.py`
- 扩展`tests/test_consistency.py`

---

## 📋 P1 任务（2-6周）

1. **并行化与缓存**
   - 混音/渲染多进程
   - 封面与标题生成结果缓存
   - 幂等键机制
   - 失败自动重试（上限+熔断）

2. **质量门**
   - 封面/描述/标题规范化校验器
   - 生成后打分与拒收机制

3. **可观测性**
   - 指标收集扩展
   - 导出CSV报表

---

## 🔗 相关文档

- [系统体检报告](./system_health_report.md)
- [Phase IV最终审计报告](./phase_iv_audit_report.md)
- [DEMO移除总结](./demo_removal_summary.md)

