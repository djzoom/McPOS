#!/usr/bin/env python3
# coding: utf-8
"""
文档链接修复工具

功能：
1. 扫描所有Markdown文档
2. 检测并修复失效的内部链接和锚点
3. 更新过期模块引用
4. 统一文档命名规范

用法：
    python scripts/fix_doc_links.py          # 预览修复
    python scripts/fix_doc_links.py --fix   # 执行修复
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def extract_headers(md_file: Path) -> List[str]:
    """提取Markdown文件中的所有标题作为锚点"""
    headers = []
    try:
        with md_file.open("r", encoding="utf-8") as f:
            for line in f:
                # 匹配Markdown标题 (# 标题)
                match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
                if match:
                    level, title = match.groups()
                    # 生成锚点（小写、空格转连字符、移除特殊字符）
                    anchor = re.sub(r'[^\w\s-]', '', title.lower())
                    anchor = re.sub(r'[-\s]+', '-', anchor).strip('-')
                    headers.append((title, anchor))
    except Exception as e:
        print(f"⚠️  无法读取文件 {md_file}: {e}")
    return headers


def normalize_anchor(text: str) -> str:
    """标准化锚点文本"""
    # 移除中文括号中的内容（可选）
    text = re.sub(r'[（(].*?[）)]', '', text)
    # 转换为小写，移除特殊字符
    anchor = re.sub(r'[^\w\s-]', '', text.lower())
    anchor = re.sub(r'[-\s]+', '-', anchor).strip('-')
    return anchor


def find_all_doc_files() -> List[Path]:
    """查找所有Markdown文档"""
    docs_dir = REPO_ROOT / "docs"
    md_files = list(docs_dir.rglob("*.md"))
    # 也包含根目录的README
    readme = REPO_ROOT / "README.md"
    if readme.exists():
        md_files.append(readme)
    return md_files


def find_internal_links(content: str) -> List[Tuple[int, str, str]]:
    """查找所有内部链接 [text](./path) 和锚点 [text](#anchor)"""
    links = []
    
    # 匹配Markdown链接: [text](./path) 或 [text](#anchor)
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    
    for match in re.finditer(pattern, content):
        text = match.group(1)
        url = match.group(2)
        line_num = content[:match.start()].count('\n') + 1
        
        # 检查是否是内部链接
        if url.startswith('./') or url.startswith('../') or url.startswith('/'):
            links.append((line_num, text, url, 'file'))
        elif url.startswith('#'):
            links.append((line_num, text, url, 'anchor'))
    
    return links


def check_file_exists(target_path: str, source_file: Path) -> bool:
    """检查相对路径文件是否存在（使用安全路径验证）"""
    try:
        from src.core.path_utils import safe_join_path, validate_path_exists
        
        if target_path.startswith('/'):
            # 绝对路径（从repo根目录）
            base_path = REPO_ROOT.resolve()
            link_part = target_path.lstrip('/')
            full_path = safe_join_path(base_path, link_part)
        else:
            # 相对路径
            base_path = source_file.parent.resolve()
            full_path = safe_join_path(base_path, target_path)
        
        return validate_path_exists(full_path, must_exist=False).exists()
    except (ImportError, Exception):
        # 回退到原始方法（如果安全工具不可用）
        if target_path.startswith('/'):
            full_path = REPO_ROOT / target_path.lstrip('/')
        else:
            full_path = (source_file.parent / target_path).resolve()
        
        return full_path.exists()


def check_anchor_exists(anchor: str, target_file: Path) -> bool:
    """检查锚点是否存在于目标文件中"""
    headers = extract_headers(target_file)
    anchor_normalized = normalize_anchor(anchor.lstrip('#'))
    
    for _, header_anchor in headers:
        if header_anchor == anchor_normalized:
            return True
    
    return False


def fix_content(content: str, source_file: Path, all_headers: Dict[Path, List[Tuple[str, str]]]) -> Tuple[str, List[str]]:
    """修复内容中的链接和引用"""
    fixes = []
    new_content = content
    
    # 1. 修复过期模块引用
    replacements = {
        r'production_log\.json': 'schedule_master.json（新架构单一数据源）',
        r'production_log': 'state_manager（已迁移）',
        r'sync_resources\.py': 'unified_sync.py（已替代）',
        r'song_usage\.csv': 'schedule_master.json动态查询（已弃用独立文件）',
    }
    
    for pattern, replacement in replacements.items():
        if re.search(pattern, new_content):
            new_content = re.sub(pattern, replacement, new_content)
            fixes.append(f"替换过期引用: {pattern} → {replacement}")
    
    # 2. 修复失效的锚点链接
    def fix_anchor_link(match):
        text = match.group(1)
        anchor = match.group(2)
        
        # 如果是同一文件的锚点
        if anchor.startswith('#'):
            anchor_text = anchor.lstrip('#')
            normalized = normalize_anchor(anchor_text)
            
            # 在源文件中查找匹配的标题
            if source_file in all_headers:
                for title, header_anchor in all_headers[source_file]:
                    if header_anchor == normalized or normalize_anchor(title) == normalized:
                        # 找到匹配，返回正确格式
                        return f"[{text}](#{header_anchor})"
                # 未找到，尝试模糊匹配
                for title, header_anchor in all_headers[source_file]:
                    if anchor_text.lower() in title.lower() or title.lower() in anchor_text.lower():
                        fixes.append(f"修复锚点: #{anchor_text} → #{header_anchor}")
                        return f"[{text}](#{header_anchor})"
        
        return match.group(0)  # 未找到匹配，保持原样
    
    new_content = re.sub(r'\[([^\]]+)\]\(#([^)]+)\)', fix_anchor_link, new_content)
    
    # 3. 修复失效的文件链接
    def fix_file_link(match):
        text = match.group(1)
        path = match.group(2)
        
        if not check_file_exists(path, source_file):
            # 尝试查找相似文件
            docs_dir = REPO_ROOT / "docs"
            possible_files = list(docs_dir.glob(f"*{path.split('/')[-1]}"))
            if possible_files:
                rel_path = possible_files[0].relative_to(REPO_ROOT)
                new_path = f"./{rel_path}"
                fixes.append(f"修复文件链接: {path} → {new_path}")
                return f"[{text}]({new_path})"
        
        return match.group(0)
    
    new_content = re.sub(r'\[([^\]]+)\]\(([./][^)]+)\)', fix_file_link, new_content)
    
    return new_content, fixes


def main():
    parser = argparse.ArgumentParser(description="文档链接修复工具")
    parser.add_argument("--fix", action="store_true", help="执行修复（默认仅为预览）")
    parser.add_argument("--verbose", action="store_true", help="显示详细信息")
    
    args = parser.parse_args()
    
    print("🔍 扫描文档并分析链接...\n")
    
    doc_files = find_all_doc_files()
    print(f"📄 找到 {len(doc_files)} 个Markdown文档\n")
    
    # 提取所有文件的标题
    all_headers: Dict[Path, List[Tuple[str, str]]] = {}
    for doc_file in doc_files:
        headers = extract_headers(doc_file)
        all_headers[doc_file] = headers
    
    total_fixes = 0
    files_with_fixes = []
    
    for doc_file in doc_files:
        try:
            with doc_file.open("r", encoding="utf-8") as f:
                content = f.read()
            
            new_content, fixes = fix_content(content, doc_file, all_headers)
            
            if fixes or new_content != content:
                files_with_fixes.append((doc_file, fixes, new_content != content))
                total_fixes += len(fixes)
                
                if args.verbose or not args.fix:
                    print(f"📝 {doc_file.relative_to(REPO_ROOT)}")
                    for fix in fixes:
                        print(f"   ✅ {fix}")
                    if new_content != content:
                        print(f"   📝 内容已更新")
                    print()
                
                if args.fix and new_content != content:
                    # 备份原文件
                    backup = doc_file.with_suffix(doc_file.suffix + ".bak")
                    doc_file.rename(backup)
                    
                    # 写入修复后的内容
                    with doc_file.open("w", encoding="utf-8") as f:
                        f.write(new_content)
                    
                    # 删除备份（如果修复成功）
                    backup.unlink()
                    print(f"   💾 已保存修复")
        except (UnicodeDecodeError, PermissionError, OSError) as e:
            print(f"❌ 处理 {doc_file} 时出错: {type(e).__name__}: {e}")
        except Exception as e:
            print(f"❌ 处理 {doc_file} 时出错: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 70)
    print("📊 修复总结")
    print("=" * 70)
    print(f"扫描文档: {len(doc_files)} 个")
    print(f"需要修复: {len(files_with_fixes)} 个文件")
    print(f"修复项数: {total_fixes}")
    
    if not args.fix:
        print("\n💡 提示: 使用 --fix 参数执行实际修复")
    else:
        print("\n✅ 修复完成！")
    
    # 如果有修复但未使用--fix，返回非零退出码
    if files_with_fixes and not args.fix:
        sys.exit(1)


if __name__ == "__main__":
    main()

