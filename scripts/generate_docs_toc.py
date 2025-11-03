#!/usr/bin/env python3
"""Generate docs/DOCS_TOC.md from all markdown files in docs/"""
import os
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent
DOCS_DIR = REPO_ROOT / "docs"

def get_doc_status(file_path: Path) -> str:
    """Determine doc status from content"""
    try:
        content = file_path.read_text(encoding='utf-8')
        if "DEPRECATED" in content.upper() or "废弃" in content:
            return "deprecated"
        if "# WIP" in content or "# TODO" in content or "DRAFT" in content.upper():
            return "draft"
        return "active"
    except:
        return "unknown"

def get_last_modified(file_path: Path) -> str:
    """Get last modified time"""
    try:
        mtime = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except:
        return "unknown"

def extract_title(content: str, file_path: Path) -> str:
    """Extract title from markdown"""
    lines = content.split('\n')
    for line in lines[:10]:
        if line.startswith('# '):
            return line[2:].strip()
        if line.startswith('## '):
            return line[3:].strip()
    return file_path.stem

def generate_toc():
    """Generate table of contents"""
    toc_lines = [
        "# Documentation Table of Contents",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        "| Title | Path | Last Modified | Status |",
        "|-------|------|--------------|--------|"
    ]
    
    # Main docs
    main_docs = []
    archive_docs = []
    
    for md_file in sorted(DOCS_DIR.rglob("*.md")):
        rel_path = md_file.relative_to(DOCS_DIR)
        
        try:
            content = md_file.read_text(encoding='utf-8')
            title = extract_title(content, md_file)
            last_mod = get_last_modified(md_file)
            status = get_doc_status(md_file)
            
            row = f"| {title} | `{rel_path}` | {last_mod} | {status} |"
            
            if "archive" in str(rel_path):
                archive_docs.append((str(rel_path), row))
            else:
                main_docs.append((str(rel_path), row))
        except Exception as e:
            print(f"Error processing {md_file}: {e}", file=os.sys.stderr)
    
    toc_lines.append("")
    toc_lines.append("## Active Documentation")
    toc_lines.append("")
    for _, row in sorted(main_docs):
        toc_lines.append(row)
    
    toc_lines.append("")
    toc_lines.append("## Archive")
    toc_lines.append("")
    for _, row in sorted(archive_docs):
        toc_lines.append(row)
    
    output_path = DOCS_DIR / "DOCS_TOC.md"
    output_path.write_text("\n".join(toc_lines), encoding='utf-8')
    print(f"✅ Generated {output_path}")

if __name__ == "__main__":
    generate_toc()

