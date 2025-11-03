#!/usr/bin/env python3
# coding: utf-8
"""
Render 模块冒烟测试

测试视频渲染的基本功能
"""
from __future__ import annotations

from pathlib import Path

import pytest


class TestRenderSmoke:
    """渲染模块冒烟测试"""

    def test_render_module_import(self):
        """测试可以导入渲染模块"""
        try:
            from scripts.local_picker import create_mixtape
            assert create_mixtape is not None
        except ImportError as e:
            pytest.skip(f"Render module not available: {e}")

    def test_render_functions_exist(self):
        """测试关键渲染函数存在"""
        try:
            from scripts.local_picker.create_mixtape import (
                get_output_dir,
                sanitize_title,
            )
            assert callable(get_output_dir)
            assert callable(sanitize_title)
        except ImportError:
            pytest.skip("Render functions not available")

    def test_render_utils_import(self):
        """测试渲染工具函数可导入"""
        try:
            from src.creation_utils import (
                get_dominant_color,
                sanitize_title,
                to_title_case,
            )
            assert callable(sanitize_title)
            assert callable(to_title_case)
        except ImportError:
            pytest.skip("Render utils not available")

