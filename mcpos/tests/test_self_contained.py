"""
Self-contained tests for McPOS core functionality.

These tests verify that McPOS can operate independently without external dependencies,
and that core interfaces remain stable and correct.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import List

from mcpos.models import EpisodeSpec, AssetPaths, EpisodeState, StageName
from mcpos.config import get_config, set_config
from mcpos.adapters.filesystem import build_asset_paths, detect_episode_state_from_filesystem
from mcpos.assets.init import generate_playlist_for_episode, init_episode
import asyncio


class TestStateDerivation:
    """Test that state derivation from filesystem works correctly."""
    
    def test_state_init_only(self, test_tmp_dir):
        """Test state detection when only init files exist."""
        # Setup minimal episode directory
        episode_dir = test_tmp_dir / "channels" / "kat" / "output" / "kat_20241201"
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        # Create only init files
        (episode_dir / "playlist.csv").write_text("test")
        (episode_dir / "recipe.json").write_text("{}")
        
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        config = get_config()
        config.channels_root = test_tmp_dir / "channels"
        paths = build_asset_paths(spec, config)
        
        state = detect_episode_state_from_filesystem(spec, paths)
        
        assert state.stage_completed[StageName.INIT] is True
        assert state.stage_completed[StageName.TEXT_BASE] is False
        assert state.stage_completed[StageName.COVER] is False
        assert state.stage_completed[StageName.MIX] is False
        assert state.stage_completed[StageName.TEXT_SRT] is False
        assert state.stage_completed[StageName.RENDER] is False
        assert state.current_stage == StageName.TEXT_BASE  # TEXT_BASE comes before COVER in default order
    
    def test_state_with_cover(self, test_tmp_dir):
        """Test state detection when cover is added."""
        episode_dir = test_tmp_dir / "channels" / "kat" / "output" / "kat_20241201"
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        # Create init + cover
        (episode_dir / "playlist.csv").write_text("test")
        (episode_dir / "recipe.json").write_text("{}")
        (episode_dir / "kat_20241201_cover.png").write_bytes(b"fake png")
        
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        config = get_config()
        config.channels_root = test_tmp_dir / "channels"
        paths = build_asset_paths(spec, config)
        
        state = detect_episode_state_from_filesystem(spec, paths)
        
        assert state.stage_completed[StageName.INIT] is True
        assert state.stage_completed[StageName.TEXT_BASE] is False
        assert state.stage_completed[StageName.COVER] is True
        assert state.stage_completed[StageName.MIX] is False
        assert state.current_stage == StageName.TEXT_BASE  # TEXT_BASE comes before MIX
    
    def test_state_text_base_requires_all_three_files(self, test_tmp_dir):
        """Test that all three text_base files are required for TEXT_BASE stage completion."""
        episode_dir = test_tmp_dir / "channels" / "kat" / "output" / "kat_20241201"
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        # Create init + cover + partial text_base
        (episode_dir / "playlist.csv").write_text("test")
        (episode_dir / "recipe.json").write_text("{}")
        (episode_dir / "kat_20241201_cover.png").write_bytes(b"fake png")
        (episode_dir / "kat_20241201_youtube_title.txt").write_text("Title")
        (episode_dir / "kat_20241201_youtube_description.txt").write_text("Desc")
        # Missing tags (text_base incomplete)
        
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        config = get_config()
        config.channels_root = test_tmp_dir / "channels"
        paths = build_asset_paths(spec, config)
        
        state = detect_episode_state_from_filesystem(spec, paths)
        
        assert state.stage_completed[StageName.TEXT_BASE] is False
        assert state.current_stage == StageName.TEXT_BASE


class TestPlaylistGeneration:
    """Test that playlist generation is self-contained and deterministic."""
    
    def test_playlist_generation_independent(self, test_tmp_dir):
        """Test that playlist generation works with minimal inputs, no external deps."""
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        
        # Create minimal fake library
        library_index: List[Path] = [
            test_tmp_dir / "song1.mp3",
            test_tmp_dir / "song2.mp3",
            test_tmp_dir / "song3.mp3",
            test_tmp_dir / "song4.mp3",
            test_tmp_dir / "song5.mp3",
        ]
        for song in library_index:
            song.write_bytes(b"fake audio")
        
        config = {
            "target_duration_minutes": 60,
            "special_tags": [],
            "must_include_track_ids": [],
        }
        
        # Should not raise any import errors or external dependencies
        side_a, side_b = generate_playlist_for_episode(
            spec=spec,
            library_index=library_index,
            config=config,
            history=None,
        )
        
        assert len(side_a) > 0
        assert len(side_b) > 0
        assert all("file_path" in track for track in side_a + side_b)
        assert all("duration_seconds" in track for track in side_a + side_b)
    
    def test_playlist_generation_deterministic(self, test_tmp_dir):
        """Test that playlist generation is deterministic with same seed."""
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        
        library_index: List[Path] = [
            test_tmp_dir / f"song{i}.mp3" for i in range(20)
        ]
        for song in library_index:
            song.write_bytes(b"fake audio")
        
        config = {
            "target_duration_minutes": 60,
            "special_tags": [],
            "must_include_track_ids": [],
        }
        
        # Run twice with same spec (same episode_id = same seed)
        side_a1, side_b1 = generate_playlist_for_episode(
            spec=spec,
            library_index=library_index,
            config=config,
            history=None,
        )
        
        side_a2, side_b2 = generate_playlist_for_episode(
            spec=spec,
            library_index=library_index,
            config=config,
            history=None,
        )
        
        # Should produce same result (deterministic)
        assert len(side_a1) == len(side_a2)
        assert len(side_b1) == len(side_b2)
        # File paths should match (same selection)
        assert [t["file_path"] for t in side_a1] == [t["file_path"] for t in side_a2]
        assert [t["file_path"] for t in side_b1] == [t["file_path"] for t in side_b2]


class TestAssetContract:
    """Test that asset contract is enforced."""
    
    def test_asset_contract_checker_init(self, test_tmp_dir):
        """Test checking asset contract for init stage."""
        episode_dir = test_tmp_dir / "channels" / "kat" / "output" / "kat_20241201"
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        config = get_config()
        config.channels_root = test_tmp_dir / "channels"
        paths = build_asset_paths(spec, config)
        
        # Check init stage
        has_playlist = paths.playlist_csv.exists()
        has_recipe = paths.recipe_json.exists()
        
        assert has_playlist is False
        assert has_recipe is False
        
        # Create files
        paths.playlist_csv.write_text("test")
        paths.recipe_json.write_text("{}")
        
        has_playlist = paths.playlist_csv.exists()
        has_recipe = paths.recipe_json.exists()
        
        assert has_playlist is True
        assert has_recipe is True
    
    def test_asset_contract_checker_all_stages(self, test_tmp_dir):
        """Test checking asset contract for all stages."""
        episode_dir = test_tmp_dir / "channels" / "kat" / "output" / "kat_20241201"
        episode_dir.mkdir(parents=True, exist_ok=True)
        
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        config = get_config()
        config.channels_root = test_tmp_dir / "channels"
        paths = build_asset_paths(spec, config)
        
        # Create all required files
        paths.playlist_csv.write_text("test")
        paths.recipe_json.write_text("{}")
        paths.cover_png.write_bytes(b"fake png")
        paths.youtube_title_txt.write_text("Title")
        paths.youtube_description_txt.write_text("Desc")
        paths.youtube_tags_txt.write_text("tag1\ntag2")
        paths.youtube_srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nTest")
        paths.final_mix_mp3.write_bytes(b"fake audio")
        paths.timeline_csv.write_text("test")
        paths.youtube_mp4.write_bytes(b"fake video")
        paths.render_complete_flag.write_text("")
        
        # Verify all exist
        assert paths.playlist_csv.exists()
        assert paths.recipe_json.exists()
        assert paths.cover_png.exists()
        assert paths.youtube_title_txt.exists()
        assert paths.youtube_description_txt.exists()
        assert paths.youtube_tags_txt.exists()
        assert paths.youtube_srt.exists()
        assert paths.final_mix_mp3.exists()
        assert paths.timeline_csv.exists()
        assert paths.youtube_mp4.exists()
        assert paths.render_complete_flag.exists()
        
        # State should show all complete
        state = detect_episode_state_from_filesystem(spec, paths)
        assert state.stage_completed[StageName.INIT] is True
        assert state.stage_completed[StageName.TEXT_BASE] is True
        assert state.stage_completed[StageName.COVER] is True
        assert state.stage_completed[StageName.MIX] is True
        assert state.stage_completed[StageName.TEXT_SRT] is True
        assert state.stage_completed[StageName.RENDER] is True
        assert state.current_stage is None  # All done


class TestInitStageRealGeneration:
    """Test that INIT stage actually produces playlist.csv and recipe.json files."""
    
    def test_init_episode_produces_files(self, test_tmp_dir):
        """Test that init_episode actually generates playlist.csv and recipe.json with valid content."""
        # Setup: Create fake library
        library_dir = test_tmp_dir / "channels" / "kat" / "library"
        library_dir.mkdir(parents=True, exist_ok=True)
        
        # Create fake audio files
        for i in range(10):
            (library_dir / f"song_{i:02d}.mp3").write_bytes(b"fake audio data")
        
        # Create episode spec
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        
        # Setup config
        config = get_config()
        config.channels_root = test_tmp_dir / "channels"
        set_config(config)
        
        # Build paths
        paths = build_asset_paths(spec, config)
        
        # Ensure output directory doesn't exist yet
        if paths.episode_output_dir.exists():
            shutil.rmtree(paths.episode_output_dir)
        
        # Run init_episode
        result = asyncio.run(init_episode(spec, paths))
        
        # Assert success
        assert result.success, f"init_episode failed: {result.error_message}"
        assert result.stage == StageName.INIT
        
        # Assert files exist at correct paths
        assert paths.playlist_csv.exists(), f"playlist.csv not found at {paths.playlist_csv}"
        assert paths.recipe_json.exists(), f"recipe.json not found at {paths.recipe_json}"
        
        # Assert playlist.csv has content
        playlist_content = paths.playlist_csv.read_text(encoding="utf-8")
        assert len(playlist_content) > 0, "playlist.csv is empty"
        assert "Section" in playlist_content, "playlist.csv missing header"
        assert "Track" in playlist_content, "playlist.csv missing track entries"
        assert spec.episode_id in playlist_content, "playlist.csv missing episode_id"
        
        # Assert recipe.json has valid JSON and required fields
        import json
        recipe = json.loads(paths.recipe_json.read_text(encoding="utf-8"))
        assert recipe["episode_id"] == spec.episode_id
        assert recipe["channel_id"] == spec.channel_id
        assert "assets" in recipe
        assert "tracks" in recipe["assets"]
        assert len(recipe["assets"]["tracks"]) > 0, "recipe.json has no tracks"
        
        # Verify state detection sees INIT as complete
        state = detect_episode_state_from_filesystem(spec, paths)
        assert state.stage_completed[StageName.INIT] is True
        assert state.current_stage == StageName.TEXT_BASE  # Next stage
    
    def test_init_episode_idempotent(self, test_tmp_dir):
        """Test that calling init_episode twice doesn't duplicate or corrupt files."""
        # Setup: Create fake library
        library_dir = test_tmp_dir / "channels" / "kat" / "library"
        library_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(10):
            (library_dir / f"song_{i:02d}.mp3").write_bytes(b"fake audio")
        
        spec = EpisodeSpec(channel_id="kat", episode_id="kat_20241201")
        config = get_config()
        config.channels_root = test_tmp_dir / "channels"
        set_config(config)
        paths = build_asset_paths(spec, config)
        
        # First run
        result1 = asyncio.run(init_episode(spec, paths))
        assert result1.success
        
        # Capture first run content
        playlist_content1 = paths.playlist_csv.read_text(encoding="utf-8")
        recipe_content1 = paths.recipe_json.read_text(encoding="utf-8")
        
        # Second run (should skip)
        result2 = asyncio.run(init_episode(spec, paths))
        assert result2.success
        
        # Content should be identical (idempotent)
        playlist_content2 = paths.playlist_csv.read_text(encoding="utf-8")
        recipe_content2 = paths.recipe_json.read_text(encoding="utf-8")
        
        assert playlist_content1 == playlist_content2, "playlist.csv changed on second run"
        assert recipe_content1 == recipe_content2, "recipe.json changed on second run"


@pytest.fixture
def test_tmp_dir():
    """Create a temporary directory for tests."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)

