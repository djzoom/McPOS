#!/usr/bin/env python3
"""
对比 songs/ 和 Suno 0127/ 目录中时长相等的文件
使用前10秒的音频哈希进行比对
"""
import subprocess
import hashlib
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

def compute_first_10_seconds_hash(file_path: Path) -> Optional[str]:
    """
    计算音频文件前10秒的MD5哈希
    
    使用 ffmpeg 提取前10秒的音频流（忽略元数据），然后计算MD5
    """
    try:
        # 使用 ffmpeg 提取前10秒的纯音频流并计算MD5
        # -t 10: 只提取前10秒
        # -map 0:a: 只提取音频流，忽略视频和元数据
        # -f md5: 输出MD5格式
        result = subprocess.run(
            ["ffmpeg", "-i", str(file_path),
             "-t", "10",  # 只提取前10秒
             "-map", "0:a",  # 只提取音频流
             "-f", "md5", "-"],  # 输出MD5
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # ffmpeg 输出的格式是: MD5=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
            output = result.stdout.strip()
            if output.startswith("MD5="):
                return output[4:].strip()
            # 如果没有 MD5= 前缀，尝试直接提取
            lines = output.split('\n')
            for line in lines:
                if '=' in line:
                    return line.split('=')[1].strip()
            return output.strip()
    except subprocess.TimeoutExpired:
        print(f"  超时: {file_path.name}")
    except Exception as e:
        print(f"  错误: {file_path.name} - {e}")
    return None

def format_duration(seconds: float) -> str:
    """格式化时长为 MM:SS 格式"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def scan_directory_by_duration(directory: Path) -> Dict[float, List[Path]]:
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

def compare_by_hash(songs_dir: Path, suno_dir: Path):
    """对比两个目录，使用前10秒哈希找出重复文件"""
    
    print("=" * 80)
    print("第一步: 扫描 songs/ 目录，按时长分组")
    print("=" * 80)
    songs_groups = scan_directory_by_duration(songs_dir)
    print(f"\nsongs/ 目录: 共 {sum(len(files) for files in songs_groups.values())} 个文件，{len(songs_groups)} 个不同时长")
    
    print("\n" + "=" * 80)
    print("第二步: 扫描 Suno 0127/ 目录，按时长分组")
    print("=" * 80)
    suno_groups = scan_directory_by_duration(suno_dir)
    print(f"\nSuno 0127/ 目录: 共 {sum(len(files) for files in suno_groups.values())} 个文件，{len(suno_groups)} 个不同时长")
    
    # 找出两个目录都有的时长
    common_durations = set(songs_groups.keys()) & set(suno_groups.keys())
    print(f"\n找到 {len(common_durations)} 个相同的时长值")
    
    # 按时长升序排序
    sorted_durations = sorted(common_durations)
    
    print("\n" + "=" * 80)
    print("第三步: 计算前10秒音频哈希并比对")
    print("=" * 80)
    
    duplicates = []  # [(songs_file, suno_file, duration, hash)]
    songs_hash_map = {}  # {hash: [file_paths]}
    suno_hash_map = {}  # {hash: [file_paths]}
    
    total_files_to_hash = 0
    for duration in sorted_durations:
        songs_files = songs_groups[duration]
        suno_files = suno_groups[duration]
        total_files_to_hash += len(songs_files) + len(suno_files)
    
    print(f"需要计算哈希的文件总数: {total_files_to_hash}")
    print()
    
    processed = 0
    for duration in sorted_durations:
        songs_files = songs_groups[duration]
        suno_files = suno_groups[duration]
        
        print(f"处理时长 {format_duration(duration)} ({duration:.1f}秒): songs={len(songs_files)}, suno={len(suno_files)}")
        
        # 计算 songs/ 目录中文件的前10秒哈希
        for file_path in songs_files:
            processed += 1
            if processed % 10 == 0:
                print(f"  进度: {processed}/{total_files_to_hash}")
            
            hash_val = compute_first_10_seconds_hash(file_path)
            if hash_val:
                if hash_val not in songs_hash_map:
                    songs_hash_map[hash_val] = []
                songs_hash_map[hash_val].append((file_path, duration))
        
        # 计算 Suno 0127/ 目录中文件的前10秒哈希
        for file_path in suno_files:
            processed += 1
            if processed % 10 == 0:
                print(f"  进度: {processed}/{total_files_to_hash}")
            
            hash_val = compute_first_10_seconds_hash(file_path)
            if hash_val:
                if hash_val not in suno_hash_map:
                    suno_hash_map[hash_val] = []
                suno_hash_map[hash_val].append((file_path, duration))
                
                # 检查是否与 songs/ 目录中的文件重复
                if hash_val in songs_hash_map:
                    for songs_file, songs_duration in songs_hash_map[hash_val]:
                        # 只记录时长相等的重复
                        if abs(songs_duration - duration) < 0.5:
                            duplicates.append((songs_file, file_path, duration, hash_val))
    
    print(f"\n完成！处理了 {processed} 个文件")
    
    # 生成报告
    print("\n" + "=" * 80)
    print("第四步: 生成重复文件报告")
    print("=" * 80)
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("前10秒音频哈希比对结果 - 重复文件列表")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append(f"找到 {len(duplicates)} 个重复文件对")
    report_lines.append("")
    
    # 按时长分组显示
    duplicates_by_duration = defaultdict(list)
    for songs_file, suno_file, duration, hash_val in duplicates:
        duplicates_by_duration[duration].append((songs_file, suno_file, hash_val))
    
    for duration in sorted(duplicates_by_duration.keys()):
        pairs = duplicates_by_duration[duration]
        report_lines.append(f"时长: {format_duration(duration)} ({duration:.1f}秒) - {len(pairs)} 个重复对")
        report_lines.append("")
        
        for songs_file, suno_file, hash_val in pairs:
            report_lines.append(f"  重复对 #{len([p for d, p_list in duplicates_by_duration.items() if d <= duration for p in p_list if p != (songs_file, suno_file, hash_val)]) + 1}")
            report_lines.append(f"    songs/ 目录: {songs_file.name}")
            report_lines.append(f"    Suno 0127/ 目录: {suno_file.name}")
            report_lines.append(f"    前10秒哈希: {hash_val}")
            report_lines.append("")
        
        report_lines.append("-" * 80)
        report_lines.append("")
    
    report_lines.append(f"总计: {len(duplicates)} 个重复文件对")
    
    # 输出报告
    report_text = "\n".join(report_lines)
    print(report_text)
    
    # 保存到文件
    report_file = songs_dir.parent / "first_10_seconds_comparison_report.txt"
    report_file.write_text(report_text, encoding='utf-8')
    print(f"\n报告已保存到: {report_file}")
    
    return duplicates

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
    
    duplicates = compare_by_hash(songs_dir, suno_dir)
    
    print(f"\n找到 {len(duplicates)} 个重复文件对")

if __name__ == "__main__":
    main()
