#!/usr/bin/env python3
# coding: utf-8
"""
生成详细的清理计划

基于项目结构分析，生成具体的清理清单和执行步骤。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_analysis() -> Dict:
    """加载项目结构分析结果"""
    analysis_file = REPO_ROOT / "docs" / "project_structure_analysis.json"
    if analysis_file.exists():
        with analysis_file.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def categorize_scripts(scripts: List[str]) -> Dict[str, List[str]]:
    """分类脚本"""
    categories = {
        "production": [],  # 生产环境使用
        "test": [],        # 测试脚本
        "fix": [],         # 一次性修复脚本
        "debug": [],       # 调试脚本
        "deprecated": [],  # 废弃脚本
        "tools": [],       # 工具脚本
    }
    
    for script in scripts:
        script_path = Path(script)
        script_name = script_path.name.lower()
        
        # 生产脚本
        if any(keyword in script_name for keyword in ["batch", "upload", "produce", "generate"]):
            if "test" not in script_name and "fix" not in script_name:
                categories["production"].append(script)
                continue
        
        # 测试脚本
        if script_name.startswith("test_") or script_name.startswith("check_"):
            categories["test"].append(script)
            continue
        
        # 修复脚本
        if script_name.startswith("fix_"):
            categories["fix"].append(script)
            continue
        
        # 调试脚本
        if script_name.startswith("diagnose_") or "debug" in script_name:
            categories["debug"].append(script)
            continue
        
        # 废弃脚本
        if any(keyword in script_name for keyword in ["old", "legacy", "archive", "create_mixtape"]):
            categories["deprecated"].append(script)
            continue
        
        # 工具脚本
        if any(keyword in script_name for keyword in ["auth", "config", "setup", "verify"]):
            categories["tools"].append(script)
            continue
        
        # 默认归类为工具
        categories["tools"].append(script)
    
    return categories


def generate_cleanup_plan() -> Dict:
    """生成清理计划"""
    analysis = load_analysis()
    
    plan = {
        "delete": {
            "directories": [],
            "files": [],
        },
        "archive": {
            "test_scripts": [],
            "fix_scripts": [],
            "debug_scripts": [],
            "deprecated_scripts": [],
        },
        "keep": {
            "core_modules": [],
            "production_scripts": [],
            "tools": [],
        },
        "refactor": {
            "src_directory": "需要评估",
            "duplicate_modules": [],
        },
    }
    
    # 分析脚本
    all_scripts = []
    scripts_dir = REPO_ROOT / "scripts"
    if scripts_dir.exists():
        for py_file in scripts_dir.rglob("*.py"):
            if py_file.is_file():
                all_scripts.append(str(py_file.relative_to(REPO_ROOT)))
    
    categorized = categorize_scripts(all_scripts)
    
    # 删除清单
    plan["delete"]["directories"] = [
        "#/",  # 临时目录
        "desktop/",  # 可能废弃
    ]
    
    plan["delete"]["files"] = [
        "scripts/local_picker/create_mixtape.py",  # 已被 McPOS 替代
        "scripts/local_picker/batch_generate_covers.py",  # 依赖旧世界脚本
    ]
    
    # 归档清单
    plan["archive"]["test_scripts"] = categorized["test"]
    plan["archive"]["fix_scripts"] = categorized["fix"]
    plan["archive"]["debug_scripts"] = categorized["debug"]
    plan["archive"]["deprecated_scripts"] = categorized["deprecated"]
    
    # 保留清单
    plan["keep"]["core_modules"] = analysis.get("core_modules", [])[:10]  # 示例
    plan["keep"]["production_scripts"] = categorized["production"]
    plan["keep"]["tools"] = categorized["tools"]
    
    return plan


def main():
    """主函数"""
    print("="*80)
    print("📋 生成清理计划")
    print("="*80)
    print()
    
    plan = generate_cleanup_plan()
    
    print("🗑️  删除清单:")
    print(f"   目录: {len(plan['delete']['directories'])} 个")
    for dir_path in plan["delete"]["directories"]:
        print(f"     - {dir_path}")
    print(f"   文件: {len(plan['delete']['files'])} 个")
    for file_path in plan["delete"]["files"]:
        print(f"     - {file_path}")
    print()
    
    print("📦 归档清单:")
    print(f"   测试脚本: {len(plan['archive']['test_scripts'])} 个")
    print(f"   修复脚本: {len(plan['archive']['fix_scripts'])} 个")
    print(f"   调试脚本: {len(plan['archive']['debug_scripts'])} 个")
    print(f"   废弃脚本: {len(plan['archive']['deprecated_scripts'])} 个")
    print()
    
    print("✅ 保留清单:")
    print(f"   生产脚本: {len(plan['keep']['production_scripts'])} 个")
    for script in plan["keep"]["production_scripts"][:10]:
        print(f"     - {script}")
    print(f"   工具脚本: {len(plan['keep']['tools'])} 个")
    for script in plan["keep"]["tools"][:10]:
        print(f"     - {script}")
    print()
    
    # 保存计划
    plan_file = REPO_ROOT / "docs" / "cleanup_plan.json"
    with plan_file.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 清理计划已保存到: {plan_file}")
    print()
    
    # 生成执行脚本
    generate_execution_script(plan)


def generate_execution_script(plan: Dict):
    """生成执行脚本"""
    script_content = """#!/bin/bash
# 项目清理执行脚本
# 基于 cleanup_plan.json 自动生成

set -e  # 遇到错误立即退出

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE_DIR="$REPO_ROOT/scripts/archive"

echo "=========================================="
echo "🧹 Kat Rec 项目清理"
echo "=========================================="
echo ""

# 创建归档目录
echo "📦 创建归档目录..."
mkdir -p "$ARCHIVE_DIR"/{test,fix,debug,deprecated}
echo "✅ 归档目录已创建"
echo ""

# 归档测试脚本
echo "📦 归档测试脚本..."
"""
    
    for script in plan["archive"]["test_scripts"]:
        script_path = Path(script)
        if script_path.exists():
            script_content += f'mv "$REPO_ROOT/{script}" "$ARCHIVE_DIR/test/" 2>/dev/null || echo "跳过: {script}"\n'
    
    script_content += 'echo "✅ 测试脚本已归档"\n'
    script_content += 'echo ""\n'
    script_content += '# 归档修复脚本\n'
    script_content += 'echo "📦 归档修复脚本..."\n'
    
    for script in plan["archive"]["fix_scripts"]:
        script_path = Path(script)
        if script_path.exists():
            script_content += f'mv "$REPO_ROOT/{script}" "$ARCHIVE_DIR/fix/" 2>/dev/null || echo "跳过: {script}"\n'
    
    script_content += 'echo "✅ 修复脚本已归档"\n'
    script_content += 'echo ""\n'
    script_content += '# 归档调试脚本\n'
    script_content += 'echo "📦 归档调试脚本..."\n'
    
    for script in plan["archive"]["debug_scripts"]:
        script_path = Path(script)
        if script_path.exists():
            script_content += f'mv "$REPO_ROOT/{script}" "$ARCHIVE_DIR/debug/" 2>/dev/null || echo "跳过: {script}"\n'
    
    script_content += 'echo "✅ 调试脚本已归档"\n'
    script_content += 'echo ""\n'
    script_content += 'echo "=========================================="\n'
    script_content += 'echo "✅ 清理完成"\n'
    script_content += 'echo "=========================================="\n'
    
    script_file = REPO_ROOT / "scripts" / "execute_cleanup.sh"
    with script_file.open("w", encoding="utf-8") as f:
        f.write(script_content)
    
    import os
    os.chmod(script_file, 0o755)
    
    print(f"✅ 执行脚本已生成: {script_file}")
    print("   运行方式: bash scripts/execute_cleanup.sh")


if __name__ == "__main__":
    main()
