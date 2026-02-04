#!/usr/bin/env python3
"""
删除 Suno 0127 目录中所有已确认重复的文件
只保留独特的（不重复的）文件
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

def remove_duplicates(duplicates: List[Tuple[str, str, float]], 
                     suno_dir: Path,
                     dry_run: bool = False):
    """
    删除 Suno 0127 目录中所有重复的文件
    
    Args:
        duplicates: 重复文件对列表
        suno_dir: Suno 0127 目录路径
        dry_run: 如果为 True，只显示将要删除的文件，不实际删除
    """
    # 获取所有要删除的文件名
    duplicate_suno_files = {suno_filename for _, suno_filename, _ in duplicates}
    
    print("=" * 80)
    print("删除 Suno 0127 目录中的重复文件")
    print("=" * 80)
    print(f"找到 {len(duplicate_suno_files)} 个重复文件需要删除")
    print()
    
    # 获取 Suno 0127 目录中的所有文件
    all_suno_files = list(suno_dir.glob("*.mp3"))
    print(f"Suno 0127 目录中总共有 {len(all_suno_files)} 个文件")
    
    # 找出要删除的文件和要保留的文件
    files_to_delete = []
    files_to_keep = []
    
    for file_path in all_suno_files:
        if file_path.name in duplicate_suno_files:
            files_to_delete.append(file_path)
        else:
            files_to_keep.append(file_path)
    
    print(f"将删除: {len(files_to_delete)} 个文件")
    print(f"将保留: {len(files_to_keep)} 个文件")
    print()
    
    log_lines = []
    log_lines.append("=" * 80)
    log_lines.append("删除 Suno 0127 目录中重复文件的操作记录")
    log_lines.append("=" * 80)
    log_lines.append("")
    log_lines.append(f"总共 {len(all_suno_files)} 个文件")
    log_lines.append(f"删除 {len(files_to_delete)} 个重复文件")
    log_lines.append(f"保留 {len(files_to_keep)} 个独特文件")
    log_lines.append("")
    log_lines.append("=" * 80)
    log_lines.append("删除的文件列表")
    log_lines.append("=" * 80)
    log_lines.append("")
    
    deleted_count = 0
    error_count = 0
    
    # 删除重复文件
    for i, file_path in enumerate(sorted(files_to_delete), 1):
        try:
            if not dry_run:
                file_path.unlink()
                log_lines.append(f"{i}. ✓ 已删除: {file_path.name}")
                deleted_count += 1
            else:
                log_lines.append(f"{i}. [DRY-RUN] 将删除: {file_path.name}")
                deleted_count += 1
        except Exception as e:
            log_lines.append(f"{i}. ❌ 错误: {file_path.name} - {e}")
            error_count += 1
    
    log_lines.append("")
    log_lines.append("=" * 80)
    log_lines.append("保留的独特文件列表")
    log_lines.append("=" * 80)
    log_lines.append("")
    
    # 列出保留的文件
    for i, file_path in enumerate(sorted(files_to_keep), 1):
        log_lines.append(f"{i}. {file_path.name}")
    
    log_lines.append("")
    log_lines.append("=" * 80)
    log_lines.append(f"完成: 删除 {deleted_count} 个，保留 {len(files_to_keep)} 个，错误 {error_count} 个")
    log_lines.append("=" * 80)
    
    # 输出日志
    log_text = "\n".join(log_lines)
    print(log_text)
    
    # 保存日志
    log_file = suno_dir.parent / "remove_duplicates_log.txt"
    log_file.write_text(log_text, encoding='utf-8')
    print(f"\n操作日志已保存到: {log_file}")
    
    return deleted_count, len(files_to_keep), error_count

def main():
    import sys
    
    # 检查是否有 --execute 参数
    execute = '--execute' in sys.argv or '-e' in sys.argv
    
    repo_root = Path(__file__).parent
    library_dir = repo_root / "channels" / "kat" / "library"
    suno_dir = library_dir / "Suno 0127"
    report_file = library_dir / "first_10_seconds_comparison_report.txt"
    
    if not report_file.exists():
        print(f"错误: 报告文件不存在 {report_file}")
        print("请先运行 compare_by_first_10_seconds.py 生成比对报告")
        return
    
    if not suno_dir.exists():
        print(f"错误: 目录不存在 {suno_dir}")
        return
    
    print("=" * 80)
    print("解析比对报告")
    print("=" * 80)
    duplicates = parse_report(report_file)
    print(f"找到 {len(duplicates)} 个重复对")
    print()
    
    if execute:
        print("【执行模式 - 将实际删除文件】")
        print()
        deleted, kept, errors = remove_duplicates(duplicates, suno_dir, dry_run=False)
        print(f"\n完成！删除: {deleted}, 保留: {kept}, 错误: {errors}")
    else:
        print("【预览模式 - 不会实际删除文件】")
        print("使用 --execute 参数来实际执行删除操作")
        print()
        remove_duplicates(duplicates, suno_dir, dry_run=True)
        
        print("\n" + "=" * 80)
        response = input("确认执行删除操作？(yes/no): ").strip().lower()
        print("=" * 80)
        
        if response == 'yes':
            print("\n开始执行删除操作...")
            deleted, kept, errors = remove_duplicates(duplicates, suno_dir, dry_run=False)
            print(f"\n完成！删除: {deleted}, 保留: {kept}, 错误: {errors}")
        else:
            print("已取消操作")

if __name__ == "__main__":
    main()
