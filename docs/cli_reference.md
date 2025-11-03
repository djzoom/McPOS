# CLI命令参考

**版本**: v1.0  
**最后更新**: 2025-11-XX

## 📋 概述

本文档列出了KAT Records Studio的所有命令行接口（CLI）命令及其参数说明。

---

## 🚀 主入口

### `scripts/kat_cli.py`

统一的命令行入口，支持所有功能模块。

**基本用法**:
```bash
python scripts/kat_cli.py <命令> [参数...]
```

---

## 📝 命令列表

### 1. `generate` - 生成视频内容

生成单期视频内容（封面、混音、视频）。

**用法**:
```bash
python scripts/kat_cli.py generate [选项]
```

**选项**:
- `--id`, `--episode-id <ID>` - 期数ID（YYYYMMDD格式）
- `--seed <N>` - 随机种子（用于重现结果）
- `--demo` - 测试模式
- `--no-remix` - 跳过混音步骤
- `--no-video` - 跳过视频生成步骤

**示例**:
```bash
# 生成指定期数
python scripts/kat_cli.py generate --id 20251102

# 测试模式
python scripts/kat_cli.py generate --id 20251102 --demo

# 仅生成封面和歌单，跳过混音和视频
python scripts/kat_cli.py generate --id 20251102 --no-remix --no-video
```

**对应脚本**: `scripts/local_picker/create_mixtape.py`

---

### 2. `schedule` - 排播表管理

排播表的创建、查看、生成和监视。

#### 2.1 `schedule create` - 创建排播表

**用法**:
```bash
python scripts/kat_cli.py schedule create --episodes <N> [选项]
```

**选项**:
- `--episodes <N>` - 期数（必需）
- `--start-date <DATE>` - 起始日期（YYYY-MM-DD格式）
- `--interval <N>` - 排播间隔（天，默认：2）
- `--yes` - 跳过确认提示
- `--force` - 强制覆盖现有排播表

**示例**:
```bash
# 创建15期排播表（交互式确认）
python scripts/kat_cli.py schedule create --episodes 15

# 直接创建，跳过确认
python scripts/kat_cli.py schedule create --episodes 15 --yes

# 指定起始日期和间隔
python scripts/kat_cli.py schedule create --episodes 20 --start-date 2025-11-10 --interval 3
```

**对应脚本**: `scripts/local_picker/create_schedule_with_confirmation.py`

#### 2.2 `schedule show` - 显示排播表

**用法**:
```bash
python scripts/kat_cli.py schedule show [选项]
```

**选项**:
- `--pending` - 只显示pending状态的期数
- `--id <ID>` - 显示指定期数的详细信息

**示例**:
```bash
# 显示完整排播表
python scripts/kat_cli.py schedule show

# 只显示待制作的期数
python scripts/kat_cli.py schedule show --pending

# 显示特定期数详情
python scripts/kat_cli.py schedule show --id 20251102
```

**对应脚本**: `scripts/local_picker/show_schedule.py`

#### 2.3 `schedule generate` - 生成完整排播表

生成排播表的标题和曲目。

**用法**:
```bash
python scripts/kat_cli.py schedule generate [选项]
```

**选项**:
- `--format <FORMAT>` - 输出格式（markdown/csv/both，默认：markdown）
- `--output <PATH>` - 输出文件路径
- `--update-schedule` - 更新排播表（自动设置）

**示例**:
```bash
# 生成Markdown格式排播表
python scripts/kat_cli.py schedule generate

# 生成CSV格式
python scripts/kat_cli.py schedule generate --format csv
```

**对应脚本**: `scripts/local_picker/generate_full_schedule.py`

#### 2.4 `schedule watch` - 监视排播表状态

**用法**:
```bash
python scripts/kat_cli.py schedule watch [选项]
```

**选项**:
- `--watch` - 持续监视模式
- `--interval <N>` - 监视间隔（秒，默认：10）

**示例**:
```bash
# 单次扫描状态
python scripts/kat_cli.py schedule watch

# 持续监视（每10秒刷新）
python scripts/kat_cli.py schedule watch --watch

# 自定义刷新间隔（每5秒）
python scripts/kat_cli.py schedule watch --watch --interval 5
```

**对应脚本**: `scripts/local_picker/watch_schedule_status.py`

---

### 3. `batch` - 批量生成

批量生成多期视频内容。

**用法**:
```bash
python scripts/kat_cli.py batch --count <N> [选项]
```

**选项**:
- `--count <N>`, `-n <N>` - 生成期数（必需）
- `--demo` - 测试模式

**示例**:
```bash
# 批量生成10期
python scripts/kat_cli.py batch --count 10

# 测试模式批量生成
python scripts/kat_cli.py batch --count 5 --demo
```

**对应脚本**: `scripts/local_picker/batch_generate_videos.py`

---

### 4. `reset` - 重置操作

重置排播表和输出文件。

**用法**:
```bash
python scripts/kat_cli.py reset <模式> [选项]
```

**互斥模式**（必须选择一个）:
- `--schedule-only` - 只清除排播表
- `--include-output` - 清除排播表 + 期数文件夹
- `--full-reset` - 完全清除（排播表 + 所有output）

**选项**:
- `--yes` - 跳过确认提示

**示例**:
```bash
# 只重置排播表（交互式确认）
python scripts/kat_cli.py reset --schedule-only

# 重置排播表和输出文件夹
python scripts/kat_cli.py reset --include-output --yes

# 完全重置
python scripts/kat_cli.py reset --full-reset --yes
```

**对应脚本**: `scripts/reset_all.py`（部分功能）

---

### 5. `help` - 帮助系统

显示帮助信息。

**用法**:
```bash
python scripts/kat_cli.py help [选项]
```

**选项**:
- `--quick` - 快速参考
- `--category <CATEGORY>` - 按类别查看
- `--command <CMD>` - 查看命令详情
- `--docs` - 文档索引

**示例**:
```bash
# 显示主帮助
python scripts/kat_cli.py help

# 快速参考
python scripts/kat_cli.py help --quick

# 查看文档索引
python scripts/kat_cli.py help --docs
```

**对应脚本**: `scripts/show_help.py`

---

### 6. `api` - API管理

API相关的配置和检查。

#### 6.1 `api check` - 检查API状态

**用法**:
```bash
python scripts/kat_cli.py api check [选项]
```

**选项**:
- `--test` - 执行实际API调用测试

**示例**:
```bash
# 检查API配置状态
python scripts/kat_cli.py api check

# 执行实际API调用测试
python scripts/kat_cli.py api check --test
```

**对应脚本**: `scripts/check_api_status.py`

#### 6.2 `api setup` - 配置API密钥

**用法**:
```bash
python scripts/kat_cli.py api setup
```

**示例**:
```bash
# 交互式配置API密钥
python scripts/kat_cli.py api setup
```

**对应脚本**: `scripts/local_picker/configure_api.py`

---

## 🔧 高级工具

### 状态管理工具

#### `validate_integrity` - 完整性验证

```bash
# 快速检查
python scripts/local_picker/validate_integrity.py

# 深度检查（包括文件系统验证）
python scripts/local_picker/validate_integrity.py --deep

# JSON格式输出
python scripts/local_picker/validate_integrity.py --json
```

#### `recover_episode` - 期数恢复

```bash
# 恢复单个期数
python scripts/local_picker/recover_episode.py --episode-id 20251102

# 恢复并自动重新运行
python scripts/local_picker/recover_episode.py --episode-id 20251102 --rerun

# 恢复所有失败的期数
python scripts/local_picker/recover_episode.py --all
```

#### `unified_sync` - 统一状态同步

```bash
# 从文件系统同步状态
python scripts/local_picker/unified_sync.py --sync

# 只同步排播表
python scripts/local_picker/unified_sync.py --sync --schedule-only

# 预览模式（不实际修改）
python scripts/local_picker/unified_sync.py --sync --dry-run
```

#### `cli_monitor` - CLI监控

```bash
# 单次显示
python scripts/local_picker/cli_monitor.py

# 持续监控（每5秒刷新）
python scripts/local_picker/cli_monitor.py --watch

# 自定义刷新间隔
python scripts/local_picker/cli_monitor.py --watch --interval 3
```

---

## 📊 状态定义

期数状态采用明确的状态机模型：

- `pending` - 待制作（初始状态）
- `remixing` - 混音中
- `rendering` - 渲染中（视频生成中）
- `uploading` - 上传中
- `completed` - 已完成
- `error` - 错误（需要人工介入）

**注意**: 旧代码可能使用中文状态值（如"待制作"），系统会自动兼容处理。

---

## 🔗 相关文档

- [系统架构文档](./ARCHITECTURE.md) - 统一状态管理架构说明
- [开发日志](./DEVELOPMENT.md) - 开发进展和成就
- [路线图](./ROADMAP.md) - 未来计划和改进方向
- [COMMAND_LINE_WORKFLOW.md](./COMMAND_LINE_WORKFLOW.md)
- [TERMINAL_GUIDE.md](./TERMINAL_GUIDE.md)

---

## ⚠️ 注意事项

1. **状态管理**: 所有状态操作应通过统一的状态管理器，避免直接修改JSON文件
2. **并发安全**: 多个进程同时操作同一期数时会自动加锁，30秒超时
3. **原子性**: 所有文件写入都是原子性的（临时文件 → 重命名）
4. **向后兼容**: 系统自动兼容旧的状态值和文件格式

---

## 🐛 故障排除

### 命令不识别

如果命令不被识别，检查：
1. Python版本（需要Python 3.11+）
2. 工作目录（应在项目根目录）
3. 脚本路径是否正确

### 状态转换错误

如果出现"无效状态转换"错误：
- 检查当前状态和目标状态是否符合状态转换规则
- 使用`validate_integrity`工具检查数据一致性

### 并发冲突

如果出现"无法获取锁"错误：
1. 等待当前进程完成（30秒超时）
2. 检查是否有其他进程正在运行
3. 如果确定无其他进程，重启Python进程

---

**最后更新**: 2025-11-XX

