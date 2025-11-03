# Kat Rec 素材与数据总览

本项目已经为唱片制作流程预置统一目录结构，以下说明各目录用途与放置规范，便于团队协同与自动化脚本引用。

## assets
- `assets/design/`：放置 4K 封面合成所需的背景、前景等透明图层素材。当前包含 `TopCover.png` 与 `TopCover_HD.png`，背景建议脚本随机生成十六进制纯色，不再额外存档；新增两张参考样式截图（`截屏2025-10-29 上午5.08.17.png`、`截屏2025-10-29 上午5.08.33.png`）供排版灵感与风格对齐。
- `assets/fonts/`：专用字体集合，供 Pillow 制作字体排版时选择使用。请在字体授权允许的前提下添加。
- `assets/sfx/`：音效素材（唱针落下、黑胶底噪等）。初始为空，可根据需要补充。

## data
- `data/google_sheet/`：存放从 Google Sheet 导出的歌库快照与曲目清单，当前包含 `Kat Record Lo-Fi Radio Songs Database - tracklist.tsv`。
- `data/song_library.csv`：自动生成的歌库索引文件（由 `generate_song_library.py` 生成）。
- `data/metrics.json`：指标数据（由系统自动生成）。

**注意**：
- 歌曲使用历史记录现在从 `config/schedule_master.json` 动态查询，不再需要独立文件。
- 自动生成的 `data/song_library.csv` 在 `.gitignore` 中，避免将动态文件提交到版本库。

## scripts
- `scripts/selection/`：远程选歌相关脚本（如 Google Apps Script），目前已有 `Google Apps Script.gs.txt`。
- `scripts/local_picker/`：本地化选歌逻辑的 Python 或其他语言实现，目前提供  
  - `generate_song_library.py`：生成/监听曲库总表。  
  - `create_mixtape.py`：快速产出符合 Google Script 规范的 AB 面歌单、标题、封面及提示词，CSV 中包含曲目列表、Side 总时长、封面 Prompt 以及带/不带唱针的时间轴事件。  
  - `remix_mixtape.py`：读取结构化歌单 CSV，自动匹配外部歌库曲目，并以 20% 音量的 `Needle_Start.mp3` / `Vinyl_Noise.mp3` 交叉淡入淡出（含 crossfade）生成 Side A/B 混音 MP3。

## config
- `config/library_settings.yml`：定义本地歌库根路径、输出文件路径及支持的音频扩展名。

## output
- `output/{id_str}_{title}/`：每期节目的统一输出目录，包含：
  - `{id_str}_cover.png`：自动化生成的 4K 专辑封面
  - `{id_str}_playlist.csv`：歌单文件
  - `{id_str}_full_mix.mp3`：混音完成的长音频
  - `{id_str}_youtube.mp4`：封面静帧 + 混音音频合成的视频文件
  - `{id_str}_youtube.srt`：与视频同步的歌曲切换字幕
  - `{id_str}_youtube_description.txt`：YouTube描述
  - `{id_str}_youtube_upload.csv`：YouTube上传信息

## 备注
- 若需长期保存的配置或模板，可在 `config/` 下建立自定义 YAML/JSON，便于脚本读取。
- `scripts/local_picker/generate_song_library.py --watch` 可监听歌库目录新增/删除文件并自动更新总表，便于在选曲前快速刷新库信息。
- `python scripts/local_picker/create_mixtape.py --seed <数字>` 可从最新曲库选出一套 AB 面歌单，并生成可直接用于封面/SEO 的标题与提示词，同时在 `output/` 下写出歌单 CSV 与示例封面 PNG。
- 脚本与素材新增后，建议更新本文件，保持团队对目录结构的共识。
