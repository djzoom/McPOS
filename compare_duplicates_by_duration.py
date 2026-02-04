#!/usr/bin/env python3
"""
对比 songs/ 和 Suno 0127/ 目录中时长相等的文件
按时长分组，按时长升序排序显示
"""
import subprocess
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

def get_audio_duration_seconds(file_path: Path) -> Optional[float]:
    """获取音频文件时长（秒）"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return None

def format_duration(seconds: float) -> str:
    """格式化时长为 MM:SS 格式"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def scan_directory(directory: Path) -> Dict[float, List[Path]]:
    """扫描目录，按时长分组"""
    duration_groups = defaultdict(list)
    
    print(f"扫描目录: {directory}")
    mp3_files = list(directory.glob("*.mp3"))
    print(f"找到 {len(mp3_files)} 个 MP3 文件")
    
    for i, file_path in enumerate(mp3_files, 1):
        if i % 50 == 0:
            print(f"  处理进度: {i}/{len(mp3_files)}")
        
        duration = get_audio_duration_seconds(file_path)
        if duration is not None:
            # 四舍五入到秒，避免浮点数精度问题
            duration_rounded = round(duration, 1)
            duration_groups[duration_rounded].append(file_path)
        else:
            print(f"  警告: 无法获取 {file_path.name} 的时长")
    
    return duration_groups

def main():
    repo_root = Path(__file__).parent
    library_dir = repo_root / "channels" / "kat" / "library"
    songs_dir = library_dir / "songs"
    suno_dir = library_dir / "Suno 0127"
    
    if not songs_dir.exists():
        print(f"错误: 目录不存在 {songs_dir}")
        return
    
    if not suno_dir.exists():
        print(f"错误: 目录不存在 {suno_dir}")
        return
    
    print("=" * 80)
    print("第一步: 扫描 songs/ 目录")
    print("=" * 80)
    songs_groups = scan_directory(songs_dir)
    print(f"\nsongs/ 目录: 共 {sum(len(files) for files in songs_groups.values())} 个文件，{len(songs_groups)} 个不同时长")
    
    print("\n" + "=" * 80)
    print("第二步: 扫描 Suno 0127/ 目录")
    print("=" * 80)
    suno_groups = scan_directory(suno_dir)
    print(f"\nSuno 0127/ 目录: 共 {sum(len(files) for files in suno_groups.values())} 个文件，{len(suno_groups)} 个不同时长")
    
    print("\n" + "=" * 80)
    print("第三步: 找出时长相等的文件对")
    print("=" * 80)
    
    # 找出两个目录都有的时长
    common_durations = set(songs_groups.keys()) & set(suno_groups.keys())
    print(f"\n找到 {len(common_durations)} 个相同的时长值")
    
    # 按时长升序排序
    sorted_durations = sorted(common_durations)
    
    # 生成报告
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("时长相等的文件对列表（按时长升序排序）")
    report_lines.append("=" * 80)
    report_lines.append("")
    
    total_pairs = 0
    for duration in sorted_durations:
        songs_files = songs_groups[duration]
        suno_files = suno_groups[duration]
        
        # 计算可能的文件对数量
        pairs_count = len(songs_files) * len(suno_files)
        total_pairs += pairs_count
        
        report_lines.append(f"时长: {format_duration(duration)} ({duration:.1f}秒)")
        report_lines.append(f"  songs/ 目录: {len(songs_files)} 个文件")
        report_lines.append(f"  Suno 0127/ 目录: {len(suno_files)} 个文件")
        report_lines.append(f"  可能的文件对数量: {pairs_count}")
        report_lines.append("")
        
        # 列出 songs/ 目录的文件
        report_lines.append("  songs/ 目录文件:")
        for file_path in sorted(songs_files):
            report_lines.append(f"    - {file_path.name}")
        report_lines.append("")
        
        # 列出 Suno 0127/ 目录的文件
        report_lines.append("  Suno 0127/ 目录文件:")
        for file_path in sorted(suno_files):
            report_lines.append(f"    - {file_path.name}")
        report_lines.append("")
        report_lines.append("-" * 80)
        report_lines.append("")
    
    report_lines.append(f"总计: {len(sorted_durations)} 个相同时长，{total_pairs} 个可能的文件对")
    
    # 输出报告
    report_text = "\n".join(report_lines)
    print(report_text)
    
    # 保存到文件
    report_file = library_dir / "duration_comparison_report.txt"
    report_file.write_text(report_text, encoding='utf-8')
    print(f"\n报告已保存到: {report_file}")

if __name__ == "__main__":
    main()
