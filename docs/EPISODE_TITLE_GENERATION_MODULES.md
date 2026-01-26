# 节目标题生成模块横向对比分析

## 📋 概述

本报告对比分析了项目中所有与节目标题生成相关的模块和组件，评估它们的功能、使用场景和优缺点。

---

## 🔍 发现的标题生成模块（4个核心模块）

### 1. **mcpos/assets/text.py (TEXT_BASE阶段)** ⭐⭐⭐⭐⭐
**推荐度：最高（McPOS核心，生产环境）**

**代码规模**：618行（标题生成部分约250行）

**功能特点**：
- ✅ **McPOS TEXT_BASE阶段的核心实现**
- ✅ **调用AI生成标题**：通过 `ai_title_generator.py` 生成
- ✅ **支持多频道**：Kat频道使用AI生成，RBR频道使用模板生成
- ✅ **幂等性检查**：如果标题文件已存在，跳过生成
- ✅ **依赖检查**：确保 `playlist.csv` 存在
- ✅ **专辑标题生成**：先生成专辑标题，再生成YouTube标题
- ✅ **历史标题去重**：通过 `ai_title_generator.py` 避免重复

**核心函数**：
- `generate_text_base_assets(spec, paths)` - 生成文本基础资产（标题、描述、标签）
- `_generate_rbr_content(spec, paths, config)` - RBR频道特定内容生成

**使用场景**：
- ✅ McPOS pipeline的TEXT_BASE阶段
- ✅ 生产环境的标题生成
- ✅ 需要完整资产验证的场景

**调用链**：
```
mcpos/assets/text.py (generate_text_base_assets)
  └─> mcpos/adapters/ai_title_generator.py
      ├─> generate_album_title() - 生成专辑标题
      └─> generate_youtube_title_and_description() - 生成YouTube标题和描述
```

**优点**：
- ✅ McPOS架构的核心组件
- ✅ 完整的错误处理和日志
- ✅ 支持多频道（Kat、RBR）
- ✅ 幂等性保证
- ✅ 历史标题去重

**缺点**：
- ⚠️ 需要完整的McPOS环境
- ⚠️ 依赖OpenAI API（Kat频道）

**示例**：
```bash
# 通过McPOS CLI运行TEXT_BASE阶段
python3 -m mcpos.cli.main run-stage kat kat_20260208 TEXT_BASE
```

---

### 2. **mcpos/adapters/ai_title_generator.py** ⭐⭐⭐⭐⭐
**推荐度：最高（AI标题生成核心引擎）**

**代码规模**：1176行

**功能特点**：
- ✅ **AI标题生成核心引擎**：使用OpenAI API生成标题
- ✅ **专辑标题生成**：`generate_album_title()` - 生成专辑标题
- ✅ **YouTube标题生成**：`generate_youtube_title_and_description()` - 生成YouTube标题和描述
- ✅ **历史标题去重**：`load_historical_titles()` - 加载历史标题避免重复
- ✅ **标题相似度检测**：`calculate_title_similarity()` - 计算标题相似度
- ✅ **标题验证**：`validate_youtube_title()` - 验证YouTube标题格式
- ✅ **Prompt构建**：`build_youtube_title_prompt()` - 构建AI prompt
- ✅ **多模型支持**：支持gpt-4o-mini等模型

**核心函数**：
- `generate_album_title()` - 生成专辑标题（异步）
- `generate_youtube_title_and_description()` - 生成YouTube标题和描述（异步）
- `load_historical_titles()` - 加载历史标题
- `validate_youtube_title()` - 验证标题格式
- `build_youtube_title_prompt()` - 构建AI prompt

**使用场景**：
- ✅ 被 `mcpos/assets/text.py` 调用
- ✅ 被 `kat_rec_web/backend/t2r/services/channel_automation.py` 调用
- ✅ 需要AI生成标题的场景

**调用链**：
```
ai_title_generator.py
  └─> OpenAI API (gpt-4o-mini)
      └─> 返回生成的标题和描述
```

**优点**：
- ✅ 核心AI生成引擎
- ✅ 完整的历史标题去重机制
- ✅ 标题验证和格式检查
- ✅ 支持异步处理
- ✅ 详细的日志和错误处理

**缺点**：
- ⚠️ 依赖OpenAI API
- ⚠️ 需要API密钥配置

**配置**：
```python
TITLE_GENERATION_CONFIG = {
    "album_title": {
        "max_tokens": 100,
        "temperature": 0.8,
        "timeout": 30.0,
    },
    "youtube_title": {
        "max_tokens": 150,
        "temperature": 0.7,
        "timeout": 30.0,
    },
}
DEFAULT_MODEL = "gpt-4o-mini"
```

---

### 3. **kat_rec_web/backend/t2r/services/channel_automation.py** ⭐⭐⭐⭐
**推荐度：高（Web后端自动化服务）**

**代码规模**：1815行（标题生成部分约130行）

**功能特点**：
- ✅ **Web后端自动化服务**：用于Web前端的标题生成
- ✅ **分步生成**：`_generate_title_only()` - 只生成标题文件
- ✅ **文件级别进度跟踪**：`FileProgressTracker` - 跟踪生成进度
- ✅ **API配置检查**：检查OpenAI API配置
- ✅ **错误处理和事件通知**：通过WebSocket通知前端

**核心函数**：
- `_generate_title_only(channel_id, episode_id)` - 只生成标题文件
- `_generate_other_text_assets(channel_id, episode_id)` - 生成其他文本资产

**使用场景**：
- ✅ Web前端触发的标题生成
- ✅ 自动化工作流
- ✅ 需要进度跟踪的场景

**调用链**：
```
channel_automation.py (_generate_title_only)
  └─> filler_generate_text_assets() (通过API)
      └─> 最终调用 ai_title_generator.py
```

**优点**：
- ✅ Web API集成
- ✅ 文件级别进度跟踪
- ✅ 事件通知（WebSocket）
- ✅ 错误处理和状态管理

**缺点**：
- ⚠️ 仅用于Web后端
- ⚠️ 需要FastAPI环境
- ⚠️ 依赖其他服务

---

### 4. **scripts/fix_problematic_titles_api.py** ⭐⭐⭐
**推荐度：中等（修复工具）**

**代码规模**：约300行

**功能特点**：
- ✅ **修复工具**：用于修复有问题的标题
- ✅ **批量处理**：可以批量修复多个标题
- ✅ **API生成**：使用OpenAI API生成新标题
- ✅ **去重检查**：检查与现有标题的重复

**核心函数**：
- `generate_new_title_api()` - 生成新标题

**使用场景**：
- ✅ 修复有问题的标题
- ✅ 批量更新标题
- ✅ 一次性脚本

**调用链**：
```
fix_problematic_titles_api.py
  └─> OpenAI API
      └─> 生成新标题并写入文件
```

**优点**：
- ✅ 简单直接的修复工具
- ✅ 批量处理支持

**缺点**：
- ⚠️ 一次性脚本，不用于生产流程
- ⚠️ 需要手动运行

---

## 📊 功能对比表

| 功能 | text.py (TEXT_BASE) | ai_title_generator.py | channel_automation.py | fix_problematic_titles_api.py |
|------|---------------------|----------------------|----------------------|------------------------------|
| **AI标题生成** | ✅ **（调用）** | ✅ **（核心引擎）** | ✅ **（调用）** | ✅ |
| **专辑标题生成** | ✅ | ✅ **（核心）** | ✅ | ❌ |
| **YouTube标题生成** | ✅ | ✅ **（核心）** | ✅ | ✅ |
| **历史标题去重** | ✅ | ✅ **（核心）** | ✅ | ⚠️ (基本) |
| **标题验证** | ✅ | ✅ **（核心）** | ✅ | ❌ |
| **多频道支持** | ✅ **（Kat、RBR）** | ✅ | ✅ | ❌ |
| **幂等性** | ✅ **（核心）** | ❌ | ✅ | ❌ |
| **进度跟踪** | ❌ | ❌ | ✅ **（文件级别）** | ❌ |
| **Web API集成** | ❌ | ❌ | ✅ **（核心）** | ❌ |
| **错误处理** | ✅ **（详细）** | ✅ **（详细）** | ✅ | ⚠️ (基本) |
| **McPOS集成** | ✅ **（核心）** | ✅ | ❌ | ❌ |
| **使用场景** | 生产环境 | 核心引擎 | Web后端 | 修复工具 |

---

## 🎯 使用场景推荐

### 场景1：McPOS Pipeline标题生成（推荐）⭐⭐⭐⭐⭐

**使用 `mcpos/assets/text.py` (TEXT_BASE阶段)**

**适用场景**：
- ✅ 生产环境的标题生成
- ✅ 完整的McPOS pipeline
- ✅ 需要资产验证的场景

**理由**：
- McPOS架构的核心组件
- 完整的错误处理和日志
- 幂等性保证
- 历史标题去重

**调用方式**：
```bash
# 通过McPOS CLI运行TEXT_BASE阶段
python3 -m mcpos.cli.main run-stage kat kat_20260208 TEXT_BASE

# 或运行完整pipeline（会自动运行TEXT_BASE）
python3 -m mcpos.cli.main run-episode kat kat_20260208
```

---

### 场景2：Web前端标题生成 ⭐⭐⭐⭐

**使用 `kat_rec_web/backend/t2r/services/channel_automation.py`**

**适用场景**：
- ✅ Web前端触发的标题生成
- ✅ 需要进度跟踪的场景
- ✅ 自动化工作流

**理由**：
- Web API集成
- 文件级别进度跟踪
- 事件通知（WebSocket）

---

### 场景3：修复有问题的标题 ⭐⭐⭐

**使用 `scripts/fix_problematic_titles_api.py`**

**适用场景**：
- ✅ 修复有问题的标题
- ✅ 批量更新标题
- ✅ 一次性修复任务

**理由**：
- 简单直接的修复工具
- 批量处理支持

---

## 🏆 最终推荐

### **最佳选择：`mcpos/assets/text.py` (TEXT_BASE阶段)** ⭐⭐⭐⭐⭐

**为什么它最好用**：

1. **McPOS架构核心**：是McPOS pipeline的标准阶段
2. **完整的资产验证**：确保所有依赖文件存在
3. **幂等性保证**：可以安全地重复运行
4. **历史标题去重**：通过 `ai_title_generator.py` 避免重复
5. **多频道支持**：Kat频道使用AI，RBR频道使用模板

**核心流程**：

```
TEXT_BASE阶段流程：
1. 检查幂等性（标题文件已存在则跳过）
2. 读取 playlist.csv（必需）
3. 读取 recipe.json（可选，用于主题色和封面信息）
4. 根据频道类型选择生成方式：
   - Kat频道：调用AI生成（必需API）
   - RBR频道：使用模板生成（基于BPM和时长）
5. 生成专辑标题（Kat频道）
6. 生成YouTube标题和描述
7. 生成标签
8. 写入文件：
   - <episode_id>_youtube_title.txt
   - <episode_id>_youtube_description.txt
   - <episode_id>_youtube_tags.txt
```

---

## 📝 标题生成流程详解

### Kat频道标题生成流程

```
1. 读取 playlist.csv
   └─> 提取曲目列表（tracks_a, tracks_b）

2. 读取 recipe.json（可选）
   └─> 提取封面图片文件名和主题色

3. 调用 generate_album_title()
   └─> 使用AI生成专辑标题
   └─> 检查历史标题去重
   └─> 验证标题格式

4. 调用 generate_youtube_title_and_description()
   └─> 使用AI生成YouTube标题和描述
   └─> 基于专辑标题和曲目列表
   └─> 验证标题格式

5. 生成标签
   └─> 基础标签（#KatRecords等）
   └─> 曲目相关标签

6. 写入文件
   └─> youtube_title.txt
   └─> youtube_description.txt
   └─> youtube_tags.txt
```

### RBR频道标题生成流程

```
1. 读取 recipe.json 或 channel config
   └─> 提取BPM和时长

2. 使用模板生成
   └─> 标题："{duration}-Minute {bpm}BPM Running Music | {action_phrase} | {series_tagline}"
   └─> 描述：基于BPM和时长的模板描述
   └─> 标签：基础标签 + BPM相关标签

3. 写入文件
   └─> youtube_title.txt
   └─> youtube_description.txt
   └─> youtube_tags.txt
```

---

## 🔧 配置要求

### OpenAI API配置

**方法1：配置文件（推荐）**
```bash
echo 'your-api-key-here' > config/openai_api_key.txt
```

**方法2：环境变量**
```bash
export OPENAI_API_KEY='your-api-key-here'
```

**方法3：.envrc文件**
```bash
source .envrc
```

### 历史标题数据

**数据文件**：`mcpos/data/historical_titles.json`

**格式**：
```json
{
  "album_titles": [
    "标题1",
    "标题2",
    ...
  ]
}
```

**回退机制**：如果数据文件不存在，会从所有episode的 `recipe.json` 中读取 `album_title` 字段。

---

## 📊 模块依赖关系

```
mcpos/assets/text.py (TEXT_BASE阶段)
  └─> mcpos/adapters/ai_title_generator.py
      ├─> generate_album_title()
      └─> generate_youtube_title_and_description()
          └─> OpenAI API

kat_rec_web/backend/t2r/services/channel_automation.py
  └─> filler_generate_text_assets() (API)
      └─> 最终调用 ai_title_generator.py
```

---

## 🎯 总结

### 模块数量统计

- **核心标题生成**：2个（text.py, ai_title_generator.py）
- **Web服务**：1个（channel_automation.py）
- **修复工具**：1个（fix_problematic_titles_api.py）

### 推荐使用顺序

1. **McPOS Pipeline标题生成**：`mcpos/assets/text.py` (TEXT_BASE阶段) ⭐⭐⭐⭐⭐
2. **Web前端标题生成**：`kat_rec_web/backend/t2r/services/channel_automation.py` ⭐⭐⭐⭐
3. **修复工具**：`scripts/fix_problematic_titles_api.py` ⭐⭐⭐

### 关键发现

1. ✅ **text.py是核心**：McPOS pipeline的标准TEXT_BASE阶段实现
2. ✅ **ai_title_generator.py是引擎**：所有AI标题生成都通过它
3. ✅ **历史标题去重**：通过 `load_historical_titles()` 避免重复
4. ✅ **多频道支持**：Kat频道使用AI，RBR频道使用模板
5. ✅ **幂等性保证**：可以安全地重复运行

---

**报告生成时间**：2026-01-26
**最后更新**：2026-01-26
**推荐模块**：`mcpos/assets/text.py` (TEXT_BASE阶段) ⭐⭐⭐⭐⭐
