"""
Unified configuration loader for Kat Records Studio.

This module consolidates scattered configuration files into a single
`config/config.yaml` entry point while keeping backward compatibility with the
legacy configuration layout (`config/library_settings.yml`, `config/api_config.json`,
etc.).  It also supports optional `.env` files and environment variable overrides
using the `KATREC_` prefix.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import yaml

__all__ = [
    "AppConfig",
    "LibraryConfig",
    "PathsConfig",
    "WorkflowConfig",
    "ApiConfig",
    "WebConfig",
    "ConfigError",
]


class ConfigError(RuntimeError):
    """Raised when the configuration file is missing or malformed."""


@dataclass(slots=True)
class LibraryConfig:
    """Settings describing the local music library."""

    song_library_root: Path
    output_catalog: Path = Path("data/song_library.csv")
    usage_log: Path = Path("data/song_usage.csv")
    audio_extensions: tuple[str, ...] = (
        ".mp3",
        ".wav",
        ".flac",
        ".m4a",
        ".aac",
    )

    def validate(self) -> None:
        """Basic validation ensuring the library root is configured."""
        if not self.song_library_root:
            raise ConfigError("Missing `library.song_library_root` configuration.")


@dataclass(slots=True)
class PathsConfig:
    """Generic paths used across the project."""

    output_dir: Path = Path("output")
    sfx_dir: Path = Path("assets/sfx")


@dataclass(slots=True)
class WorkflowConfig:
    """Workflow automation settings."""

    config_file: Path = Path("config/workflow.yml")
    auto_sync: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ApiConfig:
    """External API configuration."""

    provider: str = "openai"
    keys: Dict[str, str] = field(default_factory=dict)

    def get_key(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self.keys.get(name, default)


@dataclass(slots=True)
class WebConfig:
    """Settings related to the workflow web console."""

    host: str = "127.0.0.1"
    port: int = 8080
    auto_open_browser: bool = True
    access_token: Optional[str] = None
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "::1", "localhost")


DEFAULTS: Dict[str, Any] = {
    "library": {
        "song_library_root": "",
        "output_catalog": "data/song_library.csv",
        "usage_log": "data/song_usage.csv",
        "audio_extensions": [
            ".mp3",
            ".wav",
            ".flac",
            ".m4a",
            ".aac",
        ],
    },
    "paths": {
        "output_dir": "output",
        "sfx_dir": "assets/sfx",
    },
    "workflow": {
        "config_file": "config/workflow.yml",
        "auto_sync": {},
    },
    "api": {
        "provider": "openai",
        "keys": {},
    },
    "web": {
        "host": "127.0.0.1",
        "port": 8080,
        "auto_open_browser": True,
        "access_token": None,
        "allowed_hosts": ["127.0.0.1", "::1", "localhost"],
    },
}


def load_dotenv(env_path: Path) -> None:
    """
    Minimal `.env` loader that populates os.environ.

    Only sets variables that are not already defined in the environment to
    avoid overriding explicit user settings.
    """
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip().strip("'\"")
        # Allow escaped newlines to remain intact
        value = value.replace("\\n", "\n")
        os.environ.setdefault(key, value)


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file {path} must contain a mapping at the top level.")
    return data


def _merge_dicts(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries.

    Values from `override` take precedence. Missing keys fall back to `base`.
    """
    merged: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, Mapping):
            merged[key] = _merge_dicts(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


LEGACY_LIBRARY_FIELDS = {"song_library_root", "output_catalog", "usage_log", "audio_extensions"}
LEGACY_API_FIELDS = {"provider", "keys"}


def _coerce_legacy_layout(data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Promote legacy flat configuration keys to their new sections.

    For example, a file containing `song_library_root: ...` at the top level will
    be converted to `{"library": {...}}`.
    """
    coerced: Dict[str, Any] = dict(data)

    if "library" not in coerced:
        legacy_library = {key: coerced.pop(key) for key in list(coerced.keys()) if key in LEGACY_LIBRARY_FIELDS}
        if legacy_library:
            coerced["library"] = legacy_library

    if "api" not in coerced and LEGACY_API_FIELDS.issubset(coerced.keys()):
        legacy_api = {key: coerced.pop(key) for key in LEGACY_API_FIELDS if key in coerced}
        if legacy_api:
            coerced["api"] = legacy_api

    return coerced


ENV_PREFIX = "KATREC"


def _apply_env_overrides(payload: Any, path: Iterable[str] = ()) -> Any:
    """
    Apply environment overrides and `${VAR}` substitutions recursively.

    Environment variable naming convention:
        KATREC_<SECTION>_<SUBKEY>=value

    Strings support `${VAR}` placeholders via `os.path.expandvars`.
    """
    if isinstance(payload, Mapping):
        updated: Dict[str, Any] = {}
        for key, value in payload.items():
            key_path = tuple(path) + (key,)
            env_key = "_".join((ENV_PREFIX, *(segment.upper() for segment in key_path)))
            if env_key in os.environ:
                updated[key] = _coerce_value(os.environ[env_key])
            else:
                updated[key] = _apply_env_overrides(value, key_path)
        return updated

    if isinstance(payload, list):
        return [_apply_env_overrides(item, path) for item in payload]

    if isinstance(payload, str):
        expanded = os.path.expandvars(payload)
        return _coerce_value(expanded)

    return payload


_BOOL_PATTERN = re.compile(r"^(true|false|yes|no|on|off)$", re.IGNORECASE)
_INT_PATTERN = re.compile(r"^-?\d+$")
_FLOAT_PATTERN = re.compile(r"^-?\d+\.\d+$")


def _coerce_value(raw: str) -> Any:
    """Attempt to coerce string values to primitive Python types."""
    lower = raw.lower()
    if _BOOL_PATTERN.match(lower):
        return lower in {"true", "yes", "on"}
    if _INT_PATTERN.match(raw):
        try:
            return int(raw)
        except ValueError:
            return raw
    if _FLOAT_PATTERN.match(raw):
        try:
            return float(raw)
        except ValueError:
            return raw
    return raw


def _as_path(value: Any, *, allow_empty: bool = False) -> Path:
    if value in ("", None):
        if allow_empty:
            return Path("")
        raise ConfigError("Path value cannot be empty.")
    if isinstance(value, Path):
        return value
    if not isinstance(value, str):
        raise ConfigError(f"Expected path-like string, got {type(value)!r}")
    return Path(str(value)).expanduser()


class AppConfig:
    """
    High-level configuration facade.

    Usage:
        config = AppConfig.load()
        library_root = config.library.song_library_root
    """

    DEFAULT_PATH = Path("config/config.yaml")
    LEGACY_LIBRARY_PATH = Path("config/library_settings.yml")
    LEGACY_API_PATH = Path("config/api_config.json")

    def __init__(
        self,
        library: LibraryConfig,
        paths: PathsConfig,
        workflow: WorkflowConfig,
        api: ApiConfig,
        web: WebConfig,
    ) -> None:
        self.library = library
        self.paths = paths
        self.workflow = workflow
        self.api = api
        self.web = web

    @classmethod
    def load(
        cls,
        config_path: Path | str | None = None,
        *,
        env_file: Path | str | bool | None = None,
        fallback_legacy: bool = True,
    ) -> "AppConfig":
        """
        Load the application configuration.

        `config_path` defaults to `config/config.yaml` or the value from the
        `KATREC_CONFIG` environment variable. If the unified configuration file
        is missing and `fallback_legacy` is enabled, legacy configuration files
        are used to build a composite configuration.
        """
        if env_file is False:
            pass
        elif env_file is None:
            load_dotenv(Path(".env"))
        else:
            load_dotenv(Path(env_file))

        path = cls._resolve_config_path(config_path)
        data: Dict[str, Any] | None = None

        if path and path.exists():
            data = _read_yaml(path)
            data = _coerce_legacy_layout(data)
        elif fallback_legacy:
            data = cls._load_from_legacy()
        else:
            target = path or cls.DEFAULT_PATH
            raise ConfigError(f"Configuration file not found: {target}")

        merged = _merge_dicts(DEFAULTS, data or {})
        merged = _apply_env_overrides(merged)
        return cls.from_dict(merged)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AppConfig":
        """Instantiate an AppConfig from a dictionary payload."""
        try:
            library_section = payload["library"]
        except KeyError as exc:
            raise ConfigError("Missing 'library' section in configuration.") from exc

        library = LibraryConfig(
            song_library_root=_as_path(library_section.get("song_library_root"), allow_empty=False).expanduser(),
            output_catalog=_as_path(library_section.get("output_catalog", "data/song_library.csv"), allow_empty=True),
            usage_log=_as_path(library_section.get("usage_log", "data/song_usage.csv"), allow_empty=True),
            audio_extensions=tuple(_normalize_extensions(library_section.get("audio_extensions", []))),
        )

        paths_section = payload.get("paths", {})
        paths = PathsConfig(
            output_dir=_as_path(paths_section.get("output_dir", "output"), allow_empty=True),
            sfx_dir=_as_path(paths_section.get("sfx_dir", "assets/sfx"), allow_empty=True),
        )

        workflow_section = payload.get("workflow", {})
        workflow = WorkflowConfig(
            config_file=_as_path(workflow_section.get("config_file", "config/workflow.yml"), allow_empty=True),
            auto_sync=dict(workflow_section.get("auto_sync", {}) or {}),
        )

        api_section = payload.get("api", {})
        api = ApiConfig(
            provider=str(api_section.get("provider", "openai") or "openai"),
            keys=_normalize_api_keys(api_section.get("keys", {})),
        )

        web_section = payload.get("web", {})
        web = WebConfig(
            host=str(web_section.get("host", "127.0.0.1") or "127.0.0.1"),
            port=int(web_section.get("port", 8080) or 8080),
            auto_open_browser=bool(web_section.get("auto_open_browser", True)),
            access_token=_optional_str(web_section.get("access_token")),
            allowed_hosts=tuple(_ensure_list_of_str(web_section.get("allowed_hosts", DEFAULTS["web"]["allowed_hosts"]))),
        )

        library.validate()
        return cls(library=library, paths=paths, workflow=workflow, api=api, web=web)

    @classmethod
    def _resolve_config_path(cls, config_path: Path | str | None) -> Path:
        if config_path:
            return Path(config_path)
        if env_path := os.environ.get("KATREC_CONFIG"):
            return Path(env_path)
        return cls.DEFAULT_PATH

    @classmethod
    def _load_from_legacy(cls) -> Dict[str, Any]:
        """Build a config dictionary using legacy configuration files."""
        payload: Dict[str, Any] = {}

        if cls.LEGACY_LIBRARY_PATH.exists():
            payload["library"] = _read_yaml(cls.LEGACY_LIBRARY_PATH)
        else:
            payload["library"] = {}

        if cls.LEGACY_API_PATH.exists():
            with cls.LEGACY_API_PATH.open("r", encoding="utf-8") as handle:
                try:
                    api_data = json.load(handle) or {}
                except json.JSONDecodeError as exc:
                    raise ConfigError(f"Failed to parse {cls.LEGACY_API_PATH}: {exc}") from exc
            payload["api"] = api_data

        # Keep default workflow config if available
        if DEFAULTS["workflow"]["config_file"]:
            payload.setdefault("workflow", {})["config_file"] = DEFAULTS["workflow"]["config_file"]

        return payload

    def as_dict(self) -> Dict[str, Any]:
        """Return the configuration as a dictionary of primitive types."""
        return {
            "library": {
                "song_library_root": str(self.library.song_library_root),
                "output_catalog": str(self.library.output_catalog),
                "usage_log": str(self.library.usage_log),
                "audio_extensions": list(self.library.audio_extensions),
            },
            "paths": {
                "output_dir": str(self.paths.output_dir),
                "sfx_dir": str(self.paths.sfx_dir),
            },
            "workflow": {
                "config_file": str(self.workflow.config_file),
                "auto_sync": dict(self.workflow.auto_sync),
            },
            "api": {
                "provider": self.api.provider,
                "keys": dict(self.api.keys),
            },
            "web": {
                "host": self.web.host,
                "port": self.web.port,
                "auto_open_browser": self.web.auto_open_browser,
                "access_token": self.web.access_token,
                "allowed_hosts": list(self.web.allowed_hosts),
            },
        }


def _normalize_extensions(values: Any) -> Iterable[str]:
    if not values:
        return DEFAULTS["library"]["audio_extensions"]  # type: ignore[return-value]
    if isinstance(values, str):
        values = [values]
    normalized = []
    for item in values:
        if not item:
            continue
        ext = str(item).strip()
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.append(ext.lower())
    return normalized


def _normalize_api_keys(keys: Any) -> Dict[str, str]:
    if not keys:
        return {}
    if isinstance(keys, Mapping):
        return {str(k): str(v) for k, v in keys.items()}
    raise ConfigError("`api.keys` must be a mapping of provider -> key.")


def _ensure_list_of_str(values: Any) -> Iterable[str]:
    if values is None:
        return []
    if isinstance(values, (list, tuple, set)):
        return [str(item) for item in values if item is not None]
    if isinstance(values, str):
        return [values]
    raise ConfigError("Expected a list of strings for allowed hosts.")


def _optional_str(value: Any) -> Optional[str]:
    if value in (None, "", False):
        return None
    return str(value)
