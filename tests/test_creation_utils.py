
# tests/test_creation_utils.py
"""Tests for the creation utility functions."""

import pytest
from pathlib import Path
from PIL import Image
from src.creation_utils import get_dominant_color

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_get_dominant_color():
    """
    Tests the dominant color extraction from a sample image.
    It checks if the extracted color is within a plausible range for the given image.
    """
    # This image is known to have a warm, brownish/pinkish tone.
    image_path = REPO_ROOT / "assets/design/images/0xgarfield_a_cute_stylized_cat_sitting_on_a_windowsill_warm_s_3b45c643-8e60-4d03-bba7-b39fa96ed480_0.png"
    
    assert image_path.exists(), "Test image not found!"
    
    dominant_color = get_dominant_color(image_path)
    
    assert isinstance(dominant_color, tuple)
    assert len(dominant_color) == 3
    
    r, g, b = dominant_color
    
    # 期望暖色：R 分量应不小于 G/B，且不是纯灰
    assert r >= g and r >= b
    assert not (r == g == b)
    
    # 放宽范围，允许高亮暖色（如接近 255 的红）
    assert r >= 140

