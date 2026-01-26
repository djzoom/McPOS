#!/usr/bin/env python3
# coding: utf-8
"""
项目结构分析脚本

分析项目结构，识别：
1. 核心模块（McPOS）
2. 适配层（Web后端、脚本）
3. 废弃代码（旧世界、一次性脚本）
4. 依赖关系
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def analyze_imports(file_path: Path) -> Set[str]:
    """分析文件的导入语句"""
    imports = set()
    try:
        with file_path.open("r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except Exception:
        pass
    
    return imports


def analyze_project_structure() -> Dict:
    """分析项目结构"""
    results = {
        "core_modules": [],
        "adapter_layers": [],
        "deprecated_modules": [],
        "test_scripts": [],
        "one_time_scripts": [],
        "dependencies": defaultdict(set),
        "violations": [],
    }
    
    # 核心模块
    mcpos_dir = REPO_ROOT / "mcpos"
    if mcpos_dir.exists():
        for py_file in mcpos_dir.rglob("*.py"):
            if py_file.is_file():
                imports = analyze_imports(py_file)
                # 检查是否违反 Dev_Bible（导入 src/, scripts/, kat_rec_web/）
                violations = imports & {"src", "scripts", "kat_rec_web"}
                if violations:
                    results["violations"].append({
                        "file": str(py_file.relative_to(REPO_ROOT)),
                        "violations": list(violations)
                    })
                results["core_modules"].append(str(py_file.relative_to(REPO_ROOT)))
    
    # 适配层
    web_backend_dir = REPO_ROOT / "kat_rec_web" / "backend"
    if web_backend_dir.exists():
        for py_file in web_backend_dir.rglob("*.py"):
            if py_file.is_file():
                imports = analyze_imports(py_file)
                if "mcpos" in imports:
                    results["adapter_layers"].append(str(py_file.relative_to(REPO_ROOT)))
    
    # 脚本分析
    scripts_dir = REPO_ROOT / "scripts"
    if scripts_dir.exists():
        for py_file in scripts_dir.rglob("*.py"):
            if py_file.is_file():
                rel_path = str(py_file.relative_to(REPO_ROOT))
                file_name = py_file.name
                
                # 分类脚本
                if file_name.startswith("test_"):
                    results["test_scripts"].append(rel_path)
                elif file_name.startswith("check_"):
                    results["test_scripts"].append(rel_path)
                elif file_name.startswith("fix_"):
                    results["one_time_scripts"].append(rel_path)
                elif file_name.startswith("diagnose_"):
                    results["one_time_scripts"].append(rel_path)
                elif "batch" in file_name.lower() or "upload" in file_name.lower():
                    # 生产脚本
                    imports = analyze_imports(py_file)
                    if "mcpos" in imports:
                        results["adapter_layers"].append(rel_path)
    
    # 废弃模块识别
    deprecated_patterns = [
        "create_mixtape.py",
        "batch_generate_covers.py",
        "old",
        "legacy",
        "archive",
    ]
    
    for pattern in deprecated_patterns:
        for py_file in REPO_ROOT.rglob(f"*{pattern}*.py"):
            if py_file.is_file():
                rel_path = str(py_file.relative_to(REPO_ROOT))
                if rel_path not in results["deprecated_modules"]:
                    results["deprecated_modules"].append(rel_path)
    
    return results


def main():
    """主函数"""
    print("="*80)
    print("📊 项目结构分析")
    print("="*80)
    print()
    
    results = analyze_project_structure()
    
    print(f"核心模块（McPOS）: {len(results['core_modules'])} 个文件")
    print(f"适配层: {len(results['adapter_layers'])} 个文件")
    print(f"废弃模块: {len(results['deprecated_modules'])} 个文件")
    print(f"测试脚本: {len(results['test_scripts'])} 个文件")
    print(f"一次性脚本: {len(results['one_time_scripts'])} 个文件")
    print(f"违反 Dev_Bible: {len(results['violations'])} 个文件")
    print()
    
    if results["violations"]:
        print("⚠️  发现违反 Dev_Bible 的文件:")
        for violation in results["violations"][:10]:
            print(f"   {violation['file']}: {violation['violations']}")
        print()
    
    # 保存结果
    output_file = REPO_ROOT / "docs" / "project_structure_analysis.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 分析结果已保存到: {output_file}")
    print()
    
    # 生成清理建议
    print("="*80)
    print("🧹 清理建议")
    print("="*80)
    print()
    
    print("1. 可以删除的废弃模块:")
    for module in results["deprecated_modules"][:10]:
        print(f"   - {module}")
    print()
    
    print("2. 可以归档的测试脚本:")
    for script in results["test_scripts"][:10]:
        print(f"   - {script}")
    print()
    
    print("3. 可以归档的一次性脚本:")
    for script in results["one_time_scripts"][:10]:
        print(f"   - {script}")
    print()


if __name__ == "__main__":
    main()
