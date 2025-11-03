#!/usr/bin/env python3
# coding: utf-8
"""
标题生成功能测试

测试generate_full_schedule.py中的标题生成逻辑，包括：
1. 无API配置时的错误处理
2. API成功但标题模式重复的重试逻辑
3. API返回超过7个词的标题处理
4. API完全失败时的错误处理
5. 标题去重逻辑正确性
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加项目路径
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "local_picker"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from schedule_master import ScheduleMaster
    from generate_full_schedule import generate_episode_content
except ImportError as e:
    print(f"⚠️  导入失败: {e}")
    print("   某些测试可能无法运行")


class TestTitleGeneration(unittest.TestCase):
    """标题生成测试"""
    
    def setUp(self):
        """测试前准备"""
        self.test_image_path = REPO_ROOT / "assets" / "design" / "images"
        # 获取第一个存在的图片作为测试图片
        if self.test_image_path.exists():
            image_files = list(self.test_image_path.glob("*.png"))
            if image_files:
                self.test_image = image_files[0]
            else:
                self.test_image = None
        else:
            self.test_image = None
        
        # 创建模拟排播表
        self.schedule = Mock(spec=ScheduleMaster)
        self.schedule.title_patterns = []
        self.schedule.episodes = []
        self.schedule.get_recent_tracks = Mock(return_value=set())
        self.schedule.get_used_starting_tracks = Mock(return_value=set())
        self.schedule.get_all_used_tracks = Mock(return_value=set())
        
        def mock_check_title_pattern(title):
            """模拟标题模式检查"""
            # 简单模拟：如果标题包含"duplicate"，返回False
            if "duplicate" in title.lower():
                pattern = "test_pattern_dup"
                return False, pattern
            else:
                pattern = f"test_pattern_{title.lower().replace(' ', '_')}"
                return True, pattern
        
        self.schedule.check_title_pattern = Mock(side_effect=mock_check_title_pattern)
        self.schedule.add_title_pattern = Mock()
        
        # 创建模拟曲目
        from create_mixtape import Track
        self.mock_tracks = [
            Track(title=f"Track {i}", duration_sec=180, file_path=f"track{i}.mp3")
            for i in range(30)
        ]
    
    def test_1_no_api_key_raises_system_exit(self):
        """测试1: 无API配置时抛出SystemExit"""
        if not self.test_image:
            self.skipTest("测试图片不存在，跳过测试")
        
        episode = {
            "episode_id": "20251101",
            "episode_number": 1,
            "schedule_date": "2025-11-01",
            "image_path": str(self.test_image)
        }
        
        # 模拟require_api_key抛出SystemExit
        # 由于generate_full_schedule内部导入require_api_key，需要patch导入的位置
        with patch('api_config.require_api_key', side_effect=SystemExit(1)):
            with self.assertRaises(SystemExit):
                generate_episode_content(
                    episode,
                    self.schedule,
                    self.mock_tracks
                )
    
    def test_2_api_success_but_duplicate_pattern_retries(self):
        """测试2: API成功但标题模式重复的重试逻辑"""
        if not self.test_image:
            self.skipTest("测试图片不存在，跳过测试")
        
        episode = {
            "episode_id": "20251101",
            "episode_number": 1,
            "schedule_date": "2025-11-01",
            "image_path": str(self.test_image)
        }
        
        # 模拟API调用：第一次返回重复标题，第二次返回唯一标题
        call_count = [0]
        def mock_try_api_title(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return "Duplicate Title Here"  # 会被标记为重复
            else:
                return "Unique New Title"  # 唯一标题
        
        with patch('api_config.require_api_key', return_value="sk-test-key"):
            with patch('create_mixtape._try_api_title', side_effect=mock_try_api_title):
                # 修改check_title_pattern模拟，第一次返回False，后续返回True
                check_count = [0]
                def mock_check(title):
                    check_count[0] += 1
                    if check_count[0] == 1:
                        return False, "dup_pattern"
                    else:
                        return True, "unique_pattern"
                
                self.schedule.check_title_pattern = Mock(side_effect=mock_check)
                
                result = generate_episode_content(
                    episode,
                    self.schedule,
                    self.mock_tracks
                )
                
                # 应该成功生成标题（重试后）
                self.assertIsNotNone(result)
                self.assertEqual(result["title"], "Unique New Title")
                self.assertEqual(result["title_pattern"], "unique_pattern")
    
    def test_3_api_returns_over_7_words_retries(self):
        """测试3: API返回超过7个词的标题处理"""
        if not self.test_image:
            self.skipTest("测试图片不存在，跳过测试")
        
        episode = {
            "episode_id": "20251101",
            "episode_number": 1,
            "schedule_date": "2025-11-01",
            "image_path": str(self.test_image)
        }
        
        # 模拟API调用：第一次返回超过7个词，第二次返回有效标题
        call_count = [0]
        def mock_try_api_title(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return "This Is A Very Long Title That Exceeds Seven Words Limit"  # 超过7个词
            else:
                return "Short Valid Title"  # 有效标题
        
        with patch('api_config.require_api_key', return_value="sk-test-key"):
            with patch('create_mixtape._try_api_title', side_effect=mock_try_api_title):
                result = generate_episode_content(
                    episode,
                    self.schedule,
                    self.mock_tracks
                )
                
                # 应该成功生成标题（重试后）
                self.assertIsNotNone(result)
                self.assertEqual(result["title"], "Short Valid Title")
                # 验证API被调用了至少2次
                self.assertGreaterEqual(call_count[0], 2)
    
    def test_4_api_complete_failure_raises_error(self):
        """测试4: API完全失败时的错误处理"""
        if not self.test_image:
            self.skipTest("测试图片不存在，跳过测试")
        
        episode = {
            "episode_id": "20251101",
            "episode_number": 1,
            "schedule_date": "2025-11-01",
            "image_path": str(self.test_image)
        }
        
        # 模拟API调用始终返回None
        with patch('api_config.require_api_key', return_value="sk-test-key"):
            with patch('create_mixtape._try_api_title', return_value=None):
                with self.assertRaises(RuntimeError) as context:
                    generate_episode_content(
                        episode,
                        self.schedule,
                        self.mock_tracks
                    )
                
                # 验证错误信息包含重试次数
                error_msg = str(context.exception)
                self.assertIn("API生成标题失败", error_msg)
                self.assertIn("重试", error_msg)
    
    def test_5_title_deduplication_logic_correctness(self):
        """测试5: 标题去重逻辑正确性"""
        if not self.test_image:
            self.skipTest("测试图片不存在，跳过测试")
        
        episode = {
            "episode_id": "20251101",
            "episode_number": 1,
            "schedule_date": "2025-11-01",
            "image_path": str(self.test_image)
        }
        
        # 设置已使用的标题模式
        self.schedule.title_patterns = ["existing_pattern_1", "existing_pattern_2"]
        
        # 模拟check_title_pattern返回不同的结果
        check_results = [
            (False, "existing_pattern_1"),  # 第一次：重复
            (True, "new_unique_pattern"),   # 第二次：唯一
        ]
        check_index = [0]
        
        def mock_check(title):
            idx = check_index[0]
            check_index[0] += 1
            return check_results[min(idx, len(check_results) - 1)]
        
        self.schedule.check_title_pattern = Mock(side_effect=mock_check)
        
        # 模拟API调用
        api_call_count = [0]
        def mock_try_api_title(*args, **kwargs):
            api_call_count[0] += 1
            return f"Test Title {api_call_count[0]}"
        
        with patch('api_config.require_api_key', return_value="sk-test-key"):
            with patch('create_mixtape._try_api_title', side_effect=mock_try_api_title):
                result = generate_episode_content(
                    episode,
                    self.schedule,
                    self.mock_tracks
                )
                
                # 验证去重逻辑被调用
                self.assertGreaterEqual(self.schedule.check_title_pattern.call_count, 1)
                # 验证最终生成了唯一标题
                self.assertIsNotNone(result)
                self.assertIsNotNone(result["title"])
                self.assertEqual(result["title_pattern"], "new_unique_pattern")


if __name__ == "__main__":
    unittest.main()

