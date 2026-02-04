#!/usr/bin/env python3
"""
准备手动比对：重命名并移动疑似重复的歌曲到 Comparing 文件夹
"""
import re
import shutil
from pathlib import Path
from typing import List, Tuple

def parse_report(report_file: Path) -> List[Tuple[str, str, float]]:
    """
    解析报告文件，提取重复文件对
    
    Returns:
        List of (songs_filename, suno_filename, duration) tuples
    """
    duplicates = []
    
    with open(report_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    current_duration = 0.0
    current_songs_file = None
    current_suno_file = None
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 匹配时长行：时长: 01:28 (88.6秒)
        duration_match = re.match(r'时长: .+ \((\d+\.\d+)秒\)', line)
        if duration_match:
            current_duration = float(duration_match.group(1))
            i += 1
            continue
        
        # 匹配 songs/ 目录文件
        songs_match = re.match(r'songs/ 目录: (.+\.mp3)', line)
        if songs_match:
            current_songs_file = songs_match.group(1).strip()
            i += 1
            continue
        
        # 匹配 Suno 0127/ 目录文件
        suno_match = re.match(r'Suno 0127/ 目录: (.+\.mp3)', line)
        if suno_match:
            current_suno_file = suno_match.group(1).strip()
            # 如果已经收集到完整的一对，添加到列表
            if current_songs_file and current_suno_file:
                duplicates.append((current_songs_file, current_suno_file, current_duration))
                current_songs_file = None
                current_suno_file = None
            i += 1
            continue
        
        i += 1
    
    return duplicates

def prepare_comparison(duplicates: List[Tuple[str, str, float]], 
                       songs_dir: Path, 
                       suno_dir: Path, 
                       comparing_dir: Path,
                       dry_run: bool = False):
    """
    准备比对文件：
    1. 创建 Comparing 文件夹
    2. 复制 songs 中的文件（保持原文件名）
    3. 复制 Suno 0127 中的文件（重命名为 songs 文件名 + "-----2"）
    """
    if not dry_run:
        comparing_dir.mkdir(exist_ok=True)
        print(f"创建文件夹: {comparing_dir}")
    else:
        print(f"[DRY-RUN] 将创建文件夹: {comparing_dir}")
    
    log_lines = []
    log_lines.append("=" * 80)
    log_lines.append("手动比对准备 - 文件操作记录")
    log_lines.append("=" * 80)
    log_lines.append("")
    log_lines.append(f"总共 {len(duplicates)} 个重复对")
    log_lines.append("")
    
    success_count = 0
    error_count = 0
    
    for i, (songs_filename, suno_filename, duration) in enumerate(duplicates, 1):
        songs_file = songs_dir / songs_filename
        suno_file = suno_dir / suno_filename
        
        # 生成新文件名（去掉 .mp3，加上 -----2，再加回 .mp3）
        base_name = songs_filename[:-4]  # 去掉 .mp3
        new_suno_filename = f"{base_name}-----2.mp3"
        new_suno_file = comparing_dir / new_suno_filename
        
        log_lines.append(f"重复对 #{i} (时长: {duration:.1f}秒)")
        log_lines.append(f"  songs/ 原文件: {songs_filename}")
        log_lines.append(f"  Suno 0127/ 原文件: {suno_filename}")
        log_lines.append(f"  新文件名: {new_suno_filename}")
        log_lines.append("")
        
        # 检查源文件是否存在
        if not songs_file.exists():
            log_lines.append(f"  ❌ 错误: songs 文件不存在: {songs_file}")
            error_count += 1
            continue
        
        if not suno_file.exists():
            log_lines.append(f"  ❌ 错误: Suno 0127 文件不存在: {suno_file}")
            error_count += 1
            continue
        
        try:
            if not dry_run:
                # 复制 songs 文件（保持原文件名）
                shutil.copy2(songs_file, comparing_dir / songs_filename)
                log_lines.append(f"  ✓ 已复制: {songs_filename} -> {comparing_dir / songs_filename}")
                
                # 复制 Suno 0127 文件（重命名）
                shutil.copy2(suno_file, new_suno_file)
                log_lines.append(f"  ✓ 已复制并重命名: {suno_filename} -> {new_suno_filename}")
            else:
                log_lines.append(f"  [DRY-RUN] 将复制: {songs_filename} -> {comparing_dir / songs_filename}")
                log_lines.append(f"  [DRY-RUN] 将复制并重命名: {suno_filename} -> {new_suno_filename}")
            
            success_count += 1
        except Exception as e:
            log_lines.append(f"  ❌ 错误: {e}")
            error_count += 1
        
        log_lines.append("")
    
    log_lines.append("=" * 80)
    log_lines.append(f"完成: 成功 {success_count} 个，失败 {error_count} 个")
    log_lines.append("=" * 80)
    
    # 输出日志
    log_text = "\n".join(log_lines)
    print(log_text)
    
    # 保存日志
    log_file = comparing_dir.parent / "comparison_preparation_log.txt"
    log_file.write_text(log_text, encoding='utf-8')
    print(f"\n操作日志已保存到: {log_file}")
    
    return success_count, error_count

def main():
    import sys
    
    # 检查是否有 --execute 参数
    execute = '--execute' in sys.argv or '-e' in sys.argv
    
    repo_root = Path(__file__).parent
    library_dir = repo_root / "channels" / "kat" / "library"
    songs_dir = library_dir / "songs"
    suno_dir = library_dir / "Suno 0127"
    comparing_dir = library_dir / "Comparing"
    report_file = library_dir / "first_10_seconds_comparison_report.txt"
    
    if not report_file.exists():
        print(f"错误: 报告文件不存在 {report_file}")
        print("请先运行 compare_by_first_10_seconds.py 生成比对报告")
        return
    
    if not songs_dir.exists():
        print(f"错误: 目录不存在 {songs_dir}")
        return
    
    if not suno_dir.exists():
        print(f"错误: 目录不存在 {suno_dir}")
        return
    
    print("=" * 80)
    print("解析比对报告")
    print("=" * 80)
    duplicates = parse_report(report_file)
    print(f"找到 {len(duplicates)} 个重复对")
    
    print("\n" + "=" * 80)
    print("准备手动比对文件")
    print("=" * 80)
    print(f"目标文件夹: {comparing_dir}")
    print()
    
    if execute:
        print("【执行模式 - 将实际复制文件】")
        print()
        success, error = prepare_comparison(duplicates, songs_dir, suno_dir, comparing_dir, dry_run=False)
        print(f"\n完成！成功: {success}, 失败: {error}")
    else:
        # 先进行 dry-run
        print("【预览模式 - 不会实际复制文件】")
        print("使用 --execute 参数来实际执行文件操作")
        print()
        prepare_comparison(duplicates, songs_dir, suno_dir, comparing_dir, dry_run=True)
        
        print("\n" + "=" * 80)
        response = input("确认执行？(yes/no): ").strip().lower()
        print("=" * 80)
        
        if response == 'yes':
            print("\n开始执行文件操作...")
            success, error = prepare_comparison(duplicates, songs_dir, suno_dir, comparing_dir, dry_run=False)
            print(f"\n完成！成功: {success}, 失败: {error}")
        else:
            print("已取消操作")

if __name__ == "__main__":
    main()
