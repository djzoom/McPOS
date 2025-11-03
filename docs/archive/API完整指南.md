# 📡 Kat Records Studio - API 完整指南

**最后更新**: 2025-11-01

---

本文档整合了API的使用、安全、状态检查和常见问题，是API相关功能的完整参考。

---

## 📋 目录

1. [API使用指南](#api使用指南)
2. [API安全指南](#api安全指南)
3. [API状态检查](#api状态检查)
4. [常见问题](#常见问题)

---

## 📡 API使用指南

### 概述

**⚠️ 重要：本项目必须使用 OpenAI API，没有API将无法工作。**

项目使用 OpenAI API 来生成高质量的标题和描述。所有内容生成都依赖API，没有本地fallback机制。

**API 密钥配置位置**（按优先级）：
1. **配置文件**（推荐）: `config/openai_api_key.txt`
2. **环境变量**: `OPENAI_API_KEY`

**首次配置**：
- 运行任何命令时，如果没有API密钥，系统会自动提示交互式输入
- 或手动运行：`make check-api` 检查状态

---

### API 使用场景

#### 1. 📝 唱片标题生成

**位置**: 
- `scripts/local_picker/create_mixtape.py`
- `scripts/local_picker/generate_full_schedule.py`

**功能**: 
- 根据图片、颜色、曲目关键词生成诗意、独特的唱片标题
- 自动去重检查，避免重复标题模式
- 如果重复，自动重试（最多3次）

**API 调用**:
```python
_try_openai_title(
    image_filename: str,
    dominant_rgb: Tuple[int, int, int],
    playlist_keywords: List[str],
    seed: int,
    api_key: str
) -> str | None
```

**模型**: `gpt-4o-mini`

**Prompt 特点**:
- 要求生成短诗意的专辑标题（最多8个词）
- 避免常见短语如 "dreams of", "night of"
- 强调创意性和独特性

---

#### 2. 📄 YouTube标题生成

**位置**: `scripts/local_picker/generate_youtube_assets.py`

**功能**: 
- 根据专辑标题生成SEO优化的YouTube标题
- 遵循「Kat Records × Vibe Coding」品牌策略

**标题格式**:
```
[专辑名 LP] | Kat Records × Vibe Coding Presents [副标题 / 氛围短语]
```

**模型**: `gpt-4o-mini`

---

#### 3. 📝 YouTube描述生成

**位置**: `scripts/local_picker/generate_youtube_assets.py`

**功能**: 
- 生成完整的YouTube视频描述
- 包含厂牌介绍、氛围描述、曲目列表、品牌签名

**模型**: `gpt-4o-mini`
**最大token**: 1200

---

#### 4. 🎬 SRT字幕生成

**位置**: `scripts/local_picker/generate_youtube_assets.py`

**功能**: 
- 根据歌单生成SRT格式字幕
- 包含时间轴和曲目信息

---

### 配置方法

#### 方法1：交互式配置（推荐）

运行任何生成命令时，如果没有API密钥会自动提示：

```bash
python scripts/local_picker/create_mixtape.py --episode-id 20251101
# 会自动显示交互式输入界面
```

#### 方法2：使用配置脚本

```bash
bash scripts/setup_api_key.sh
```

#### 方法3：手动配置

```bash
# 创建配置文件
echo "sk-your-api-key-here" > config/openai_api_key.txt

# 设置权限
chmod 600 config/openai_api_key.txt
```

#### 方法4：环境变量

```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

---

## 🔐 API安全指南

### API密钥保存机制

#### 交互式输入时的保存选项

当您首次运行生成命令时，如果系统检测到没有API密钥，会显示交互式输入界面：

```
🔑 OpenAI API 密钥配置
======================================================================

请输入您的 OpenAI API 密钥 (输入为空取消): 

是否保存到配置文件以便下次使用？(Y/n):
```

**默认行为**：
- ✅ **默认保存**：如果直接按回车，密钥会保存到 `config/openai_api_key.txt`
- ⚠️ **可选不保存**：输入 `n` 则只在本次会话中使用（使用环境变量）

#### 保存位置

API密钥可以保存在以下位置（按优先级）：

1. **配置文件**（推荐）：`config/openai_api_key.txt`
   - 仅在本地存储
   - 文件权限自动设置为 600（仅所有者可读写）
   - 已在 `.gitignore` 中，不会被Git追踪

2. **环境变量**：`OPENAI_API_KEY`
   - 适合生产环境或CI/CD
   - 不存储在文件系统中

---

### 安全措施

#### 1. 文件权限保护

保存密钥时，系统会自动设置文件权限为 `600`：

```bash
# 自动执行（在 api_config.py 中）
chmod 600 config/openai_api_key.txt
```

**权限说明**：
- `600` = `rw-------` (仅所有者可读写)
- 其他用户无法读取或修改

**验证权限**：
```bash
ls -la config/openai_api_key.txt
# 应该显示: -rw-------  (600权限)
```

#### 2. Git 保护

API密钥文件已在 `.gitignore` 中：

```gitignore
# API Keys (安全：绝不提交)
config/openai_api_key.txt
config/*_api_key.txt
config/*_secret.txt
**/openai_api_key.txt
**/*_api_key.txt
```

**验证是否被Git追踪**：
```bash
git check-ignore config/openai_api_key.txt
# 应该返回: config/openai_api_key.txt (表示被忽略)
```

#### 3. 输入安全

- 使用 `getpass.getpass()` 输入密钥（不回显）
- 不会在终端历史记录中保存
- 不会在日志中显示完整密钥

#### 4. 密钥格式验证

保存前会验证密钥格式：
- 必须以 `sk-` 开头
- 长度至少 20 字符
- 如果格式错误，会提示重新输入

---

### 安全检查清单

#### ✅ 配置前检查

1. **确认项目目录是私有的**
   ```bash
   # 检查目录权限
   ls -ld /Users/z/Downloads/Kat_Rec
   # 应该只有您有访问权限
   ```

2. **确认 .gitignore 已配置**
   ```bash
   git check-ignore config/openai_api_key.txt
   ```

3. **如果使用 Git，确保未追踪**
   ```bash
   git ls-files config/openai_api_key.txt
   # 应该返回空（未被追踪）
   ```

#### ✅ 配置后检查

1. **验证文件权限**
   ```bash
   ls -la config/openai_api_key.txt
   # 应该显示: -rw------- 1 user group ...
   ```

2. **验证Git状态**
   ```bash
   git status
   # config/openai_api_key.txt 不应该出现在未追踪文件中
   ```

3. **测试API连接**
   ```bash
   make check-api --test
   # 应该显示: API连接成功 ✅
   ```

---

### 安全最佳实践

#### ✅ 应该做的

1. **使用配置文件时**：
   - ✅ 确保文件权限为 600
   - ✅ 确认已在 `.gitignore` 中
   - ✅ 定期检查文件是否意外被提交

2. **使用环境变量时**：
   - ✅ 不要将密钥写入公开的脚本
   - ✅ 使用密钥管理工具（如 macOS Keychain）
   - ✅ 在CI/CD中使用加密的环境变量

3. **共享代码时**：
   - ✅ 确保 `.gitignore` 包含所有密钥文件
   - ✅ 使用 `.env.example` 模板（不含真实密钥）
   - ✅ 不要通过截图、日志或聊天工具分享密钥

4. **密钥泄露后**：
   - ✅ **立即在 OpenAI 平台删除该密钥**
   - ✅ 创建新密钥
   - ✅ 更新配置文件

#### ❌ 不应该做的

1. ❌ **不要将密钥提交到Git**
2. ❌ **不要将密钥硬编码在代码中**
3. ❌ **不要分享密钥给他人**
4. ❌ **不要在公开仓库中暴露**
5. ❌ **不要使用过于宽松的文件权限**

---

### 密钥更换流程

如果密钥泄露或需要更换：

1. **在 OpenAI 平台删除旧密钥**
   - 访问: https://platform.openai.com/api-keys
   - 找到旧密钥，点击删除

2. **更新本地配置**
   ```bash
   # 方法1：使用配置脚本（推荐）
   bash scripts/setup_api_key.sh
   
   # 方法2：手动编辑
   nano config/openai_api_key.txt  # 编辑并保存
   chmod 600 config/openai_api_key.txt
   
   # 方法3：删除后重新输入
   rm config/openai_api_key.txt
   # 下次运行时会自动提示输入
   ```

3. **更新环境变量**（如果使用）
   ```bash
   # 编辑 ~/.zshrc 或 ~/.bashrc
   nano ~/.zshrc
   # 更新 OPENAI_API_KEY 的值
   source ~/.zshrc
   ```

4. **验证新密钥**
   ```bash
   make check-api --test
   ```

---

## 🔍 API状态检查

### 快速检查

#### 方法1：使用检查脚本（推荐）

```bash
# 基本检查（不调用API，仅检查配置）
python scripts/check_api_status.py

# 或使用Makefile
make check-api
```

#### 方法2：实际API测试（验证连接）

```bash
# 执行实际API调用测试（会产生少量费用）
python scripts/check_api_status.py --test

# 或使用Makefile
make test-api
```

---

### 检查内容

脚本会检查以下方面：

1. **API密钥配置** ✅
   - 检查配置文件 (`config/openai_api_key.txt`)
   - 检查环境变量 (`OPENAI_API_KEY`)
   - 显示配置来源
   - 显示密钥格式（部分遮蔽，安全显示）

2. **文件权限检查** 🔒
   - 检查配置文件权限（应该是 600）
   - ⚠️  如果权限不安全，会提示修复

3. **Git安全检查** 🛡️
   - 检查密钥文件是否在 `.gitignore` 中
   - ⚠️  如果已被Git追踪，会警告

4. **API连接测试** 🌐
   - 密钥格式验证（基本检查）
   - 实际API调用测试（`--test` 模式）
   - 网络连接检查
   - API响应验证

---

### 检查结果示例

#### ✅ API已配置且就绪

```
======================================================================
🔍 OpenAI API 就绪状态检查
======================================================================

📋 1. API密钥配置检查
----------------------------------------------------------------------
✅ API密钥已配置
   来源: 环境变量 (OPENAI_API_KEY)
   密钥: sk-proj-...abcd
   长度: 51 字符

📋 2. 文件权限检查
----------------------------------------------------------------------
✅ 配置文件不存在（使用环境变量）

📋 3. Git安全检查
----------------------------------------------------------------------
✅ 密钥文件未被Git追踪

📋 4. API连接测试
----------------------------------------------------------------------
✅ 密钥格式正确
💡 提示：使用 --test 参数执行实际API调用测试
```

#### ❌ API未配置

```
======================================================================
🔍 OpenAI API 就绪状态检查
======================================================================

📋 1. API密钥配置检查
----------------------------------------------------------------------
❌ API密钥未配置
   来源: 未找到配置

💡 配置方法：
   1. 运行配置脚本: bash scripts/setup_api_key.sh
   2. 使用环境变量: export OPENAI_API_KEY='sk-...'
   3. 创建配置文件: echo 'sk-...' > config/openai_api_key.txt
```

---

## ❓ 常见问题

### Q: API密钥会泄露吗？

**A**: 不会，系统已实施多重安全措施：

1. **文件权限保护**
   - 配置文件自动设置为 `600` 权限（仅所有者可读可写）
   - 其他用户无法读取您的API密钥

2. **Git保护**
   - `config/openai_api_key.txt` 已在 `.gitignore` 中
   - **绝不会被提交到Git仓库**
   - 即使您运行 `git add .`，API密钥文件也不会被添加

3. **输入保护**
   - 使用 `getpass.getpass()` 输入密钥（不回显）
   - 输入时终端不会显示密钥内容

4. **本地存储**
   - API密钥仅存储在您的本地计算机
   - 不会上传到任何服务器

### Q: API密钥何时失效？

**A**: 
- **永久有效**：除非您主动删除或重置密钥
- **使用限制**：受账户余额和额度限制
- **安全建议**：如果密钥泄露，立即在OpenAI平台删除并重新生成

### Q: 重启后还能用吗？

**A**: 是的，配置会自动加载！

配置机制：
1. **持久化存储** - 配置保存在 `config/openai_api_key.txt`
2. **自动加载优先级**（按顺序）：
   - 环境变量（最高优先级）
   - 配置文件：`config/openai_api_key.txt`
3. **重启后**：
   - ✅ 系统自动读取已保存的配置
   - ✅ 无需重新输入
   - ✅ 立即可用

### Q: 密钥保存在哪里？

**A**: 默认保存在 `config/openai_api_key.txt`，文件权限为 600（仅所有者可读）。

### Q: 密钥会被提交到Git吗？

**A**: 不会。`config/openai_api_key.txt` 已在 `.gitignore` 中，不会被Git追踪。

### Q: 可以使用环境变量吗？

**A**: 可以。设置 `export OPENAI_API_KEY="sk-..."` 即可，优先级高于配置文件。

### Q: 如果密钥泄露了怎么办？

**A**: 
1. 立即在 OpenAI 平台删除该密钥
2. 创建新密钥
3. 更新本地配置

### Q: 如何在团队中安全共享项目？

**A**: 
1. 确保 `.gitignore` 包含密钥文件
2. 创建 `.env.example` 模板（不含真实密钥）
3. 每个成员自行配置自己的密钥
4. 不要在团队聊天工具中分享密钥

### Q: macOS Keychain 支持吗？

**A**: 当前版本使用文件或环境变量。macOS Keychain 集成可在未来版本中添加。

---

## 📚 相关文档

- [命令行工作流](COMMAND_LINE_WORKFLOW.md) - 完整工作流程
- [文档索引](文档索引与阅读指南.md) - 所有文档索引
- [项目README](../README.md) - 项目概览

---

**最后更新**: 2025-11-01  
**维护者**: KAT Records 开发团队

