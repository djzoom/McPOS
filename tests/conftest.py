from __future__ import annotations

from pathlib import Path

import pytest

from mcpos.config import McPOSConfig, get_config, set_config
from tests.helpers import make_test_config, make_tone_mp3, write_seed_png, write_sg_config


@pytest.fixture
def isolated_mcpos(tmp_path: Path) -> McPOSConfig:
    old_config = get_config()
    config = make_test_config(tmp_path)
    config.channels_root.mkdir(parents=True, exist_ok=True)
    config.images_pool_available.mkdir(parents=True, exist_ok=True)
    config.images_pool_used.mkdir(parents=True, exist_ok=True)
    write_seed_png(config.images_pool_available / "cover_seed.png")
    set_config(config)
    try:
        yield config
    finally:
        set_config(old_config)


@pytest.fixture
def sg_workspace(isolated_mcpos: McPOSConfig) -> dict[str, Path]:
    sg_root = isolated_mcpos.channels_root / "sg"
    library_root = sg_root / "library" / "songs"
    assets_root = sg_root / "assets"
    catalog_root = sg_root / "catalog"
    vo_dir = isolated_mcpos.repo_root / "sg_vo_assets"

    for path in [
        sg_root / "config",
        library_root,
        assets_root,
        assets_root / "video",
        catalog_root,
        vo_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)

    return {
        "sg_root": sg_root,
        "library_root": library_root,
        "assets_root": assets_root,
        "catalog_root": catalog_root,
        "vo_dir": vo_dir,
    }
