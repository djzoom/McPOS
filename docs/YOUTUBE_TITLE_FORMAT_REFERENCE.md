# YouTube 标题格式参考

## YouTube "Develop idea" 样例

YouTube 的 AI 内容生成建议功能提供了以下标题格式作为参考：

1. **Morning Dew & Unfurling Petals LP**
2. **Glimmering Shores & Whispering Tides LP**
3. **Ember Glow & Hearthside Reveries LP**
4. **Silent Forests & Echoing Moonbeams LP**
5. **Urban Solitude & City Night Melodies LP**

## 格式特点

### 结构
- **双主题格式**：`{Theme1} & {Theme2} LP`
- **简洁性**：没有品牌标识（如 "Kat Records Presents"）
- **诗意性**：每个主题都是 2-3 个词的意象组合
- **对称性**：两个主题在长度和韵律上平衡

### 主题特征
- **主题1**：通常是自然/环境意象（Morning Dew, Glimmering Shores, Ember Glow, Silent Forests, Urban Solitude）
- **主题2**：通常是动作/情感意象（Unfurling Petals, Whispering Tides, Hearthside Reveries, Echoing Moonbeams, City Night Melodies）
- **连接词**：使用 "&" 连接，简洁有力
- **后缀**：统一使用 "LP" 标识

### 词汇风格
- **形容词 + 名词**：如 "Morning Dew", "Silent Forests"
- **动名词 + 名词**：如 "Unfurling Petals", "Whispering Tides"
- **抽象概念**：如 "Reveries", "Solitude", "Melodies"
- **自然意象**：如 "Dew", "Shores", "Forests", "Moonbeams"

## 与当前格式对比

### 当前格式（Kat Records）
```
{Album Title} LP | Kat Records Presents {Atmospheric Subtitle} (optional descriptor)
```

**示例**：
- Neon Memory LP | Kat Records Presents Liquid Dreams at Midnight (lofi edition)
- Rainlight Café LP | Kat Records Presents Urban Whispers in Twilight (lofi edition)

### YouTube 样例格式
```
{Theme1} & {Theme2} LP
```

**示例**：
- Morning Dew & Unfurling Petals LP
- Glimmering Shores & Whispering Tides LP

## 差异分析

| 维度 | 当前格式 | YouTube 样例格式 |
|------|---------|-----------------|
| **长度** | 较长（60-100 字符） | 较短（30-50 字符） |
| **品牌标识** | 包含 "Kat Records Presents" | 无品牌标识 |
| **结构复杂度** | 三段式（标题 + 品牌 + 副标题） | 单段式（双主题） |
| **诗意性** | 高（多层意象） | 高（简洁意象） |
| **SEO 友好度** | 中等（品牌词占用空间） | 高（更多关键词空间） |
| **识别度** | 高（品牌明确） | 低（无品牌） |

## 应用建议

### 方案 1：保持当前格式（推荐）
**理由**：
- 品牌识别度高（"Kat Records Presents"）
- 符合虚拟唱片厂牌的定位
- 已有成熟的 prompt 和验证逻辑

**优化方向**：
- 参考 YouTube 样例的**双主题意象组合**方式
- 在副标题中采用 `{Theme1} & {Theme2}` 的简洁结构
- 例如：`Neon Memory LP | Kat Records Presents Morning Dew & Unfurling Petals`

### 方案 2：提供备选格式
**实现**：
- 在 `build_youtube_title_prompt` 中添加格式选项
- 支持生成两种格式：
  1. **完整格式**（当前）：`{Album} LP | Kat Records Presents {Subtitle}`
  2. **简洁格式**（YouTube 风格）：`{Theme1} & {Theme2} LP`

**使用场景**：
- 完整格式：用于品牌推广和识别
- 简洁格式：用于 SEO 优化和简洁展示

### 方案 3：混合格式
**结构**：
```
{Theme1} & {Theme2} LP | Kat Records
```

**示例**：
- Morning Dew & Unfurling Petals LP | Kat Records
- Glimmering Shores & Whispering Tides LP | Kat Records

**优点**：
- 保留品牌标识（但更简洁）
- 采用 YouTube 样例的双主题格式
- 长度适中（40-60 字符）

## Prompt 改进建议

### 当前 Prompt 可以增强的部分

1. **双主题意象提取**：
   ```
   从曲目中提取两个互补的主题：
   - 主题1：环境/自然意象（如 Morning Dew, Silent Forests）
   - 主题2：动作/情感意象（如 Unfurling Petals, Echoing Moonbeams）
   ```

2. **简洁性指导**：
   ```
   如果空间允许，考虑使用双主题格式：
   "{Theme1} & {Theme2}" 作为副标题
   例如："Morning Dew & Unfurling Petals"
   ```

3. **韵律平衡**：
   ```
   确保两个主题在长度和韵律上平衡：
   - 避免一个主题过长，另一个过短
   - 保持节奏感（如 "Morning Dew" 与 "Unfurling Petals"）
   ```

## 实施建议

### 短期（立即）
1. **更新 Prompt**：在 `build_youtube_title_prompt` 中添加 YouTube 样例作为参考
2. **增强意象提取**：鼓励 AI 生成双主题意象组合

### 中期（1-2 周）
1. **添加格式选项**：支持生成多种格式（完整/简洁/混合）
2. **格式验证**：确保双主题格式的平衡性和诗意性

### 长期（1-3 个月）
1. **A/B 测试**：比较不同格式的点击率和观看时长
2. **智能选择**：根据内容特征自动选择最佳格式

## 相关文件

- `mcpos/adapters/ai_title_generator.py` - 标题生成逻辑
- `mcpos/adapters/ai_title_generator.py::build_youtube_title_prompt()` - YouTube 标题 prompt
- `mcpos/adapters/ai_title_generator.py::validate_youtube_title()` - 标题验证

## 参考资源

- YouTube Creator Studio: "Develop idea" 功能
- YouTube 标题最佳实践指南
- Lo-fi 音乐频道标题分析

