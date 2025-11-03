import subprocess
import time
import argparse
from pathlib import Path

TRACKLIST = "data/google_sheet/Kat Record Lo-Fi Radio Songs Database - tracklist.tsv"
FONT_DIR = Path("assets/fonts")


def batch_generate(n=10, delay=1, font_mode=False):
    if font_mode:
        font_files = [f for f in FONT_DIR.iterdir() if f.suffix.lower() in {".ttf", ".otf"}]
        for font_path in font_files:
            font_name = font_path.stem
            print(f"生成字体 {font_name} ...")
            cmd = [
                "python", "scripts/local_picker/create_mixtape.py",
                "--tracklist", TRACKLIST,
                "--font_name", font_name
            ]
            subprocess.run(cmd)
            time.sleep(delay)
    else:
        cmd = [
            "python", "scripts/local_picker/create_mixtape.py",
            "--tracklist", TRACKLIST
        ]
        for i in range(n):
            print(f"生成第{i+1}期...")
            subprocess.run(cmd)
            time.sleep(delay)

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--font", action="store_true", help="遍历字体并标注字体名")
    args = parser.parse_args()

    if args.font:
        font_files = [f for f in FONT_DIR.iterdir() if f.suffix.lower() in {".ttf", ".otf"}]
        if not font_files:
            print("未找到任何字体文件。")
        else:
            # 先生成第一个字体
            first_font = font_files[0]
            font_name = first_font.stem
            print(f"生成字体 {font_name} ...")
            output_name = f"cover_{font_name}.png"
            cmd = [
                "python", "scripts/local_picker/create_mixtape.py",
                "--tracklist", TRACKLIST,
                "--font_name", font_name,
                "--show_font_name",
                "--output_name", output_name
            ]
            subprocess.run(cmd)
            # 询问用户是否继续
            resp = input(f"已生成 {output_name}，是否继续生成剩余 {len(font_files)-1} 个字体的封面？(y/n): ")
            if resp.strip().lower() == 'y':
                for font_path in font_files[1:]:
                    font_name = font_path.stem
                    print(f"生成字体 {font_name} ...")
                    output_name = f"cover_{font_name}.png"
                    cmd = [
                        "python", "scripts/local_picker/create_mixtape.py",
                        "--tracklist", TRACKLIST,
                        "--font_name", font_name,
                        "--show_font_name",
                        "--output_name", output_name
                    ]
                    subprocess.run(cmd)
                    time.sleep(1)
            else:
                print("已取消批量生成其余字体封面。")
    else:
        # 非字体批量模式，默认生成1个
        cmd = [
            "python", "scripts/local_picker/create_mixtape.py",
            "--tracklist", TRACKLIST
        ]
        print("生成一期封面...")
        subprocess.run(cmd)
