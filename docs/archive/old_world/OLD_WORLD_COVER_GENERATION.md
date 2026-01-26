# 旧世界封面生成方法调研

本文档记录旧世界（`scripts/local_picker/create_mixtape.py`）的封面生成方法，供 McPOS 参考排版、字体、图片裁剪等设计细节。

## 一、画布尺寸与缩放

### 基础尺寸
- **8K 主图**：`CANVAS_SIZE_8K = (7680, 4320)` - 用于生成最终封面
- **4K 尺寸**：`CANVAS_SIZE_4K = (3840, 2160)` - 用于某些计算
- **缩放比例**：`SCALE_4K = 0.5` - 用于字体大小等参数的计算

### 实际使用
- `compose_cover()` 函数使用 `CANVAS_SIZE_4K`（3840×2160）作为画布
- 但注释中提到"Base canvas is layout.canvas_size (defaults to 7680x4320)"，实际代码中使用的是 4K

## 二、布局配置（CoverLayoutConfig）

### 关键参数
```python
@dataclass
class CoverLayoutConfig:
    canvas_size: Tuple[int, int] = CANVAS_SIZE_4K  # (3840, 2160)
    x_margin_frac: float = 0.08                    # 水平边距比例
    y_margin_frac: float = 0.18                    # 垂直边距比例
    left_block_width_frac: float = 0.38            # 左侧区块宽度比例
    spine_width_px: int = int(90 * SCALE_4K)      # 封脊宽度（像素）
    spine_x_pos: int = int(3295 * SCALE_4K)        # 封脊X位置
    title_size_frac: float = 0.035                 # 标题字号比例
    body_size_frac: float = 0.012                   # 正文字号比例
    side_title_size_frac: float = 0.018            # Side A/B 标题字号比例
    min_title_px: int = int(36 * SCALE_4K)         # 最小标题字号
    min_body_px: int = int(16 * SCALE_4K)          # 最小正文字号
    side_title_x_offset: float = 0.03              # Side 标题X偏移
    text_opacity: float = 1.0                      # 文字不透明度
    title_right_center_frac: float = 0.70         # 右侧标题中心位置比例
    title_top_margin: int = int(250 * SCALE_4K)    # 标题顶部边距
```

## 三、图片裁剪与粘贴

### 主图区域参数（固定位置）
```python
box_x, box_y = 1885, 282      # 主图左上角坐标
box_w, box_h = 1746, 1599     # 主图宽度和高度
```

### 裁剪逻辑
1. **计算宽高比**：
   - `img_ratio = img.width / img.height`
   - `box_ratio = box_w / box_h`

2. **等比缩放并裁剪**：
   - 如果 `img_ratio > box_ratio`（图片更扁）：
     - 按高度拉伸：`img_scale = box_h / img.height`
     - 缩放后宽度：`new_w = int(img.width * img_scale)`
     - 居中裁剪：`left = (new_w - box_w) // 2`
     - 裁剪区域：`(left, 0, left + box_w, box_h)`
   
   - 如果 `img_ratio <= box_ratio`（图片更高）：
     - 按宽度拉伸：`img_scale = box_w / img.width`
     - 缩放后高度：`new_h = int(img.height * img_scale)`
     - 居中裁剪：`top = (new_h - box_h) // 2`
     - 裁剪区域：`(0, top, box_w, top + box_h)`

3. **粘贴到画布**：
   - 使用 `canvas.paste(img_cropped, (box_x, box_y), img_cropped)`
   - 第三个参数 `img_cropped` 作为 alpha 蒙版，支持透明图片

## 四、背景色与噪点叠加

### 背景色
- 使用传入的 `color_hex`（十六进制颜色）
- 转换为 RGB：`bg_color = tuple(int(color_hex[i : i + 2], 16) for i in (0, 2, 4))`
- 创建 RGBA 画布：`canvas = Image.new("RGBA", (width, height), bg_color + (255,))`

### 噪点叠加（做旧效果）
```python
import numpy as np
noise_strength = 18  # 噪点强度，建议10~30
noise_alpha = 32     # 透明度，建议16~48
noise = np.random.normal(128, noise_strength, (height, width)).clip(0,255).astype(np.uint8)
noise_img = Image.fromarray(noise, mode="L").convert("RGBA")
alpha = Image.new("L", (width, height), noise_alpha)
noise_img.putalpha(alpha)
canvas = Image.alpha_composite(canvas, noise_img)
```

## 五、字体选择

### 字体目录
- `FONT_DIR = REPO_ROOT / "assets/fonts"`
- 支持 `.ttf` 和 `.otf` 格式

### 字体选择逻辑
1. **优先使用指定字体**：如果 `font_name` 参数提供，在 `FONT_DIR` 中查找匹配的字体文件
2. **随机选择**：如果没有指定，使用 `choose_font_path(rng)` 从可用字体中随机选择
3. **回退**：如果找不到字体，使用系统默认字体（Arial.ttf 或 `ImageFont.load_default()`）

### 常用字体
- 代码中提到了 `Lora` 字体（在 Dev_Bible 中提到）
- 实际字体选择是动态的，从 `assets/fonts/` 目录中随机选择

## 六、歌单区块布局

### 歌单区块参数（固定位置）
```python
block_x = 251      # 区块左上角X坐标
block_y = 225      # 区块左上角Y坐标
block_w = 1100     # 区块宽度
block_h = 1400     # 区块高度
```

### 字体自适应算法
1. **基准行数**：始终以 AB 各 12 首（24行）为基准，保证字体不会因曲目少而过大
2. **二分查找**：在 `min_px` 到 `max_px` 之间二分查找最大字号
   - `min_px = int(12 * scale)`
   - `max_px = int(180 * scale)`
3. **测量函数**：`measure_block(font_size)` 计算：
   - 总高度（包括 Side A/B 标题、空行、曲目行）
   - 最大行宽度
   - 确保 `h <= block_h` 且 `max_line_w <= block_w`
4. **字体大小关系**：
   - `body_font`：正文字体（曲目列表）
   - `side_title_font = body_font * 1.5`：Side A/B 标题字体（正文字体的 1.5 倍）

### 歌单文本格式
- **Side A/B 标题**：`"SIDE A"` / `"SIDE B"`，居中显示
- **曲目行**：`"{idx:02d}. {track.title}"`（例如：`"01. Song Title"`）
- **行间距**：`body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)`

### 垂直居中
- 计算实际内容总高度
- `start_y = block_y + (block_h - h) // 2` 实现上下居中
- `center_x = block_x + block_w // 2` 实现水平居中

## 七、标题布局

### 右侧水平标题（主标题）
1. **位置**：
   - X 坐标：与主图水平中心对齐
     ```python
     image_center_x = box_x + box_w // 2  # 1885 + 1746 // 2 = 2758
     title_width = text_draw.textlength(title, font=title_font)
     title_x = image_center_x - int(title_width / 2)
     ```
   - Y 坐标：在图片上方，画布上边的正中央
     ```python
     top_area_center = int((box_y - title_height) // 2)  # (282 - title_height) // 2
     title_y = top_area_center
     ```

2. **字体大小**：
   - `title_font = side_title_font.size + 10`（比 Side A/B 标题大 10 像素）

3. **颜色**：
   - 纯白色，85% 不透明度：`fill_title_full = (255, 255, 255, 217)`

### 封脊垂直标题（Spine Title）
1. **位置**：
   - X 坐标：`spine_x_pos = int(3295 * SCALE_4K)`（默认）或使用传入的 `spine_x` 参数
   - Y 坐标：垂直居中 `paste_y = (height - spine_img.height) // 2`

2. **字体自适应**：
   - 最小字号：`min_spine_px = max(cfg.min_body_px, int(18 * scale))`
   - 最大字号：`max_spine_px = min(cfg.spine_width_px, body_font.size)`
   - 逐步增大字号，确保：
     - `text_w <= int(height * 0.95)`（文本宽度不超过画布高度的 95%）
     - `text_h <= int(cfg.spine_width_px * 0.95)`（文本高度不超过封脊宽度的 95%）

3. **旋转与粘贴**：
   - 先水平绘制文本到临时图像
   - 旋转 -90 度：`spine_img = spine_img.rotate(-90, expand=True)`
   - 粘贴到主画布：`canvas.alpha_composite(spine_img, (use_spine_x - spine_img.width // 2, paste_y))`

4. **填充与边距**：
   - 顶部对齐绘制，避免下半部分被裁切
   - 增加高度冗余：`pad_h = int(text_h * 0.3)`

## 八、文本样式

### 颜色
- **统一颜色**：纯白色，85% 不透明度
  ```python
  fill_track = (255, 255, 255, 217)        # 曲目列表
  fill_title_full = (255, 255, 255, 217)  # 标题
  ```

### 文本渲染
- 使用 `ImageDraw.Draw(text_overlay)` 在透明图层上绘制文本
- 最后使用 `canvas.alpha_composite(text_overlay, (0, 0))` 叠加到主画布

## 九、条形码与ID

### 位置
- 位于封面右下角（具体位置见代码 1180-1220 行）

### 生成
- 使用 `python-barcode` 库生成 Code128 条形码
- 使用传入的 `id_str` 作为条形码内容
- 如果没有提供，生成简短ID：`YYMMDDHHmm`（10位）

## 十、关键设计原则总结

### 布局原则
1. **主图位置固定**：左上角 (1885, 282)，尺寸 1746×1599
2. **歌单区块固定**：左上角 (251, 225)，尺寸 1100×1400
3. **封脊位置固定**：X = 3295（4K 缩放后），宽度 90 像素
4. **标题位置**：
   - 右侧标题：主图正上方，水平居中
   - 封脊标题：垂直居中，旋转 -90 度

### 字体原则
1. **自适应字号**：歌单字体通过二分查找最大化，确保填满区块且不超宽
2. **字体比例**：Side A/B 标题 = 正文字体 × 1.5，主标题 = Side 标题 + 10px
3. **行间距**：`字体高度 + 字体大小 × 0.25`

### 视觉效果
1. **背景色**：使用主题色（从图片提取）
2. **噪点叠加**：添加做旧颗粒感（numpy 生成正态分布噪点）
3. **文本颜色**：纯白色，85% 不透明度

## 十一、McPOS 参考建议

### 需要借鉴的部分
1. **图片裁剪逻辑**：等比缩放 + 居中裁剪的算法
2. **字体自适应算法**：二分查找最大字号，确保内容填满区块
3. **布局参数**：主图、歌单区块、封脊的固定位置和尺寸
4. **封脊标题旋转**：-90 度旋转，垂直居中的实现
5. **噪点叠加**：做旧效果的实现（可选）

### 不需要借鉴的部分（McPOS 自己实现）
1. **标题生成**：使用 McPOS 的 AI 标题生成
2. **歌单内容**：使用 McPOS 的 playlist.csv
3. **背景色**：使用 McPOS 的 `extract_theme_color()` 提取的主题色

### 字体建议
- 优先使用 `assets/fonts/Lora-Regular.ttf`（如 Dev_Bible 中提到的）
- 如果没有，从 `assets/fonts/` 目录中选择可用字体
- 保持字体自适应逻辑，确保内容填满区块

