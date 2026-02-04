"""
封面生成

按照文档标准实现：使用 TEXT_BASE 标题和 playlist.csv 歌单生成封面。
生成 4K 封面 PNG (3840×2160)，参考旧世界布局设计。
"""

from pathlib import Path
from datetime import datetime
import json
import csv

from ..models import EpisodeSpec, AssetPaths, StageResult, StageName
from ..core.logging import log_info, log_error, log_warning
from ..adapters.color_extractor import extract_theme_color, rgb_to_hex
from ..config import get_config

# 布局参数（4K 画布：3840×2160）
CANVAS_WIDTH = 3840
CANVAS_HEIGHT = 2160

# 主图区域（固定位置）
MAIN_IMAGE_BOX_X = 1885
MAIN_IMAGE_BOX_Y = 282
MAIN_IMAGE_BOX_W = 1746
MAIN_IMAGE_BOX_H = 1599

# 歌单区块（固定位置）
TRACKLIST_BLOCK_X = 251
TRACKLIST_BLOCK_Y = 225
TRACKLIST_BLOCK_W = 1100
TRACKLIST_BLOCK_H = 1400

# 封脊位置（4K 画布，从8K坐标除以2得到）
SPINE_X_POS = 1648  # 封脊 X 位置（中心），原8K坐标3295，4K应为3295*0.5≈1648
SPINE_WIDTH_PX = 90  # 封脊宽度

# 文本样式
TEXT_COLOR = (255, 255, 255, 217)  # 纯白色，85% 不透明度
TEXT_OPACITY = 217  # Alpha 通道值

# 字体大小范围（4K 画布）
MIN_FONT_SIZE = 12
MAX_FONT_SIZE = 180


def _update_recipe_with_image(
    paths: AssetPaths,
    image_filename: str,
    theme_rgb: tuple[int, int, int] | None = None,
) -> None:
    """
    更新 recipe.json，记录使用的封面图片文件名和主题色
    
    Args:
        paths: AssetPaths 对象
        image_filename: 使用的图片文件名
        theme_rgb: 主题色 RGB 元组（可选）
    """
    recipe_path = paths.recipe_json
    
    if not recipe_path.exists():
        log_warning(f"recipe.json not found at {recipe_path}, cannot update cover_image_filename")
        return
    
    try:
        with recipe_path.open("r", encoding="utf-8") as f:
            recipe = json.load(f)
        
        recipe["cover_image_filename"] = image_filename
        
        # 如果提供了主题色，写入 assets 部分（供 TEXT_BASE 阶段复用）
        if theme_rgb:
            if "assets" not in recipe:
                recipe["assets"] = {}
            recipe["assets"]["theme_color_rgb"] = list(theme_rgb)
            log_info(f"Updated recipe.json with theme_color_rgb: {theme_rgb}")
        
        with recipe_path.open("w", encoding="utf-8") as f:
            json.dump(recipe, f, ensure_ascii=False, indent=2)
        
        log_info(f"Updated recipe.json with cover_image_filename: {image_filename}")
    except Exception as e:
        log_error(f"Failed to update recipe.json with cover_image_filename: {e}")


def _read_tracks_from_playlist(playlist_csv: Path) -> tuple[list[dict], list[dict]]:
    """
    从 playlist.csv 读取 Side A 和 Side B 的曲目列表
    
    Args:
        playlist_csv: playlist.csv 文件路径
    
    Returns:
        (side_a_tracks, side_b_tracks) - 每个 track 包含 "title" 字段
    """
    tracks_a = []
    tracks_b = []
    
    if not playlist_csv.exists():
        raise FileNotFoundError(f"playlist.csv not found at {playlist_csv}")
    
    with playlist_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            section = (row.get("Section") or "").strip()
            if section == "Track":
                title = (row.get("Title") or "").strip()
                side = (row.get("Side") or "").strip().upper()
                
                if title:
                    track_data = {"title": title}
                    
                    if side == "A":
                        tracks_a.append(track_data)
                    elif side == "B":
                        tracks_b.append(track_data)
    
    return tracks_a, tracks_b


def _crop_and_paste_image(
    canvas: "Image.Image",
    source_img: "Image.Image",
    box_x: int,
    box_y: int,
    box_w: int,
    box_h: int,
) -> None:
    """
    等比缩放 + 居中裁剪图片，然后粘贴到画布指定位置
    
    Args:
        canvas: 目标画布（RGBA）
        source_img: 源图片（RGBA）
        box_x, box_y: 目标区域左上角坐标
        box_w, box_h: 目标区域宽度和高度
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("PIL (Pillow) is required for cover generation. Install it with: pip install Pillow")
    
    img_ratio = source_img.width / source_img.height
    box_ratio = box_w / box_h
    
    if img_ratio > box_ratio:
        # 图片更扁，按高度拉伸，左右裁切
        img_scale = box_h / source_img.height
        new_w = int(source_img.width * img_scale)
        img_resized = source_img.resize((new_w, box_h), Image.Resampling.LANCZOS)
        left = (new_w - box_w) // 2
        img_cropped = img_resized.crop((left, 0, left + box_w, box_h))
    else:
        # 图片更高，按宽度拉伸，上下裁切
        img_scale = box_w / source_img.width
        new_h = int(source_img.height * img_scale)
        img_resized = source_img.resize((box_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - box_h) // 2
        img_cropped = img_resized.crop((0, top, box_w, top + box_h))
    
    # 使用 paste 并携带自身 alpha 作为蒙版，正确贴到指定位置
    canvas.paste(img_cropped, (box_x, box_y), img_cropped)


def _find_optimal_font_size(
    font_path: Path | None,
    tracks_a: list[dict],
    tracks_b: list[dict],
    block_w: int,
    block_h: int,
) -> tuple["ImageFont.FreeTypeFont", "ImageFont.FreeTypeFont"]:
    """
    二分查找最大字号，确保歌单内容填满区块且不超宽
    
    Args:
        font_path: 字体文件路径（如果为 None 则使用系统默认字体）
        tracks_a: Side A 曲目列表
        tracks_b: Side B 曲目列表
        block_w: 歌单区块宽度
        block_h: 歌单区块高度
    
    Returns:
        (body_font, side_title_font) - 正文字体和 Side A/B 标题字体
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ImportError("PIL (Pillow) is required for cover generation. Install it with: pip install Pillow")
    
    # 始终以 AB 各 12 首（24行）为基准，保证字体不会因曲目少而过大
    max_tracks_per_side = 12
    fake_side_a = tracks_a[:max_tracks_per_side] + [{"title": ""}] * max(0, max_tracks_per_side - len(tracks_a))
    fake_side_b = tracks_b[:max_tracks_per_side] + [{"title": ""}] * max(0, max_tracks_per_side - len(tracks_b))
    
    def wrap_track_lines(side_label: str, tracks: list[dict]) -> list[str]:
        """将曲目列表格式化为行文本"""
        lines = []
        for idx, track in enumerate(tracks, 1):
            if track.get("title"):
                lines.append(f"{idx:02d}. {track['title']}")
        return lines
    
    side_a_lines = wrap_track_lines("A", fake_side_a)
    side_b_lines = wrap_track_lines("B", fake_side_b)
    
    def measure_block(font_size: int) -> tuple[int, "ImageFont.FreeTypeFont", "ImageFont.FreeTypeFont", float]:
        """测量给定字号下的总高度和最大行宽度"""
        try:
            if font_path and font_path.exists():
                body_font = ImageFont.truetype(str(font_path), font_size)
                side_title_font = ImageFont.truetype(str(font_path), int(font_size * 1.5))
            else:
                body_font = ImageFont.load_default()
                side_title_font = ImageFont.load_default()
        except Exception:
            body_font = ImageFont.load_default()
            side_title_font = ImageFont.load_default()
        
        # 预估总高度（24行基准）
        h = 0
        h += int(side_title_font.size * 1.2)  # Side A 标题
        h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)  # 空行
        h += max_tracks_per_side * (body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25))
        h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)  # A-B 间空行
        h += int(side_title_font.size * 1.2)  # Side B 标题
        h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)  # 空行
        h += max_tracks_per_side * (body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25))
        
        # 计算最大行宽度
        max_line_w = 0.0
        for ln in side_a_lines + side_b_lines:
            w = body_font.getlength(ln)
            max_line_w = max(max_line_w, w)
        max_line_w = max(max_line_w, side_title_font.getlength("SIDE A"))
        max_line_w = max(max_line_w, side_title_font.getlength("SIDE B"))
        
        return h, body_font, side_title_font, max_line_w
    
    # 二分查找最大字号
    min_px, max_px = MIN_FONT_SIZE, MAX_FONT_SIZE
    best_px = min_px
    best_fonts = None
    
    while min_px <= max_px:
        mid = (min_px + max_px) // 2
        h, bf, stf, max_line_w = measure_block(mid)
        
        if h <= block_h and max_line_w <= block_w:
            best_px, best_fonts = mid, (bf, stf)
            min_px = mid + 1
        else:
            max_px = mid - 1
    
    if best_fonts is None:
        # Fallback：使用最小字号
        _, bf, stf, _ = measure_block(MIN_FONT_SIZE)
        best_fonts = (bf, stf)
    
    return best_fonts


def _draw_tracklist(
    draw: "ImageDraw.ImageDraw",
    tracks_a: list[dict],
    tracks_b: list[dict],
    block_x: int,
    block_y: int,
    block_w: int,
    block_h: int,
    body_font: "ImageFont.FreeTypeFont",
    side_title_font: "ImageFont.FreeTypeFont",
) -> None:
    """
    绘制 Side A/B 标题和曲目列表，垂直居中布局
    
    Args:
        draw: ImageDraw 对象
        tracks_a: Side A 曲目列表
        tracks_b: Side B 曲目列表
        block_x, block_y: 区块左上角坐标
        block_w, block_h: 区块宽度和高度
        body_font: 正文字体
        side_title_font: Side A/B 标题字体
    """
    def wrap_track_lines(side_label: str, tracks: list[dict]) -> list[str]:
        """将曲目列表格式化为行文本"""
        lines = []
        for idx, track in enumerate(tracks, 1):
            if track.get("title"):
                lines.append(f"{idx:02d}. {track['title']}")
        return lines
    
    side_a_lines = wrap_track_lines("A", tracks_a)
    side_b_lines = wrap_track_lines("B", tracks_b)
    
    # 计算实际内容总高度
    h = 0
    h += int(side_title_font.size * 1.2)  # Side A 标题
    h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)  # 空行
    h += len(side_a_lines) * (body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25))
    h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)  # A-B 间空行
    h += int(side_title_font.size * 1.2)  # Side B 标题
    h += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)  # 空行
    h += len(side_b_lines) * (body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25))
    
    # 垂直居中
    start_y = block_y + (block_h - h) // 2
    center_x = block_x + block_w // 2
    current_y = start_y
    
    # Side A 标题
    side_a_title = "SIDE A"
    side_a_title_w = draw.textlength(side_a_title, font=side_title_font)
    draw.text((center_x - side_a_title_w // 2, current_y), side_a_title, font=side_title_font, fill=TEXT_COLOR)
    current_y += int(side_title_font.size * 1.2)
    
    # 空行
    current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)
    
    # Side A 曲目
    for ln in side_a_lines:
        w = draw.textlength(ln, font=body_font)
        draw.text((center_x - w // 2, current_y), ln, font=body_font, fill=TEXT_COLOR)
        current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)
    
    # A-B 间空行
    current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)
    
    # Side B 标题
    side_b_title = "SIDE B"
    side_b_title_w = draw.textlength(side_b_title, font=side_title_font)
    draw.text((center_x - side_b_title_w // 2, current_y), side_b_title, font=side_title_font, fill=TEXT_COLOR)
    current_y += int(side_title_font.size * 1.2)
    
    # 空行
    current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)
    
    # Side B 曲目
    for ln in side_b_lines:
        w = draw.textlength(ln, font=body_font)
        draw.text((center_x - w // 2, current_y), ln, font=body_font, fill=TEXT_COLOR)
        current_y += body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1] + int(body_font.size * 0.25)


def _add_noise_overlay(canvas: "Image.Image") -> "Image.Image":
    """
    添加噪点叠加（做旧效果）
    
    Args:
        canvas: RGBA 画布
    
    Returns:
        叠加噪点后的画布
    """
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        log_warning("numpy not available, skipping noise overlay")
        return canvas
    
    width, height = canvas.size
    noise_strength = 18  # 噪点强度，建议10~30
    noise_alpha = 32     # 透明度，建议16~48
    
    noise = np.random.normal(128, noise_strength, (height, width)).clip(0, 255).astype(np.uint8)
    noise_img = Image.fromarray(noise, mode="L").convert("RGBA")
    # 设置alpha通道
    alpha = Image.new("L", (width, height), noise_alpha)
    noise_img.putalpha(alpha)
    # 叠加到主画布
    return Image.alpha_composite(canvas, noise_img)


def _load_font(font_path: Path | None, size: int) -> "ImageFont.FreeTypeFont":
    """
    加载字体文件
    
    Args:
        font_path: 字体文件路径（如果为 None 则使用系统默认字体）
        size: 字体大小
    
    Returns:
        ImageFont 对象
    """
    try:
        from PIL import ImageFont
    except ImportError:
        raise ImportError("PIL (Pillow) is required for cover generation. Install it with: pip install Pillow")
    
    if font_path and font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception as e:
            log_warning(f"Failed to load font from {font_path}: {e}, using default font")
    
    # Fallback：使用系统默认字体
    return ImageFont.load_default()


def _create_cover_image(
    source_image_path: Path,
    title: str,
    tracks_a: list[dict],
    tracks_b: list[dict],
    output_path: Path,
    theme_rgb: tuple[int, int, int] | None = None,
    font_path: Path | None = None,
) -> None:
    """
    创建封面图片（参考旧世界布局设计）
    
    Args:
        source_image_path: 源图片路径
        title: 封面标题
        tracks_a: Side A 曲目列表
        tracks_b: Side B 曲目列表
        output_path: 输出路径
        theme_rgb: 主题色 RGB 元组（可选，如果为 None 则使用黑色背景）
        font_path: 字体文件路径（可选，如果为 None 则从 assets/fonts/Lora-Regular.ttf 加载）
    
    Note:
        - 生成 4K 封面 (3840×2160)
        - 如果主题色提取失败，使用黑色背景作为 fallback
        - 使用 Lora-Regular.ttf 字体（如果可用）
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ImportError("PIL (Pillow) is required for cover generation. Install it with: pip install Pillow")
    
    # 画布尺寸：4K (3840×2160)
    width, height = CANVAS_WIDTH, CANVAS_HEIGHT
    
    # 背景色
    bg_color = theme_rgb if theme_rgb else (0, 0, 0)
    canvas = Image.new("RGBA", (width, height), bg_color + (255,))
    
    # 可选：添加噪点叠加（做旧效果）
    try:
        canvas = _add_noise_overlay(canvas)
    except Exception:
        pass  # 如果失败，继续使用无噪点的画布
    
    # 加载字体（优先使用 Lora-Regular.ttf）
    if font_path is None:
        config = get_config()
        default_font_path = config.fonts_dir / "Lora-Regular.ttf"
        if default_font_path.exists():
            font_path = default_font_path
            log_info(f"Using default font: {font_path}")
        else:
            log_warning(f"Default font not found at {default_font_path}, will use system font")
    
    # 主图裁剪与粘贴
    try:
        with Image.open(source_image_path) as source_img:
            source_img = source_img.convert("RGBA")
            _crop_and_paste_image(
                canvas,
                source_img,
                MAIN_IMAGE_BOX_X,
                MAIN_IMAGE_BOX_Y,
                MAIN_IMAGE_BOX_W,
                MAIN_IMAGE_BOX_H,
            )
    except Exception as e:
        log_warning(f"Failed to paste main image: {e}")
    
    # 字体自适应（二分查找最大字号）
    body_font, side_title_font = _find_optimal_font_size(
        font_path,
        tracks_a,
        tracks_b,
        TRACKLIST_BLOCK_W,
        TRACKLIST_BLOCK_H,
    )
    
    # 创建文本叠加层
    text_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_overlay)
    
    # 绘制歌单
    _draw_tracklist(
        text_draw,
        tracks_a,
        tracks_b,
        TRACKLIST_BLOCK_X,
        TRACKLIST_BLOCK_Y,
        TRACKLIST_BLOCK_W,
        TRACKLIST_BLOCK_H,
        body_font,
        side_title_font,
    )
    
    # 绘制标题
    # 右侧水平标题字体：比 Side 标题大 10px
    try:
        title_font_size = side_title_font.size + 10
        if font_path and font_path.exists():
            title_font = ImageFont.truetype(str(font_path), title_font_size)
        else:
            title_font = ImageFont.load_default()
    except Exception:
        title_font = ImageFont.load_default()
    
    # 封脊标题字体：自适应以适配封脊宽度
    min_spine_px = max(18, MIN_FONT_SIZE)
    max_spine_px = min(SPINE_WIDTH_PX, body_font.size)
    best_spine_px = min_spine_px
    
    for px in range(min_spine_px, max_spine_px + 1):
        try:
            if font_path and font_path.exists():
                test_font = ImageFont.truetype(str(font_path), px)
            else:
                test_font = ImageFont.load_default()
        except Exception:
            continue
        
        measure_img = Image.new("RGBA", (2000, 2000), (0, 0, 0, 0))
        measure_draw = ImageDraw.Draw(measure_img)
        bbox = measure_draw.textbbox((0, 0), title, font=test_font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        fits_vert = text_w <= int(height * 0.95)
        fits_width = text_h <= int(SPINE_WIDTH_PX * 0.95)
        
        if fits_vert and fits_width:
            best_spine_px = px
        else:
            break
    
    best_spine_px = max(1, best_spine_px - 1)
    try:
        if font_path and font_path.exists():
            spine_font = ImageFont.truetype(str(font_path), best_spine_px)
        else:
            spine_font = ImageFont.load_default()
    except Exception:
        spine_font = ImageFont.load_default()
    
    # 绘制右侧水平标题
    image_center_x = MAIN_IMAGE_BOX_X + MAIN_IMAGE_BOX_W // 2
    title_width = text_draw.textlength(title, font=title_font)
    title_x = image_center_x - int(title_width / 2)
    title_bbox = text_draw.textbbox((0, 0), title, font=title_font)
    title_height = title_bbox[3] - title_bbox[1]
    top_area_center = int((MAIN_IMAGE_BOX_Y - title_height) // 2)
    title_y = top_area_center
    text_draw.text((title_x, title_y), title, font=title_font, fill=TEXT_COLOR)
    
    # 先添加蒙版透明图层（TopCover_HD.png，从8K缩放到4K）
    # 注意：蒙版必须在文本层之前叠加，这样文本层才能显示在最上层
    config = get_config()
    overlay_path = config.design_dir / "TopCover_HD.png"
    if overlay_path.exists():
        try:
            with Image.open(overlay_path) as overlay_img:
                # 从8K (7680×4320) 缩放到4K (3840×2160)
                overlay_resized = overlay_img.resize((width, height), Image.Resampling.LANCZOS)
                overlay_resized = overlay_resized.convert("RGBA")
                # 使用 alpha_composite 叠加蒙版（保证透明度正确）
                canvas = Image.alpha_composite(canvas, overlay_resized)
                log_info(f"Applied mask overlay from {overlay_path}")
        except Exception as e:
            log_warning(f"Failed to apply mask overlay: {e}")
    else:
        log_warning(f"Mask overlay not found at {overlay_path}, skipping overlay")
    
    # 绘制封脊垂直标题（在蒙版之后，单独叠加以确保在最上层）
    measure_img = Image.new("RGBA", (2000, 2000), (0, 0, 0, 0))
    measure_draw = ImageDraw.Draw(measure_img)
    final_bbox = measure_draw.textbbox((0, 0), title, font=spine_font)
    text_w = final_bbox[2] - final_bbox[0]
    text_h = final_bbox[3] - final_bbox[1]
    pad_h = int(text_h * 0.3)
    spine_img = Image.new("RGBA", (text_w, text_h + pad_h), (0, 0, 0, 0))
    spine_draw = ImageDraw.Draw(spine_img)
    spine_draw.text((0, 0), title, font=spine_font, fill=TEXT_COLOR)
    spine_img = spine_img.rotate(-90, expand=True)
    paste_y = (height - spine_img.height) // 2
    # 封脊位置已修正：原8K坐标3295，4K应为1648（除以2）
    # 将封脊标题添加到文本层（与其他文本一起）
    text_overlay.paste(spine_img, (SPINE_X_POS - spine_img.width // 2, paste_y), spine_img)
    
    # 最后叠加文本层到主画布（确保所有文本都在最上层）
    canvas = Image.alpha_composite(canvas, text_overlay)
    
    # 单独叠加封脊垂直标题，确保它在所有图层的最上层（包括其他文本）
    spine_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    spine_overlay.paste(spine_img, (SPINE_X_POS - spine_img.width // 2, paste_y), spine_img)
    canvas = Image.alpha_composite(canvas, spine_overlay)
    
    # 转换为 RGB 并保存
    canvas_rgb = canvas.convert("RGB")
    canvas_rgb.save(output_path, "PNG", optimize=True)
    log_info(f"Cover image saved to {output_path} ({width}×{height})")


async def generate_cover_for_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult:
    """
    生成封面图片
    
    Interface Contract: async def generate_cover_for_episode(spec: EpisodeSpec, paths: AssetPaths) -> StageResult
    
    按照文档标准实现：
    - 使用 TEXT_BASE 标题和 playlist.csv 歌单生成封面
    - 生成 4K 封面 PNG (3840×2160)，参考旧世界布局设计
    - 从图片池选择图片，提取主题色作为背景
    - 支持从 recipe.json 读取已选图片（INIT 阶段已选图）
    
    输出文件：
    - paths.cover_png (<episode_id>_cover.png, 4K 3840×2160)
    
    依赖：
    - playlist.csv (必需, 来自 INIT 阶段)
    - paths.youtube_title_txt (可选, 来自 TEXT_BASE 阶段)
    """
    started_at = datetime.now()
    
    try:
        # 幂等性检查：如果封面已存在且尺寸正确，跳过生成
        if paths.cover_png.exists():
            try:
                from PIL import Image
                with Image.open(paths.cover_png) as img:
                    if img.size == (CANVAS_WIDTH, CANVAS_HEIGHT):
                        log_info(f"Cover already exists for {spec.episode_id}, skipping")
                        finished_at = datetime.now()
                        duration = (finished_at - started_at).total_seconds()
                        
                        return StageResult(
                            stage=StageName.COVER,
                            success=True,
                            duration_seconds=duration,
                            key_asset_paths=[paths.cover_png],
                            started_at=started_at,
                            finished_at=finished_at,
                        )
            except Exception:
                # 如果检查失败，重新生成
                pass
        
        # 确保输出目录存在
        paths.episode_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 读取 recipe.json，必须包含已选定的图片（INIT 阶段已选图）
        config = get_config()
        recipe_path = paths.recipe_json
        image_filename = None

        if not recipe_path.exists():
            raise FileNotFoundError(
                f"recipe.json not found at {recipe_path}. "
                "COVER 阶段必须有已选定图片，请先完成 INIT。"
            )

        try:
            with recipe_path.open("r", encoding="utf-8") as f:
                recipe = json.load(f)
            # 支持新格式（cover_image_filename）和老格式（image_filename）作为兼容
            image_filename = recipe.get("cover_image_filename") or recipe.get("image_filename")
        except Exception as e:
            raise RuntimeError(f"Failed to read recipe.json for cover selection: {e}") from e

        if not image_filename:
            raise ValueError(
                f"recipe.json missing cover_image_filename for {spec.episode_id}. "
                "缺图无法继续生成封面。"
            )

        # New workflow: cover image is copied into the episode folder during Plan stage.
        # Backward-compatible fallbacks: used pool, then available pool.
        episode_local_path = paths.episode_output_dir / image_filename
        used_pool_path = config.images_pool_root / "used" / image_filename
        available_pool_path = config.images_pool_root / "available" / image_filename

        if episode_local_path.exists():
            source_image = episode_local_path
            log_info(f"Using episode-local planned cover image: {image_filename}")
        elif used_pool_path.exists():
            source_image = used_pool_path
            log_info(f"Using cover image from used pool: {image_filename}")
        elif available_pool_path.exists():
            source_image = available_pool_path
            log_warning(f"Using cover image directly from available pool (expected episode-local copy): {image_filename}")
        else:
            raise FileNotFoundError(
                f"Cover image not found for {spec.episode_id}: {image_filename}. "
                f"Checked: {episode_local_path}, {used_pool_path}, {available_pool_path}."
            )
        
        # 读取专辑标题（优先从 recipe.json 读取，TEXT_BASE 阶段已写入）
        title = None
        if recipe_path.exists():
            try:
                with recipe_path.open("r", encoding="utf-8") as f:
                    recipe = json.load(f)
                title = recipe.get("album_title")
                if title:
                    log_info(f"Using album title from recipe.json: {title}")
            except Exception as e:
                log_warning(f"Failed to read album_title from recipe.json: {e}")
        
        # 如果 recipe.json 中没有 album_title，尝试从 YouTube 标题中提取
        if not title and paths.youtube_title_txt.exists():
            try:
                youtube_title = paths.youtube_title_txt.read_text(encoding="utf-8").strip()
                # 专辑标题通常是 "XXX LP |" 或 "XXX Vinyl |" 之前的部分
                if " LP |" in youtube_title:
                    title = youtube_title.split(" LP |")[0]
                elif " Vinyl |" in youtube_title:
                    title = youtube_title.split(" Vinyl |")[0]
                elif " | " in youtube_title:
                    title = youtube_title.split(" | ")[0]
                else:
                    title = youtube_title
                log_info(f"Extracted album title from YouTube title: {title}")
            except Exception as e:
                log_warning(f"Failed to extract album title from YouTube title: {e}")
        
        if not title:
            # Fallback：使用 channel_id 和 episode_id 组合
            title = f"{spec.channel_id} {spec.episode_id}"
            log_info(f"Using fallback title: {title}")
        
        # 从 playlist.csv 读取 Side A/B 曲目列表
        tracks_a, tracks_b = _read_tracks_from_playlist(paths.playlist_csv)
        log_info(f"Loaded {len(tracks_a)} tracks on Side A, {len(tracks_b)} tracks on Side B")
        
        # 提取主题色（带容错处理）
        theme_rgb = None
        theme_hex = None
        
        try:
            theme_rgb = extract_theme_color(source_image)
            if theme_rgb:
                theme_hex = rgb_to_hex(theme_rgb)
                log_info(f"Extracted theme color: #{theme_hex} (RGB: {theme_rgb})")
            else:
                log_warning("Theme color extractor returned None, fallback to black background")
        except Exception as e:
            log_warning(f"Failed to extract theme color: {e}, fallback to black background")
        
        # 获取字体路径（从配置读取，支持跨平台）
        font_path = None
        if hasattr(config, "cover_font_path") and config.cover_font_path:
            font_path = config.cover_font_path
            if not font_path.exists():
                log_warning(f"Configured cover font path not found: {font_path}, using default font")
                font_path = None
        
        # 生成封面
        log_info(f"Generating cover image: {paths.cover_png}")
        _create_cover_image(
            source_image_path=source_image,
            title=title,
            tracks_a=tracks_a,
            tracks_b=tracks_b,
            output_path=paths.cover_png,
            theme_rgb=theme_rgb,
            font_path=font_path,
        )
        
        # 更新 recipe.json，记录使用的图片文件名和主题色
        _update_recipe_with_image(paths, image_filename, theme_rgb=theme_rgb)
        
        # 验证文件是否存在且尺寸正确
        if not paths.cover_png.exists():
            raise FileNotFoundError(f"Cover image not generated: {paths.cover_png}")
        
        try:
            from PIL import Image
            with Image.open(paths.cover_png) as img:
                if img.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
                    log_warning(
                        f"Cover image size mismatch: expected {CANVAS_WIDTH}×{CANVAS_HEIGHT}, "
                        f"got {img.size[0]}×{img.size[1]}"
                    )
        except Exception as e:
            log_warning(f"Failed to verify cover image size: {e}")
        
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        log_info(f"✅ Cover generation complete for {spec.episode_id} (duration: {duration:.1f}s)")
        
        return StageResult(
            stage=StageName.COVER,
            success=True,
            duration_seconds=duration,
            key_asset_paths=[paths.cover_png],
            started_at=started_at,
            finished_at=finished_at,
        )
        
    except Exception as e:
        import traceback
        log_error(f"generate_cover_for_episode exception for {spec.episode_id}: {e}\n{traceback.format_exc()}")
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        return StageResult(
            stage=StageName.COVER,
            success=False,
            duration_seconds=duration,
            key_asset_paths=[],
            error_message=str(e),
            started_at=started_at,
            finished_at=finished_at,
        )
