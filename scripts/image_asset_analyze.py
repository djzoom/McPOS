import os
import re
from PIL import Image
from collections import Counter

def extract_image_description(filename):
    # 匹配文件名中的描述部分
    match = re.search(r'_(.*?)_[0-9a-fA-F\-]+_\d+\.png$', filename)
    if match:
        return match.group(1).replace('_', ' ')
    return None

def get_main_color(image_path, num_colors=5):
    with Image.open(image_path) as img:
        img = img.convert('RGB').resize((64, 64))
        pixels = list(img.getdata())
        most_common = Counter(pixels).most_common(num_colors)
        # 返回最常见的颜色
        return [color for color, _ in most_common]

def scan_image_assets(image_dir):
    results = []
    for fname in os.listdir(image_dir):
        if fname.lower().endswith('.png'):
            desc = extract_image_description(fname)
            path = os.path.join(image_dir, fname)
            main_colors = get_main_color(path)
            results.append({
                'filename': fname,
                'description': desc,
                'main_colors': main_colors
            })
    return results

if __name__ == '__main__':
    image_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../assets/design/images'))
    data = scan_image_assets(image_dir)
    for item in data:
        print(f"{item['filename']} | 描述: {item['description']} | 主色: {item['main_colors']}")
