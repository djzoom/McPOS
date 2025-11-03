import csv
from pathlib import Path
import pytest

import scripts.local_picker.create_mixtape as mixtape
from src.creation_utils import generate_poetic_title, get_dominant_color


REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_IMG_DIR = REPO_ROOT / "assets/design/images"


def test_parse_duration_variants():
    assert mixtape.parse_duration("215") == 215
    assert mixtape.parse_duration("3:45") == 225
    assert mixtape.parse_duration("1:02:03") == 3723
    with pytest.raises(ValueError):
        mixtape.parse_duration("xx:yy")


def test_select_tracks_with_reduced_thresholds(monkeypatch):
    # Reduce thresholds for fast test
    monkeypatch.setattr(mixtape, "MIN_DURATION", 60, raising=True)
    monkeypatch.setattr(mixtape, "MAX_DURATION", 120, raising=True)

    # Build small track pool
    tracks = [
        mixtape.Track(title=f"t{i}", duration_sec=d)
        for i, d in enumerate([30, 35, 40, 45, 50, 55, 60, 65], start=1)
    ]

    side_a, side_b = mixtape.select_tracks(tracks, seed=123)

    assert sum(t.duration_sec for t in side_a) >= 60
    assert sum(t.duration_sec for t in side_b) >= 60
    # Disjoint selection
    assert set(id(t) for t in side_a).isdisjoint(set(id(t) for t in side_b))


def test_build_timelines_structure():
    side_a = [mixtape.Track("A1", 100), mixtape.Track("A2", 90)]
    side_b = [mixtape.Track("B1", 80)]
    needle, clean = mixtape.build_timelines(side_a, side_b)

    # Starts with needle events for each side
    assert any(e["side"] == "A" and e["description"] == "Needle On Vinyl Record" for e in needle)
    assert any(e["side"] == "B" and e["description"] == "Needle On Vinyl Record" for e in needle)

    # No Vinyl Noise after last track of a side
    last_a_idx = max(i for i, e in enumerate(needle) if e["side"] == "A")
    assert needle[last_a_idx]["description"] != "Vinyl Noise"

    # Clean timeline only includes tracks
    assert all(e["description"] not in {"Vinyl Noise", "Silence", "Needle On Vinyl Record"} for e in clean)


def test_export_playlist_writes_csv(tmp_path):
    side_a = [mixtape.Track("A1", 100)]
    side_b = [mixtape.Track("B1", 120)]
    title = "Test Title"
    color_hex = "aabbcc"
    prompt = "prompt"
    needle, clean = mixtape.build_timelines(side_a, side_b)

    # Redirect output dir
    monkey_output = tmp_path / "playlists"
    monkey_output.mkdir(parents=True, exist_ok=True)
    original_dir = mixtape.OUTPUT_PLAYLIST_DIR
    try:
        setattr(mixtape, "OUTPUT_PLAYLIST_DIR", monkey_output)
        csv_path = mixtape.export_playlist(side_a, side_b, title, color_hex, prompt, needle, clean)
    finally:
        setattr(mixtape, "OUTPUT_PLAYLIST_DIR", original_dir)

    assert csv_path.exists()
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        headers = next(reader)
        assert headers[:3] == ["Section", "Field", "Value"]


def test_compose_cover_smoke(tmp_path):
    # Use a real image from assets
    images = list(ASSETS_IMG_DIR.glob("*.png")) + list(ASSETS_IMG_DIR.glob("*.jpg"))
    assert images, "需要至少一张测试图片放在 assets/design/images/"
    image_path = images[0]

    side_a = [mixtape.Track("A1", 100), mixtape.Track("A2", 95)]
    side_b = [mixtape.Track("B1", 90)]
    color_hex = "a97c5a"  # arbitrary warm color

    # Redirect output dir
    monkey_cover = tmp_path / "cover"
    monkey_cover.mkdir(parents=True, exist_ok=True)
    original_dir = mixtape.OUTPUT_COVER_DIR
    try:
        setattr(mixtape, "OUTPUT_COVER_DIR", monkey_cover)
        out = mixtape.compose_cover(
            title="Test Cover",
            side_a=side_a,
            side_b=side_b,
            color_hex=color_hex,
            seed=42,
            output_name="test_cover.png",
            image_path=image_path,
        )
    finally:
        setattr(mixtape, "OUTPUT_COVER_DIR", original_dir)

    assert out.exists()
    assert out.suffix == ".png"


def test_generate_poetic_title_determinism():
    img_name = "0xgarfield_cat_window_rain.png"
    dominant = (170, 120, 80)
    keywords = ["dream", "sleep", "calm"]
    t1 = generate_poetic_title(img_name, dominant, keywords, seed=1234)
    t2 = generate_poetic_title(img_name, dominant, keywords, seed=1234)
    assert t1 == t2
    assert isinstance(t1, str) and len(t1) > 0


def test_title_from_playlist_and_image(tmp_path):
    """给定歌单CSV与图片，生成可复现的标题。"""
    # 1) 准备一个最小歌单CSV（仅需 Title 列即可）
    playlist_csv = tmp_path / "mini_playlist.csv"
    playlist_csv.write_text(
        """Section,Field,Value,Side,Order,Title,Duration,DurationSeconds,Timeline,Timestamp,Description
Track,,,,,Midnight Window,3:21,201,,,
Track,,,,,Soft Paws,2:58,178,,,
Track,,,,,Quiet Rain,4:02,242,,,
""",
        encoding="utf-8",
    )
    # 从CSV读取标题
    import csv as _csv
    with playlist_csv.open(encoding="utf-8") as fh:
        reader = _csv.DictReader(fh)
        song_titles = [row["Title"] for row in reader if row.get("Title")]

    # 2) 选择一张实际存在的测试图片
    images = list(ASSETS_IMG_DIR.glob("*.png")) + list(ASSETS_IMG_DIR.glob("*.jpg"))
    assert images, "需要至少一张测试图片放在 assets/design/images/"
    image_path = images[0]

    # 3) 提取主导色并生成标题（与生产流程一致）
    dom = get_dominant_color(image_path)
    seed = 20251030
    title1 = generate_poetic_title(image_path.name, dom, song_titles, seed)
    title2 = generate_poetic_title(image_path.name, dom, song_titles, seed)

    # 4) 断言：标题非空、确定性（同参同seed一致）
    assert isinstance(title1, str) and len(title1) > 0
    assert title1 == title2


