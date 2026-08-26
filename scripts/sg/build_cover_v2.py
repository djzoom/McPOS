#!/usr/bin/env python3
"""SG 封面 v2c：文字区按逐列垂直插值重建天空，偏差像素全部回填。"""
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SESS = Path("/Users/z/Studio/Workspace/outputs/sg/sessions")
DBG = Path("/private/tmp/claude-501/-Users-z-Projects/778af98c-f729-4397-a575-8a88eba29052/scratchpad/sg_debug")
FONT = "/Library/Fonts/AGaramondPro-Regular.otf"

RX0, RX1, RY0, RY1 = 650, 1245, 262, 418      # 旧标题 ROI
A_TOP = (238, 260)                             # 上锚行区间
A_BOT = (420, 442)                             # 下锚行区间

JOBS = [
    ("sg_mol_v3_deut31", "sg_gold_003", "He will never|leave you", "DEUTERONOMY 31:6"),
    ("sg_mol_v3_john14", "sg_gold_008", "Peace the world|cannot give", "JOHN 14:27"),
    ("sg_mol_v3_ps121a", "sg_gold_002", "Your keeper|never sleeps", "PSALM 121"),
    ("sg_mol_v3_phil4",  "sg_gold_004", "Anxious|for nothing", "PHILIPPIANS 4:6-7"),
    ("sg_mol_v3_ps16",   "sg_gold_007", "At His right hand|unshaken", "PSALM 16:8"),
    ("sg_mol_v3_john10", "sg_gold_005", "No one can|snatch you away", "JOHN 10:28"),
    ("sg_mol_v3_isa26",  "sg_gold_006", "Kept in|perfect peace", "ISAIAH 26:3"),
    ("sg_mol_v3_ps121b", "sg_gold_001", "He will not|let you fall", "PSALM 121:4"),
    ("sg_mol_v3_ps4a",   "sg_gold_002", "In peace|I lie down", "PSALM 4:8"),
]


def erase(bgr):
    img = bgr.astype(np.float32)
    top = np.median(img[A_TOP[0]:A_TOP[1], RX0:RX1], axis=0)   # (W,3) 每列上锚
    bot = np.median(img[A_BOT[0]:A_BOT[1], RX0:RX1], axis=0)
    # 列向平滑，去掉锚行里的星点
    top = cv2.blur(top.reshape(1, -1, 3), (1, 31)).reshape(-1, 3)
    bot = cv2.blur(bot.reshape(1, -1, 3), (1, 31)).reshape(-1, 3)
    h = RY1 - RY0
    t = (np.arange(h, dtype=np.float32) / (h - 1)).reshape(-1, 1, 1)
    model = top[None, :, :] * (1 - t) + bot[None, :, :] * t     # (h,W,3)
    roi = img[RY0:RY1, RX0:RX1]
    dev = np.abs(roi - model).sum(axis=2)
    dev = cv2.GaussianBlur(dev, (0, 0), 2)
    dev = cv2.dilate(dev, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    # 连续混合：dev 18→55 线性升到 1（smoothstep），软晕也被吃掉
    a = np.clip((dev - 18.0) / (55.0 - 18.0), 0, 1)
    a = a * a * (3 - 2 * a)
    noise = np.random.default_rng(7).normal(0, 2.0, model.shape).astype(np.float32)
    fill = np.clip(model + noise, 0, 255)
    m = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 3)[..., None]
    m = np.clip(m, 0, 1)
    out = img.copy()
    out[RY0:RY1, RX0:RX1] = roi * (1 - m) + fill * m
    return out.astype(np.uint8)


def draw_text(img, phrase, ref):
    W, H = img.size
    cx, max_w = 950, 560
    lines = phrase.split("|")
    size = 108
    while size > 56:
        f = ImageFont.truetype(FONT, size)
        if max(f.getbbox(t)[2] - f.getbbox(t)[0] for t in lines) <= max_w:
            break
        size -= 4
    f = ImageFont.truetype(FONT, size)
    fs = ImageFont.truetype(FONT, 40)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    line_h = int(size * 1.06)
    block_h = line_h * len(lines)
    sub_gap, sub_h = 36, 40
    y0 = 340 - (block_h + sub_gap + sub_h) // 2
    for i, t in enumerate(lines):
        bb = f.getbbox(t)
        d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], y0 + i * line_h), t,
               font=f, fill=(240, 205, 152, 255))
    tracked = " ".join(ref)
    bb = fs.getbbox(tracked)
    d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], y0 + block_h + sub_gap), tracked,
           font=fs, fill=(217, 179, 132, 235))
    glow = layer.filter(ImageFilter.GaussianBlur(12))
    tint = Image.new("RGBA", (W, H), (199, 126, 58, 0))
    tint.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.55)))
    out = Image.alpha_composite(img.convert("RGBA"), tint)
    return Image.alpha_composite(out, layer).convert("RGB")


for ep, bg, phrase, ref in JOBS:
    bgr = cv2.imread(str(SESS / bg / f"{bg}_cover.jpg"))
    assert bgr is not None
    img = draw_text(Image.fromarray(cv2.cvtColor(erase(bgr), cv2.COLOR_BGR2RGB)), phrase, ref)
    dst = SESS / ep / f"{ep}_cover_v2.jpg"
    img.save(dst, quality=90)
    print(f"✅ {ep}  {dst.stat().st_size//1024}K")

thumbs = [Image.open(SESS / ep / f"{ep}_cover_v2.jpg").resize((426, 240)) for ep, *_ in JOBS]
sheet = Image.new("RGB", (426 * 3 + 16, 240 * 3 + 16), (16, 16, 20))
for i, t in enumerate(thumbs):
    sheet.paste(t, ((i % 3) * 434, (i // 3) * 248))
sheet.save(DBG / "contact_sheet_v2c.jpg", quality=88)
print("sheet ok")
