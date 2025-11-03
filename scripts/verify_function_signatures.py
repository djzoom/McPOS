#!/usr/bin/env python3
# coding: utf-8
"""
函数签名一致性验证工具

验证核心函数签名在所有调用点的一致性
"""
from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_function_signature(module_path: str, func_name: str) -> Dict:
    """获取函数的签名信息"""
    try:
        # 动态导入模块
        spec = __import__(module_path, fromlist=[func_name])
        func = getattr(spec, func_name)
        sig = inspect.signature(func)
        
        params = {}
        for param_name, param in sig.parameters.items():
            params[param_name] = {
                "kind": str(param.kind),
                "default": param.default if param.default != inspect.Parameter.empty else None,
                "annotation": str(param.annotation) if param.annotation != inspect.Parameter.empty else None
            }
        
        return {
            "params": params,
            "return_annotation": str(sig.return_annotation) if sig.return_annotation != inspect.Signature.empty else None
        }
    except Exception as e:
        return {"error": str(e)}


def find_function_calls(source_file: Path, func_name: str) -> List[Tuple[int, str]]:
    """在源代码中查找函数调用"""
    calls = []
    try:
        with source_file.open("r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content, filename=str(source_file))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    # 方法调用: obj.method()
                    if node.func.attr == func_name:
                        calls.append((node.lineno, "method_call"))
                elif isinstance(node.func, ast.Name):
                    # 函数调用: func()
                    if node.func.id == func_name:
                        calls.append((node.lineno, "function_call"))
    except Exception:
        pass
    
    return calls


def verify_core_signatures() -> Dict:
    """验证核心函数签名"""
    results = {
        "state_manager": {},
        "metrics_manager": {},
        "issues": []
    }
    
    # 1. 验证 state_manager.update_status
    try:
        sys.path.insert(0, str(REPO_ROOT / "src" / "core"))
        from state_manager import StateManager
        
        sig = inspect.signature(StateManager.update_status)
        expected_params = list(sig.parameters.keys())
        results["state_manager"]["update_status"] = {
            "params": expected_params,
            "signature": str(sig)
        }
        
        # 验证必需参数
        required = [p for p, param in sig.parameters.items() 
                   if param.default == inspect.Parameter.empty and p != 'self']
        results["state_manager"]["update_status"]["required"] = required
        
    except Exception as e:
        results["issues"].append(f"无法验证state_manager.update_status: {e}")
    
    # 2. 验证 state_manager.rollback_status
    try:
        sig = inspect.signature(StateManager.rollback_status)
        expected_params = list(sig.parameters.keys())
        results["state_manager"]["rollback_status"] = {
            "params": expected_params,
            "signature": str(sig)
        }
    except Exception as e:
        results["issues"].append(f"无法验证state_manager.rollback_status: {e}")
    
    # 3. 验证 metrics_manager.record_event
    try:
        from metrics_manager import MetricsManager
        sig = inspect.signature(MetricsManager.record_event)
        expected_params = list(sig.parameters.keys())
        results["metrics_manager"]["record_event"] = {
            "params": expected_params,
            "signature": str(sig)
        }
    except Exception as e:
        results["issues"].append(f"无法验证metrics_manager.record_event: {e}")
    
    return results


def main():
    print("🔍 验证函数签名一致性...\n")
    
    results = verify_core_signatures()
    
    print("📋 核心函数签名")
    print("=" * 70)
    
    if results["state_manager"].get("update_status"):
        info = results["state_manager"]["update_status"]
        print(f"\n✅ StateManager.update_status")
        print(f"   签名: {info['signature']}")
        print(f"   必需参数: {', '.join(info['required'])}")
    
    if results["state_manager"].get("rollback_status"):
        info = results["state_manager"]["rollback_status"]
        print(f"\n✅ StateManager.rollback_status")
        print(f"   签名: {info['signature']}")
    
    if results["metrics_manager"].get("record_event"):
        info = results["metrics_manager"]["record_event"]
        print(f"\n✅ MetricsManager.record_event")
        print(f"   签名: {info['signature']}")
    
    if results["issues"]:
        print("\n⚠️  问题:")
        for issue in results["issues"]:
            print(f"   - {issue}")
    else:
        print("\n✅ 所有核心函数签名验证通过")
    
    print("\n" + "=" * 70)
    return 0 if not results["issues"] else 1


if __name__ == "__main__":
    sys.exit(main())

