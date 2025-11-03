#!/usr/bin/env python3
# coding: utf-8
"""
KAT Records Studio 帮助系统

功能：
1. 显示完整的命令辞典
2. 显示快速参考
3. 显示文档索引
4. 按类别搜索命令
5. 显示命令详细说明

用法：
    python scripts/show_help.py
    python scripts/show_help.py --quick
    python scripts/show_help.py --category 排播
    python scripts/show_help.py --command make schedule
    make help
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_markdown_content(file_path: Path) -> str:
    """加载Markdown文件内容"""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def show_main_help():
    """显示主帮助信息"""
    print("=" * 70)
    print("🎵 KAT Records Studio - 命令帮助系统")
    print("=" * 70)
    print()
    print("📚 帮助命令：")
    print("  make help              - 显示此帮助")
    print("  make help --quick      - 快速参考")
    print("  make help --category 排播 - 按类别查看")
    print("  make help --command 'make schedule' - 查看命令详情")
    print()
    print("📖 文档命令：")
    print("  make docs              - 列出所有文档")
    print("  make docs-api          - API使用指南")
    print("  make docs-security     - API安全指南")
    print()
    print("🔧 常用命令：")
    print()
    print("  工作流：")
    print("    make build-video              - 生成完整视频")
    print("    make cover                    - 仅生成封面")
    print("    make cover N=10               - 批量生成封面")
    print()
    print("  排播系统：")
    print("    make schedule EPISODES=15      - 创建排播表")
    print("    make show-schedule            - 查看排播表")
    print("    make video-id ID=20251101     - 按ID生成单期")
    print("    make 4kvideo N=10             - 批量生成")
    print()
    print("  环境测试：")
    print("    make init                     - 初始化环境")
    print("    make bench                    - 基准测试")
    print("    make check-api                - 检查API状态")
    print()
    print("  其他：")
    print("    make test                     - 运行测试")
    print()
    print("=" * 70)
    print("💡 提示：使用 'make help --category <类别>' 查看详细分类")
    print("   或查看文档: docs/COMMAND_REFERENCE.md")
    print("=" * 70)


def show_quick_reference():
    """显示快速参考"""
    print("=" * 70)
    print("⚡ KAT Records - 快速参考")
    print("=" * 70)
    print()
    
    categories = {
        "生成视频": [
            ("make build-video", "生成完整视频（封面+歌单+混音+视频）"),
            ("make cover", "仅生成封面和歌单"),
            ("make cover N=10", "批量生成10个封面"),
        ],
        "排播系统": [
            ("make schedule EPISODES=15", "创建15期排播表"),
            ("make show-schedule", "查看排播表状态"),
            ("make video-id ID=20251101", "生成指定期数"),
            ("make 4kvideo N=10", "批量生成10期"),
            ("make watch-schedule", "监视排播表状态"),
        ],
        "环境管理": [
            ("make init", "初始化环境（测试编码器）"),
            ("make init-check", "检查环境状态"),
            ("make bench IMAGE=xxx AUDIO=xxx", "基准测试"),
            ("make check-api", "检查API配置"),
            ("make test-api", "测试API连接"),
        ],
        "排播表管理": [
            ("rm config/schedule_master.json", "删除排播表"),
            ("make schedule EPISODES=15 START_DATE=2025-11-01", "创建新排播表"),
            ("python scripts/local_picker/generate_full_schedule.py", "生成完整排播（标题+曲目）"),
        ],
    }
    
    for category, commands in categories.items():
        print(f"📋 {category}:")
        for cmd, desc in commands:
            print(f"   {cmd:<45} {desc}")
        print()
    
    print("=" * 70)


def show_category(category: str):
    """按类别显示命令"""
    category_lower = category.lower()
    
    # 读取命令参考文档
    cmd_ref_path = REPO_ROOT / "COMMAND_REFERENCE.md"
    quick_ref_path = REPO_ROOT / "COMMAND_QUICK_REF.md"
    
    if not cmd_ref_path.exists() and not quick_ref_path.exists():
        print(f"❌ 未找到命令参考文档")
        return
    
    content = ""
    if cmd_ref_path.exists():
        content += load_markdown_content(cmd_ref_path)
    if quick_ref_path.exists():
        content += "\n\n" + load_markdown_content(quick_ref_path)
    
    # 搜索相关章节
    lines = content.split("\n")
    in_section = False
    section_lines = []
    
    for line in lines:
        # 检查是否是相关章节
        if line.startswith("#") and category_lower in line.lower():
            in_section = True
            section_lines = [line]
            continue
        
        if in_section:
            if line.startswith("#") and not line.startswith("##"):
                # 遇到新的顶级标题，结束当前章节
                break
            section_lines.append(line)
    
    if section_lines:
        print("=" * 70)
        print(f"📚 {category} - 相关命令")
        print("=" * 70)
        print()
        print("\n".join(section_lines))
    else:
        print(f"❌ 未找到类别 '{category}' 的相关信息")
        print(f"💡 可用类别: 排播, 生成, 环境, API, 测试")


def show_command_detail(command: str):
    """显示命令详细信息"""
    # 移除 'make' 前缀
    if command.startswith("make "):
        command = command[5:]
    
    # 读取命令参考
    cmd_ref_path = REPO_ROOT / "COMMAND_REFERENCE.md"
    if not cmd_ref_path.exists():
        print(f"❌ 未找到命令参考文档")
        return
    
    content = load_markdown_content(cmd_ref_path)
    lines = content.split("\n")
    
    # 搜索命令
    found = False
    in_section = False
    section_lines = []
    
    for i, line in enumerate(lines):
        # 检查是否包含命令
        if command.lower() in line.lower():
            # 找到命令所在章节
            # 向上查找章节标题
            for j in range(i, max(0, i-20), -1):
                if lines[j].startswith("#"):
                    section_lines.append(lines[j])
                    break
            
            # 向下收集命令相关内容（最多50行）
            for j in range(i, min(len(lines), i+50)):
                if j != i and lines[j].startswith("#") and not lines[j].startswith("##"):
                    break
                section_lines.append(lines[j])
            
            found = True
            break
    
    if found and section_lines:
        print("=" * 70)
        print(f"📖 命令详情: {command}")
        print("=" * 70)
        print()
        print("\n".join(section_lines))
    else:
        print(f"❌ 未找到命令 '{command}' 的详细信息")
        print(f"💡 使用 'make help' 查看所有可用命令")


def show_docs_index():
    """显示文档索引"""
    docs_dir = REPO_ROOT / "docs"
    
    print("=" * 70)
    print("📚 KAT Records Studio - 文档索引")
    print("=" * 70)
    print()
    
    if not docs_dir.exists():
        print("❌ docs 目录不存在")
        return
    
    # 主要文档
    main_docs = {
        "命令参考": [
            "COMMAND_REFERENCE.md",
            "COMMAND_QUICK_REF.md",
        ],
        "API相关": [
            "API完整指南.md",
        ],
        "排播系统": [
            "SCHEDULE_MASTER_GUIDE.md",
            "COMMAND_LINE_WORKFLOW.md",
        ],
        "其他": [
            "LIBRARY_MANAGEMENT.md",
            "PACKAGING_GUIDE.md",
        ],
    }
    
    for category, files in main_docs.items():
        print(f"📋 {category}:")
        for filename in files:
            doc_path = REPO_ROOT / filename if not filename.startswith("docs/") else REPO_ROOT / filename
            if not doc_path.exists():
                doc_path = docs_dir / filename
            if doc_path.exists():
                print(f"   • {filename}")
            else:
                print(f"   • {filename} (未找到)")
        print()
    
    # 列出docs目录中的所有Markdown文件
    if docs_dir.exists():
        all_docs = sorted(docs_dir.glob("*.md"))
        if all_docs:
            print("📁 docs/ 目录中的其他文档：")
            for doc_path in all_docs:
                print(f"   • docs/{doc_path.name}")
    
    print()
    print("=" * 70)
    print("💡 提示：使用 'cat docs/<文件名>' 或 'less docs/<文件名>' 查看文档")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="KAT Records Studio 帮助系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  make help                    # 显示主帮助
  make help --quick            # 快速参考
  make help --category 排播     # 查看排播相关命令
  make help --command 'make schedule'  # 查看命令详情
  make help --docs             # 显示文档索引
        """
    )
    
    parser.add_argument(
        "--quick",
        action="store_true",
        help="显示快速参考"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="按类别查看命令（如：排播、生成、环境）"
    )
    parser.add_argument(
        "--command",
        type=str,
        help="查看命令详细说明（如：'make schedule'）"
    )
    parser.add_argument(
        "--docs",
        action="store_true",
        help="显示文档索引"
    )
    
    args = parser.parse_args()
    
    if args.quick:
        show_quick_reference()
    elif args.category:
        show_category(args.category)
    elif args.command:
        show_command_detail(args.command)
    elif args.docs:
        show_docs_index()
    else:
        show_main_help()


if __name__ == "__main__":
    main()


