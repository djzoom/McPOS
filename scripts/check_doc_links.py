#!/usr/bin/env python3
# coding: utf-8
"""
检查docs目录下所有Markdown文档的链接
识别过时链接和引用
"""
import re
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"

# 已归档的文档映射（旧路径 -> 新路径）
ARCHIVED_DOCS = {
    "state_refactor.md": "archive/state_refactor.md",
    "文档索引与阅读指南.md": "archive/文档索引与阅读指南.md",
    "开发日志总结.md": "archive/开发日志总结.md",
    "项目综述与未来计划.md": "archive/项目综述与未来计划.md",
    "开发建议-下一阶段.md": "archive/开发建议-下一阶段.md",
    "应用封装与打包完整指南.md": "archive/应用封装与打包完整指南.md",
    "如何添加应用程序图标.md": "archive/如何添加应用程序图标.md",
    "菜单结构图.md": "archive/菜单结构图.md",
    "新手教程-从零开始生成YouTube视频.md": "archive/新手教程-从零开始生成YouTube视频.md",
    "API完整指南.md": "archive/API完整指南.md",
    "YouTube上传MVP方案.md": "archive/YouTube上传MVP方案.md",
    "工具入口整合方案.md": "archive/工具入口整合方案.md",
    "KAT_REC工作流程.md": "archive/KAT_REC工作流程.md",
}

# 文档重命名映射（旧名 -> 新名）
RENAMED_DOCS = {
    "state_refactor.md": "ARCHITECTURE.md",
    "开发日志总结.md": "DEVELOPMENT.md",
    "项目综述与未来计划.md": "DEVELOPMENT.md",
    "开发建议-下一阶段.md": "ROADMAP.md",
    "improvement_roadmap.md": "ROADMAP.md",
    "system_health_report.md": "ROADMAP.md",
}

# Markdown链接模式
LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)', re.IGNORECASE)


def find_all_docs() -> List[Path]:
    """查找所有Markdown文档"""
    docs = []
    for md_file in DOCS_DIR.rglob("*.md"):
        # 跳过archive目录外的文档（但archive内的也要检查链接）
        docs.append(md_file)
    return sorted(docs)


def extract_links(content: str) -> List[Tuple[str, str, str]]:
    """提取所有Markdown链接"""
    links = []
    for match in LINK_PATTERN.finditer(content):
        link_text = match.group(1)
        link_path = match.group(2)
        links.append((match.group(0), link_text, link_path))
    return links


def check_link(link_path: str, current_file: Path) -> Tuple[bool, str]:
    """
    检查链接是否有效
    
    Returns:
        (is_valid, message)
    """
    # 处理相对路径
    if link_path.startswith("http"):
        return True, "External link"
    
    # 处理锚点
    if "#" in link_path:
        link_path = link_path.split("#")[0]
    
    # 构建完整路径（使用安全路径工具）
    try:
        from src.core.path_utils import safe_join_path
        
        if link_path.startswith("/"):
            # 绝对路径（从repo根目录）
            base_path = REPO_ROOT.resolve()
            link_part = link_path.lstrip("/")
            full_path = safe_join_path(base_path, link_part)
        elif link_path.startswith("./"):
            # 相对路径（当前目录）
            base_path = current_file.parent.resolve()
            link_part = link_path[2:]
            full_path = safe_join_path(base_path, link_part)
        else:
            # 相对路径
            base_path = current_file.parent.resolve()
            full_path = safe_join_path(base_path, link_path)
    except (ImportError, Exception):
        # 回退到原始方法（如果安全工具不可用）
        if link_path.startswith("/"):
            full_path = REPO_ROOT / link_path.lstrip("/")
        elif link_path.startswith("./"):
            full_path = current_file.parent / link_path[2:]
        else:
            full_path = current_file.parent / link_path
    
    # 检查文件是否存在
    if full_path.exists():
        return True, "Valid"
    
    # 检查是否在归档映射中
    link_filename = Path(link_path).name
    if link_filename in ARCHIVED_DOCS:
        return False, f"Link to archived doc: should be {ARCHIVED_DOCS[link_filename]}"
    
    # 检查是否已重命名
    if link_filename in RENAMED_DOCS:
        return False, f"Link to renamed doc: should be {RENAMED_DOCS[link_filename]}"
        
    return False, "File not found"


def check_document(file_path: Path) -> Dict:
    """检查单个文档"""
    content = file_path.read_text(encoding="utf-8")
    links = extract_links(content)
    
    issues = []
    for full_link, link_text, link_path in links:
        is_valid, message = check_link(link_path, file_path)
        if not is_valid:
            issues.append({
                "link": full_link,
                "text": link_text,
                "path": link_path,
                "message": message
                    })
    
    return {
        "file": file_path.relative_to(REPO_ROOT),
        "issues": issues,
        "total_links": len(links),
        "broken_links": len(issues)
    }


def main():
    """主函数"""
    print("🔍 Checking document links...")
    print("=" * 70)
    
    all_issues = []
    for doc_file in find_all_docs():
        if doc_file.relative_to(REPO_ROOT).parts[0] != "docs":
            continue
        
        result = check_document(doc_file)
        if result["issues"]:
            all_issues.append(result)
            print(f"\n📄 {result['file']}")
            print(f"   Total links: {result['total_links']}, Broken: {result['broken_links']}")
            for issue in result["issues"]:
                print(f"   ❌ {issue['link']}")
                print(f"      → {issue['message']}")
    
    print("\n" + "=" * 70)
    print(f"📊 Summary: {len(all_issues)} files with broken links")
    
    return all_issues


if __name__ == "__main__":
    issues = main()
