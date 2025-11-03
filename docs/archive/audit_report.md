# 项目一致性审计报告

**生成时间**: 2025-11-02T17:53:13.764579

## 📊 摘要

- **总问题数**: 10
- **错误**: 0
- **警告**: 10
- **信息**: 0
- **可自动修复**: 3
- **分析模块数**: 63

## 📋 按类别统计

- **import**: 3
- **doc**: 4
- **file**: 3

## ❌ 错误列表

✅ 无错误

## ⚠️ 警告列表

### scripts/local_picker/create_mixtape.py
**消息**: 使用了已弃用的导入: production_log（已标记为向后兼容）
**建议**: 已添加注释说明向后兼容

### scripts/local_picker/unified_sync.py
**消息**: 使用了已弃用的导入: production_log（已标记为向后兼容）
**建议**: 已添加注释说明向后兼容

### scripts/local_picker/batch_generate_videos.py
**消息**: 使用了已弃用的导入: production_log（已标记为向后兼容）
**建议**: 已添加注释说明向后兼容

### docs/audit_report.md
**消息**: 文档中引用了已弃用的sync_resources.py
**建议**: 应更新为unified_sync.py

### docs/archive/phase_iv_final_summary.md
**消息**: 文档中引用了production_log.json但未说明已弃用

### docs/archive/phase_iv_audit_report.md
**消息**: 文档中引用了production_log.json但未说明已弃用

### docs/archive/phase_iv_audit_report.md
**消息**: 文档中引用了已弃用的sync_resources.py
**建议**: 应更新为unified_sync.py

### config/production_log.json
**消息**: 发现过期文件: 已弃用，应通过unified_sync.py从文件系统重建

### data/song_usage.csv
**消息**: 发现过期文件: 已弃用，应从schedule_master.json动态查询

### scripts/local_picker/sync_resources.py
**消息**: 发现过期文件: 已弃用，使用unified_sync.py替代


## 🔧 修复建议

1. 优先修复所有错误级别的问题
2. 审查警告级别的问题，根据实际情况决定是否需要修复
3. 使用 `--fix` 参数可以自动修复部分问题
