from __future__ import annotations

import os
from pathlib import Path
import textwrap

import pytest

from src.configuration import AppConfig, ConfigError


def write_file(path: Path, content: str) -> Path:
    text = textwrap.dedent(content).strip()
    path.write_text(text + "\n", encoding="utf-8")
    return path


def test_load_unified_configuration(tmp_path: Path) -> None:
    config_path = write_file(
        tmp_path / "config.yaml",
        """
        library:
          song_library_root: "./data/library"
          audio_extensions:
            - .mp3
            - .wav
        paths:
          output_dir: "./output"
          sfx_dir: "./assets/sfx"
        api:
          provider: openai
          keys:
            openai: test-key
        """,
    )

    config = AppConfig.load(config_path=config_path, env_file=False, fallback_legacy=False)

    assert config.library.song_library_root == Path("./data/library")
    assert config.library.audio_extensions == (".mp3", ".wav")
    assert config.paths.output_dir == Path("./output")
    assert config.api.get_key("openai") == "test-key"
    assert config.web.host == "127.0.0.1"
    assert config.web.access_token is None


def test_promotes_legacy_library_settings(tmp_path: Path) -> None:
    legacy_path = write_file(
        tmp_path / "library_settings.yml",
        """
        song_library_root: "./legacy_library"
        audio_extensions:
          - mp3
          - wav
        """,
    )

    config = AppConfig.load(config_path=legacy_path, env_file=False, fallback_legacy=False)

    assert config.library.song_library_root == Path("./legacy_library")
    # Legacy extensions should be normalized with a leading dot.
    assert ".mp3" in config.library.audio_extensions
    assert ".wav" in config.library.audio_extensions
    assert config.web.port == 8080


def test_environment_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = write_file(
        tmp_path / "config.yaml",
        """
        library:
          song_library_root: "./data/library"
        """,
    )
    monkeypatch.setenv("KATREC_LIBRARY_SONG_LIBRARY_ROOT", "/override/library")

    config = AppConfig.load(config_path=config_path, env_file=False, fallback_legacy=False)

    assert config.library.song_library_root == Path("/override/library")


def test_dotenv_support(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = write_file(
        tmp_path / "config.yaml",
        """
        library:
          song_library_root: "${LIBRARY_ROOT}"
        """,
    )
    env_file = write_file(
        tmp_path / ".env",
        """
        LIBRARY_ROOT=/dotenv/library
        """,
    )
    # Ensure the value is not already present to verify `.env` injection.
    monkeypatch.delenv("LIBRARY_ROOT", raising=False)

    config = AppConfig.load(config_path=config_path, env_file=env_file, fallback_legacy=False)

    assert config.library.song_library_root == Path("/dotenv/library")


def test_missing_library_root_raises(tmp_path: Path) -> None:
    config_path = write_file(
        tmp_path / "config.yaml",
        """
        library:
          song_library_root: ""
        """,
    )

    with pytest.raises(ConfigError):
        AppConfig.load(config_path=config_path, env_file=False, fallback_legacy=False)


def test_web_config_overrides(tmp_path: Path) -> None:
    config_path = write_file(
        tmp_path / "config.yaml",
        """
        library:
          song_library_root: "./data/library"
        web:
          host: "0.0.0.0"
          port: 9090
          access_token: "secret"
          allowed_hosts:
            - "127.0.0.1"
            - "192.168.1.2"
        """,
    )

    config = AppConfig.load(config_path=config_path, env_file=False, fallback_legacy=False)

    assert config.web.host == "0.0.0.0"
    assert config.web.port == 9090
    assert config.web.access_token == "secret"
    assert config.web.allowed_hosts == ("127.0.0.1", "192.168.1.2")
