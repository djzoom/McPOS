# YouTube 标题验证功能实现

## 问题描述

YouTube 标题有时会出现以下问题：
1. **长度过长**：超过 100 字符限制（YouTube 要求）
2. **中断的词**：标题被截断，出现不完整的词（如 "ambie" 而不是 "ambient"）
3. **不完整的括号**：只有一半括号（如 "(ambient" 或 "cut)"）

## 实现方案

### 1. 标题验证函数

**文件**: `src/core/youtube_assets.py`

**函数**: `validate_youtube_title(title: str) -> tuple[bool, Optional[str]]`

**检查项**：
1. ✅ **长度检查**：不超过 100 字符
2. ✅ **括号完整性**：
   - 检查开括号和闭括号数量是否匹配
   - 检查是否有不完整的括号对（开括号后没有闭括号，或闭括号前没有开括号）
3. ✅ **中断词检测**：
   - 检查最后一个词是否可能是中断的（短词且不在常见词列表中）
   - 检查词是否以不完整后缀结尾（如 "ie", "nt", "ly"）
4. ✅ **截断模式检测**：
   - 检查标题首尾是否有空白字符
   - 检查末尾是否有不完整的模式（空格后跟标点）

### 2. Prompt 更新

**文件**: `src/core/youtube_assets.py` - `build_title_prompt`

**修改内容**：
- 将最大长度从 90 字符改为 **100 字符**（YouTube 要求）
- 添加了 **CRITICAL** 要求：
  - Title must be complete - no truncated words
  - All parentheses must be complete pairs
  - Title must end with a complete word, not mid-word

### 3. 生成后验证和重试

**文件**: `src/core/youtube_assets.py` - `generate_youtube_title_desc`

**实现**：
- 添加了重试机制（最多 3 次）
- 每次生成后立即验证标题
- 如果验证失败，记录警告并重新生成
- 如果 3 次尝试都失败，抛出 `RuntimeError` 包含详细错误信息

### 4. 清理后验证

**文件**: `kat_rec_web/backend/t2r/routes/automation.py` - `filler_generate_text_assets`

**实现**：
- 在清理标题后（移除 "× Vibe Coding"、处理括号等）进行验证
- 如果验证失败，记录错误但不抛出异常（让调用者决定如何处理）
- 将验证错误添加到结果中的 `errors` 字段

## 验证逻辑详解

### 长度检查
```python
if len(title) > 100:
    return False, f"标题长度超过 100 字符（当前: {len(title)} 字符）"
```

### 括号完整性检查
```python
open_count = title.count('(')
close_count = title.count(')')
if open_count != close_count:
    return False, f"括号不匹配：有 {open_count} 个开括号和 {close_count} 个闭括号"
```

### 中断词检测
- 检查最后一个词是否很短（1-4 个字母）
- 检查是否不在常见短词列表中
- 检查是否以不完整后缀结尾（如 "ie", "nt", "ly"）
- 如果满足以上条件，可能是中断的词

### 截断模式检测
- 检查标题首尾是否有空白字符
- 检查末尾是否有空格后跟标点的模式

## 使用示例

### 在生成标题时自动验证和重试

```python
from src.core.youtube_assets import generate_youtube_title_desc

title, description = generate_youtube_title_desc(
    original_title="Test Album",
    playlist_data=playlist_data,
    api_key=api_key,
    api_base=api_base,
    model=model,
    logger=logger
)
# 如果标题验证失败，会自动重试最多 3 次
# 如果 3 次都失败，会抛出 RuntimeError
```

### 手动验证标题

```python
from src.core.youtube_assets import validate_youtube_title

is_valid, error = validate_youtube_title(title)
if not is_valid:
    print(f"标题验证失败: {error}")
```

## 相关文件

- `src/core/youtube_assets.py` - 验证函数和生成逻辑
- `kat_rec_web/backend/t2r/routes/automation.py` - 清理后验证

## 更新日期

2025-01-XX

