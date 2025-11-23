"""
颜色提取适配器

基于旧世界的取色逻辑，使用 Pillow 提取图片主题色。
提供深浅多元的取色方案，确保背景色不要太深或太浅，适合显示白色文字。
"""

from pathlib import Path
import colorsys

from ..core.logging import log_info, log_warning

# 类型别名
RGB = tuple[int, int, int]


def extract_dominant_color(image_path: Path, quality: int = 150) -> RGB:
    """
    提取图片的主色调
    
    Args:
        image_path: 图片文件路径
        quality: 分析质量（图片缩放的尺寸，越小越快但精度越低）
    
    Returns:
        (r, g, b) 元组，表示主色调
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("PIL (Pillow) is required for color extraction. Install it with: pip install Pillow")
    
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found at {image_path}")
    
    with Image.open(image_path) as img:
        image = img.convert("RGB")
        image.thumbnail((quality, quality))
        # 获取所有颜色及其出现次数
        pixels = image.getcolors(image.width * image.height)
    if not pixels:
        log_warning(f"No pixels found in image {image_path}, using default gray")
        return (128, 128, 128)
    
    # 按出现次数排序
    sorted_pixels = sorted(pixels, key=lambda t: t[0], reverse=True)
    
    # 优先选择非灰度的颜色
    for count, color in sorted_pixels:
        r, g, b = color
        # 避免纯灰/白/黑
        if abs(r - g) > 15 or abs(g - b) > 15:
            return color
    
    # 如果都是灰度，返回最常见的颜色
    if sorted_pixels:
        return sorted_pixels[0][1]
    
    # 最后的回退
    return (128, 128, 128)


def extract_theme_color(image_path: Path, quality: int = 150, top_k: int = 12) -> RGB:
    """
    提取适合作为背景的主题色
    
    策略：
    - 从图片中提取多个候选颜色
    - 评分标准：饱和度 + 适中的亮度（不要太深也不要太浅）
    - 确保颜色适合显示白色文字（对比度足够）
    
    Args:
        image_path: 图片文件路径
        quality: 分析质量
        top_k: 考虑的前 k 个最常见颜色
    
    Returns:
        (r, g, b) 元组，表示主题色
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("PIL (Pillow) is required for color extraction. Install it with: pip install Pillow")
    
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found at {image_path}")
    
    with Image.open(image_path) as img:
        image = img.convert("RGB")
        image.thumbnail((quality, quality))
        pixels = image.getcolors(image.width * image.height)
    
    if not pixels:
        log_warning(f"No pixels found in image {image_path}, falling back to dominant color")
        return extract_dominant_color(image_path, quality)
    
    # 取前 top_k 个最常见的颜色
    top = sorted(pixels, key=lambda t: t[0], reverse=True)[:max(4, top_k)]
    
    def score_color(rgb: RGB) -> float:
        """评分函数：偏好适中的亮度和较高的饱和度"""
        r, g, b = [c / 255.0 for c in rgb]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        
        # 饱和度偏好
        sat_score = s
        
        # 亮度偏好：偏好 0.25-0.75 范围（不要太深也不要太浅）
        # 使用高斯型函数，峰值在 0.5
        brightness_center = 0.5
        brightness_spread = 0.25
        brightness_score = 1.0 - abs(v - brightness_center) / brightness_spread
        brightness_score = max(0.0, min(1.0, brightness_score))
        
        # 组合评分：饱和度权重 1.2，亮度权重 1.0
        total_score = 1.2 * sat_score + 1.0 * brightness_score
        
        # 对超出理想范围的颜色进行惩罚
        if v < 0.15:  # 太深
            total_score *= 0.3
        elif v > 0.85:  # 太浅
            total_score *= 0.4
        elif s < 0.2:  # 饱和度太低
            total_score *= 0.5
        
        return total_score
    
    # 过滤掉接近灰度的颜色
    candidates = []
    for _, rgb in top:
        r, g, b = rgb
        if abs(r - g) < 8 and abs(g - b) < 8:
            continue  # 跳过接近灰度的颜色
        candidates.append(rgb)
    
    if not candidates:
        candidates = [rgb for _, rgb in top]
    
    # 选择评分最高的颜色
    best = max(candidates, key=score_color)
    
    # 调整颜色以确保适合显示白色文字
    r, g, b = best
    rr, gg, bb = [c / 255.0 for c in (r, g, b)]
    h, s, v = colorsys.rgb_to_hsv(rr, gg, bb)
    
    # 如果太亮，稍微调暗（保持色调和饱和度）
    if v > 0.80:
        v = 0.70  # 调整到 70% 亮度
        rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
        best = (int(rr * 255), int(gg * 255), int(bb * 255))
    # 如果太暗，稍微调亮
    elif v < 0.20:
        v = 0.30  # 调整到 30% 亮度
        rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
        best = (int(rr * 255), int(gg * 255), int(bb * 255))
    
    return best


def rgb_to_hex(rgb: RGB) -> str:
    """将 RGB 元组转换为十六进制字符串"""
    return f"{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def hex_to_rgb(hex_str: str) -> RGB:
    """将十六进制字符串转换为 RGB 元组"""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        raise ValueError(f"Invalid hex color: {hex_str}")
    return (
        int(hex_str[0:2], 16),
        int(hex_str[2:4], 16),
        int(hex_str[4:6], 16),
    )

