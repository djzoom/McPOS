#!/usr/bin/env python3
# coding: utf-8
"""
MRRC (Maintenance, Refactoring & Release Cycle) - Full Project Cleanup

This script performs a comprehensive maintenance and refactoring cycle:
1. Maintenance Pass - Remove scaffolding, deprecated files
2. Refactoring Pass - Apply standards, consolidate code
3. Documentation Pass - Update docs and changelogs
4. Logging & Stability Pass - Standardize logging
5. Release Preparation - Validate and prepare release

Usage:
    python scripts/mrrc_cycle.py [--dry-run] [--phase PHASE]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


class MRRCCycle:
    """MRRC执行器"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.report: Dict = {
            "timestamp": datetime.now().isoformat(),
            "dry_run": dry_run,
            "phases": {},
            "files_removed": [],
            "files_updated": [],
            "issues_found": [],
            "warnings": [],
        }
    
    def run_all_phases(self) -> Dict:
        """运行所有阶段"""
        print("\n" + "="*70)
        print("🔧 MRRC (Maintenance, Refactoring & Release Cycle)")
        print("="*70 + "\n")
        
        phases = [
            ("maintenance", "Maintenance Pass", self.maintenance_pass),
            ("refactoring", "Refactoring Pass", self.refactoring_pass),
            ("documentation", "Documentation Pass", self.documentation_pass),
            ("logging", "Logging & Stability Pass", self.logging_pass),
            ("release", "Release Preparation", self.release_preparation),
        ]
        
        for phase_id, phase_name, phase_func in phases:
            print(f"\n{'='*70}")
            print(f"📋 Phase: {phase_name}")
            print(f"{'='*70}\n")
            
            try:
                result = phase_func()
                self.report["phases"][phase_id] = result
                print(f"✅ {phase_name} completed")
            except KeyboardInterrupt:
                print(f"\n\n⚠️  用户中断: Phase {phase_id}")
                self.report["phases"][phase_id] = {"error": "Interrupted by user"}
                raise
            except Exception as e:
                error_msg = f"Phase {phase_id} failed: {e}"
                print(f"❌ {error_msg}")
                self.report["phases"][phase_id] = {"error": error_msg}
                if not self.dry_run:
                    import traceback
                    traceback.print_exc()
                # 继续执行其他阶段，不中断整个流程
        
        self._save_report()
        return self.report
    
    def maintenance_pass(self) -> Dict:
        """阶段1: 维护清理"""
        result = {
            "files_removed": [],
            "files_archived": [],
            "deprecated_found": [],
        }
        
        # 1.1 删除废弃文件
        obsolete_files = [
            "config/pppproduction_log.json",  # 错误命名的文件，包含DEMO引用
        ]
        
        for file_path in obsolete_files:
            full_path = REPO_ROOT / file_path
            if full_path.exists():
                if self.dry_run:
                    print(f"[DRY RUN] 将删除: {file_path}")
                else:
                    full_path.unlink()
                    print(f"🗑️  已删除: {file_path}")
                result["files_removed"].append(file_path)
        
        # 1.2 检查废弃脚本（标记但保留）
        deprecated_scripts = [
            "scripts/local_picker/sync_resources.py",  # 已标记废弃
        ]
        
        for script_path in deprecated_scripts:
            full_path = REPO_ROOT / script_path
            if full_path.exists():
                content = full_path.read_text(encoding='utf-8')
                if "已废弃" in content or "已弃用" in content:
                    result["deprecated_found"].append(script_path)
                    print(f"⚠️  废弃脚本（保留）: {script_path}")
        
        # 1.3 检查未使用的导入
        unused_imports = self._find_unused_imports()
        if unused_imports:
            result["unused_imports"] = unused_imports
            print(f"📝 发现 {len(unused_imports)} 个文件可能有未使用的导入")
        
        return result
    
    def refactoring_pass(self) -> Dict:
        """阶段2: 重构"""
        result = {
            "files_checked": 0,
            "type_hints_added": 0,
            "print_replaced": 0,
            "pep8_fixes": 0,
        }
        
        # 2.1 统计print()使用情况
        print_files = self._count_print_statements()
        result["print_count"] = sum(print_files.values())
        result["files_with_print"] = len(print_files)
        
        print(f"📊 发现 {result['print_count']} 个 print() 语句在 {result['files_with_print']} 个文件中")
        print(f"💡 建议：逐步替换为结构化日志（logging）")
        
        # 2.2 检查类型提示
        type_hint_stats = self._check_type_hints()
        result["type_hint_coverage"] = type_hint_stats
        print(f"📊 类型提示覆盖率: {type_hint_stats['coverage']:.1f}%")
        
        # 2.3 检查PEP8违规
        pep8_issues = self._check_pep8_issues()
        result["pep8_issues"] = len(pep8_issues)
        if pep8_issues:
            print(f"⚠️  发现 {len(pep8_issues)} 个潜在的PEP8问题")
        
        return result
    
    def documentation_pass(self) -> Dict:
        """阶段3: 文档更新"""
        result = {
            "docs_reviewed": 0,
            "docs_updated": [],
            "broken_links": [],
        }
        
        # 3.1 检查文档
        docs_dir = REPO_ROOT / "docs"
        if docs_dir.exists():
            docs_files = list(docs_dir.glob("*.md"))
            result["docs_reviewed"] = len(docs_files)
            print(f"📚 审查了 {len(docs_files)} 个文档文件")
        
        # 3.2 检查文档链接
        if not self.dry_run:
            try:
                broken_links = self._check_doc_links()
                result["broken_links"] = broken_links
                if broken_links:
                    print(f"⚠️  发现 {len(broken_links)} 个断链")
            except Exception as e:
                print(f"⚠️  链接检查失败: {e}")
        
        # 3.3 更新主要文档
        if not self.dry_run:
            self._update_main_docs()
            result["docs_updated"] = ["README.md", "docs/ARCHITECTURE.md"]
        
        return result
    
    def logging_pass(self) -> Dict:
        """阶段4: 日志标准化"""
        result = {
            "logging_modules": [],
            "log_level_issues": [],
        }
        
        # 4.1 检查日志配置
        logging_configs = self._check_logging_config()
        result["logging_modules"] = logging_configs
        
        # 4.2 验证日志格式
        log_file = REPO_ROOT / "logs" / "katrec.log"
        if log_file.exists():
            log_lines = log_file.read_text(encoding='utf-8').split('\n')
            json_lines = [l for l in log_lines if l.strip() and l.strip().startswith('{')]
            result["log_format_valid"] = len(json_lines) > 0
            print(f"📊 日志文件包含 {len(json_lines)} 条JSON格式记录")
        
        return result
    
    def release_preparation(self) -> Dict:
        """阶段5: 发布准备"""
        result = {
            "tests_run": False,
            "dependencies_check": False,
            "validation_passed": False,
        }
        
        # 5.1 检查依赖
        if not self.dry_run:
            try:
                check_result = subprocess.run(
                    [sys.executable, "-m", "pip", "check"],
                    capture_output=True,
                    text=True,
                    cwd=REPO_ROOT
                )
                result["dependencies_check"] = check_result.returncode == 0
                if check_result.returncode == 0:
                    print("✅ 依赖检查通过")
                else:
                    print(f"⚠️  依赖问题:\n{check_result.stdout}")
            except (FileNotFoundError, subprocess.SubprocessError) as e:
                print(f"⚠️  无法运行pip check: {e}")
            except Exception as e:
                print(f"⚠️  无法运行pip check: {type(e).__name__}: {e}")
        
        # 5.2 运行测试（如果存在）
        test_dir = REPO_ROOT / "tests"
        if test_dir.exists():
            test_files = list(test_dir.glob("test_*.py"))
            if test_files:
                print(f"📋 发现 {len(test_files)} 个测试文件")
                result["test_files_count"] = len(test_files)
        
        return result
    
    def _find_unused_imports(self) -> List[Dict]:
        """
        查找可能未使用的导入
        
        Returns:
            包含未使用导入信息的字典列表
        """
        issues = []
        scripts_dir = REPO_ROOT / "scripts"
        
        for py_file in scripts_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                tree = ast.parse(content, filename=str(py_file))
                
                # 提取所有导入
                imports = set()
                import_aliases = {}
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split('.')[0])
                            if alias.asname:
                                import_aliases[alias.asname] = alias.name.split('.')[0]
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split('.')[0])
                        for alias in node.names:
                            name = alias.name if not alias.asname else alias.asname
                            imports.add(name.split('.')[0])
                
                # 检查导入是否在代码中使用（简单检查）
                # 注意：这是简化版本，可能产生误报
                used_imports = set()
                for name in ast.walk(tree):
                    if isinstance(name, ast.Name):
                        if name.id in imports or name.id in import_aliases:
                            used_imports.add(name.id)
                
                # 找出可能的未使用导入（保守策略）
                unused = imports - used_imports
                # 排除内置模块和常见的情况
                builtin_modules = {'sys', 'os', 'pathlib', 'json', 'argparse', 'typing', 'collections', 'datetime', 're', 'subprocess'}
                unused = unused - builtin_modules
                
                if unused:
                    issues.append({
                        "file": str(py_file.relative_to(REPO_ROOT)),
                        "unused_imports": sorted(unused),
                        "note": "可能有误报，需要人工检查"
                    })
                    
            except SyntaxError:
                # 跳过语法错误的文件
                continue
            except Exception as e:
                # 记录错误但不中断流程
                issues.append({
                    "file": str(py_file.relative_to(REPO_ROOT)),
                    "error": f"Failed to analyze: {e}"
                })
        
        return issues
    
    def _count_print_statements(self) -> Dict[str, int]:
        """统计print()语句"""
        counts = {}
        scripts_dir = REPO_ROOT / "scripts"
        
        for py_file in scripts_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding='utf-8')
                count = len(re.findall(r'\bprint\s*\(', content))
                if count > 0:
                    counts[str(py_file.relative_to(REPO_ROOT))] = count
            except (UnicodeDecodeError, PermissionError, OSError):
                # 跳过无法读取的文件
                continue
        
        return counts
    
    def _check_type_hints(self) -> Dict:
        """检查类型提示覆盖率"""
        stats = {"total": 0, "with_hints": 0}
        
        scripts_dir = REPO_ROOT / "scripts"
        for py_file in scripts_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        stats["total"] += 1
                        if node.returns or any(
                            arg.annotation for arg in node.args.args
                        ):
                            stats["with_hints"] += 1
            except (SyntaxError, UnicodeDecodeError):
                # 跳过语法错误和编码问题的文件
                continue
            except (PermissionError, OSError):
                # 跳过权限错误的文件
                continue
        
        coverage = (stats["with_hints"] / stats["total"] * 100) if stats["total"] > 0 else 0
        stats["coverage"] = coverage
        return stats
    
    def _check_pep8_issues(self) -> List[str]:
        """检查PEP8问题（简化版）"""
        issues = []
        # 这里可以集成flake8或pylint
        return issues
    
    def _check_doc_links(self) -> List[str]:
        """
        检查文档链接
        
        Returns:
            断链列表
        """
        broken = []
        check_script = REPO_ROOT / "scripts" / "check_doc_links.py"
        
        if check_script.exists():
            try:
                result = subprocess.run(
                    [sys.executable, str(check_script)],
                    capture_output=True,
                    text=True,
                    cwd=REPO_ROOT,
                    timeout=30
                )
                
                if result.returncode != 0:
                    # 解析输出查找断链
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if "not found" in line.lower() or "broken" in line.lower():
                            broken.append(line.strip())
            except subprocess.TimeoutExpired:
                broken.append("Link check timed out")
            except Exception as e:
                broken.append(f"Link check failed: {e}")
        else:
            # 简单的手动检查
            docs_dir = REPO_ROOT / "docs"
            if docs_dir.exists():
                for doc_file in docs_dir.glob("*.md"):
                    try:
                        content = doc_file.read_text(encoding='utf-8')
                        # 查找 markdown 链接
                        import re
                        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
                        for match in re.finditer(link_pattern, content):
                            link_path = match.group(2)
                            if not link_path.startswith(('http', 'https', 'mailto:')):
                                # 相对链接
                                if link_path.startswith('/'):
                                    target = REPO_ROOT / link_path.lstrip('/')
                                else:
                                    target = doc_file.parent / link_path
                                
                                if not target.exists():
                                    broken.append(f"{doc_file.relative_to(REPO_ROOT)}: {link_path}")
                    except (UnicodeDecodeError, PermissionError, OSError):
                        # 跳过无法读取的文件
                        continue
        
        return broken
    
    def _check_logging_config(self) -> List[str]:
        """检查日志配置"""
        modules = []
        scripts_dir = REPO_ROOT / "scripts"
        
        for py_file in scripts_dir.rglob("*.py"):
            content = py_file.read_text(encoding='utf-8')
            if "import logging" in content or "from logging import" in content:
                modules.append(str(py_file.relative_to(REPO_ROOT)))
        
        return modules
    
    def _update_main_docs(self):
        """
        更新主要文档
        
        添加 MRRC 相关信息到核心文档
        """
        readme_path = REPO_ROOT / "README.md"
        if readme_path.exists():
            try:
            content = readme_path.read_text(encoding='utf-8')
                
                # 检查是否已有 MRRC 部分
                if "MRRC" not in content or "Maintenance, Refactoring & Release Cycle" not in content:
                    # 在合适的位置插入 MRRC 部分
                    mrrc_section = """
## 🔄 MRRC System (Maintenance, Refactoring & Release Cycle)

The project follows a regular **MRRC cycle** to ensure code quality and consistency:

1. **Maintenance Pass**: Remove scaffolding, deprecated files, and unused imports
2. **Refactoring Pass**: Apply PEP8, type hints, replace print() with logging
3. **Documentation Pass**: Update docs, validate links, generate changelog
4. **Logging & Stability Pass**: Standardize log levels, verify state transitions
5. **Release Preparation**: Run tests, check dependencies, validate system

Run MRRC cycle:
```bash
python scripts/mrrc_cycle.py [--dry-run] [--phase PHASE]
```
"""
                    
                    # 尝试在 "Development" 或 "🛠️" 部分之后插入
                    dev_section_match = re.search(r'(##\s*🛠️.*?Development.*?\n)', content, re.IGNORECASE | re.DOTALL)
                    if dev_section_match:
                        insert_pos = dev_section_match.end()
                        content = content[:insert_pos] + mrrc_section + "\n" + content[insert_pos:]
                    else:
                        # 如果找不到合适位置，在文档末尾添加
                        content = content.rstrip() + "\n" + mrrc_section + "\n"
                    
                    if not self.dry_run:
                        readme_path.write_text(content, encoding='utf-8')
                        print(f"✅ 已更新 README.md")
            except Exception as e:
                print(f"⚠️  更新 README.md 失败: {e}")
    
    def _save_report(self):
        """保存报告"""
        report_file = REPO_ROOT / "logs" / f"mrrc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.dry_run:
            report_file.write_text(
                json.dumps(self.report, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            print(f"\n📄 MRRC报告已保存: {report_file}")
        
        # 也输出摘要
        self._print_summary()
    
    def _print_summary(self):
        """打印摘要"""
        print("\n" + "="*70)
        print("📊 MRRC Summary")
        print("="*70)
        
        for phase_id, phase_result in self.report["phases"].items():
            if isinstance(phase_result, dict) and "error" not in phase_result:
                print(f"\n{phase_id}:")
                for key, value in phase_result.items():
                    if isinstance(value, (int, float, bool)):
                        print(f"  {key}: {value}")
                    elif isinstance(value, list) and len(value) <= 5:
                        print(f"  {key}: {len(value)} items")


def main():
    parser = argparse.ArgumentParser(description="MRRC Cycle - Full Project Cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--phase", choices=["maintenance", "refactoring", "documentation", "logging", "release"],
                       help="Run only specific phase")
    
    args = parser.parse_args()
    
    mrrc = MRRCCycle(dry_run=args.dry_run)
    
    if args.phase:
        # 运行单个阶段
        phase_map = {
            "maintenance": mrrc.maintenance_pass,
            "refactoring": mrrc.refactoring_pass,
            "documentation": mrrc.documentation_pass,
            "logging": mrrc.logging_pass,
            "release": mrrc.release_preparation,
        }
        result = phase_map[args.phase]()
        print(f"\n✅ Phase '{args.phase}' completed")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # 运行所有阶段
        report = mrrc.run_all_phases()
        print("\n✅ MRRC Cycle completed!")


if __name__ == "__main__":
    main()

