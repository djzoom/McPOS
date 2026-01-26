# 资产生成函数清单

本文档列出项目中所有用于生成各类资产的函数和方法，按资产类型分组。

---

## 1. 封面图像文件

### 1.1 generate_cover
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `async def generate_cover(request: GenerateCoverRequest) -> Dict`
- **输入参数**:
  - `request.episode_id`: 期数ID
  - `request.channel_id`: 频道ID
- **输出形式**: 返回字典，包含 `cover_path`（封面PNG文件路径，格式：`{episode_id}_cover.png`）
- **是否使用 Plugin 系统**: 是，通过 `CoverPlugin` 包装调用
- **是否依赖 Legacy Stage Executor**: 否，使用新的自动化流程

### 1.2 compose_cover
- **模块路径**: `scripts/local_picker/create_mixtape.py`
- **函数签名**: `def compose_cover(title: str, side_a: Sequence[Track], side_b: Sequence[Track], color_hex: str, seed: int, layout: CoverLayoutConfig | None = None, spine_x: int | None = None, output_name: str | None = None, font_name: str | None = None, output_size: Tuple[int, int] = CANVAS_SIZE_4K, image_path: Path | None = None, text_style: str = "noise", output_dir: Path | None = None, id_str: str | None = None) -> Path`
- **输入参数**:
  - `title`: 专辑标题
  - `side_a`, `side_b`: Side A 和 Side B 的曲目列表
  - `color_hex`: 背景色（十六进制）
  - `seed`: 随机种子
  - `image_path`: 主图片路径
  - `output_dir`: 输出目录
  - 其他参数：布局配置、字体、输出尺寸等
- **输出形式**: 返回封面PNG文件路径（4K分辨率，7680x4320）
- **是否使用 Plugin 系统**: 否，这是底层合成函数
- **是否依赖 Legacy Stage Executor**: 否

### 1.3 _try_api_title
- **模块路径**: `scripts/local_picker/create_mixtape.py`
- **函数签名**: `def _try_api_title(image_filename: str, dominant_rgb: Tuple[int, int, int], playlist_keywords: List[str], seed: int, api_key: str, base_url: str, model: str, provider: str = "openai") -> str | None`
- **输入参数**:
  - `image_filename`: 图片文件名
  - `dominant_rgb`: 主色调RGB值
  - `playlist_keywords`: 歌单关键词列表
  - `seed`: 随机种子
  - `api_key`, `base_url`, `model`, `provider`: API配置
- **输出形式**: 返回生成的标题字符串（最多7个词）
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 1.4 generate_poetic_title
- **模块路径**: `src/creation_utils.py`
- **函数签名**: `def generate_poetic_title(image_filename: str, dominant_color: Tuple[int, int, int], playlist_keywords: List[str], seed: int) -> str`
- **输入参数**:
  - `image_filename`: 图片文件名
  - `dominant_color`: 主色调RGB值
  - `playlist_keywords`: 歌单关键词列表
  - `seed`: 随机种子
- **输出形式**: 返回生成的标题字符串（不使用API，基于规则生成）
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 1.5 CoverPlugin.execute
- **模块路径**: `kat_rec_web/backend/t2r/plugins/cover_plugin.py`
- **函数签名**: `async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]`
- **输入参数**:
  - `context.episode_id`: 期数ID
  - `context.channel_id`: 频道ID
- **输出形式**: 返回执行结果字典，包含封面文件路径
- **是否使用 Plugin 系统**: 是，这是Plugin系统的实现
- **是否依赖 Legacy Stage Executor**: 否，使用新的Stageflow系统

---

## 2. 音频混音输出

### 2.1 remix_mixtape.py (main函数)
- **模块路径**: `scripts/local_picker/remix_mixtape.py`
- **函数签名**: `def main() -> None`
- **输入参数**: 通过命令行参数传入
  - `--playlist`: 歌单CSV文件路径
  - `--engine`: 混音引擎（ffmpeg）
  - `--audio_bitrate`: 音频比特率（默认320k）
- **输出形式**: 生成 `{episode_id}_full_mix.mp3` 文件（320kbps）
- **是否使用 Plugin 系统**: 否，这是独立脚本
- **是否依赖 Legacy Stage Executor**: 否

### 2.2 _execute_stage (remix阶段)
- **模块路径**: `kat_rec_web/backend/t2r/routes/plan.py`
- **函数签名**: `async def _execute_stage(stage: str, episode_id: str, channel_id: Optional[str] = None, recipe_path: Optional[str] = None, emit_events: bool = True, _skip_queue: bool = False) -> None`
- **输入参数**:
  - `stage`: 阶段名称（"remix"）
  - `episode_id`: 期数ID
  - `channel_id`: 频道ID
  - 其他参数：recipe路径、事件发射标志等
- **输出形式**: 生成 `{episode_id}_full_mix.mp3` 和 `{episode_id}_final_mix.mp3`（256kbps）
- **是否使用 Plugin 系统**: 否，直接调用脚本
- **是否依赖 Legacy Stage Executor**: 否，使用StageflowExecutor

### 2.3 RemixPlugin.execute
- **模块路径**: `kat_rec_web/backend/t2r/plugins/remix_plugin.py`
- **函数签名**: `async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]`
- **输入参数**:
  - `context.episode_id`: 期数ID
  - `context.channel_id`: 频道ID
- **输出形式**: 返回执行结果字典
- **是否使用 Plugin 系统**: 是，这是Plugin系统的实现
- **是否依赖 Legacy Stage Executor**: 否，内部使用StageflowExecutor

### 2.4 PlanRemixEngine.remix
- **模块路径**: `kat_rec_web/backend/t2r/services/episode_flow_adapters.py`
- **函数签名**: `async def remix(self, playlist_path: Path, episode_id: str, channel_id: str) -> Path`
- **输入参数**:
  - `playlist_path`: 歌单文件路径
  - `episode_id`: 期数ID
  - `channel_id`: 频道ID
- **输出形式**: 返回生成的音频文件路径
- **是否使用 Plugin 系统**: 否，这是EpisodeFlow的适配器
- **是否依赖 Legacy Stage Executor**: 否，调用 `_execute_stage_core`

### 2.5 EpisodeFlow.remix
- **模块路径**: `src/core/episode_flow.py`
- **函数签名**: `async def remix(self) -> None`
- **输入参数**: 无（使用实例的remix_engine）
- **输出形式**: 更新episode.paths["mix"]，生成音频文件
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否，使用Protocol-based依赖注入

---

## 3. 视频渲染输出

### 3.1 render_video_direct_from_playlist
- **模块路径**: `kat_rec_web/backend/t2r/utils/direct_video_render.py`
- **函数签名**: `async def render_video_direct_from_playlist(playlist_path: Path, cover_path: Path, output_video_path: Path, library_root: Path, sfx_dir: Path, extensions: List[str], audio_bitrate: str = "192k", lufs: float = -14.0, tp: float = -1.0, vinyl_noise_db: float = -18.0, needle_gain_db: float = -18.0, episode_id: Optional[str] = None) -> Path`
- **输入参数**:
  - `playlist_path`: 歌单CSV文件路径
  - `cover_path`: 封面图片路径
  - `output_video_path`: 输出视频路径
  - `library_root`: 音乐库根目录
  - `sfx_dir`: 音效目录
  - `extensions`: 音频文件扩展名列表
  - `audio_bitrate`: 音频比特率
  - `lufs`, `tp`: 音频响度参数
  - `vinyl_noise_db`, `needle_gain_db`: 音效增益参数
  - `episode_id`: 期数ID（用于检测final_mix.mp3）
- **输出形式**: 返回生成的视频文件路径（4K MP4，格式：`{episode_id}_youtube.mp4`）
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否，使用新的直接渲染流程

### 3.2 _execute_stage (render阶段)
- **模块路径**: `kat_rec_web/backend/t2r/routes/plan.py`
- **函数签名**: `async def _execute_stage(stage: str, episode_id: str, channel_id: Optional[str] = None, recipe_path: Optional[str] = None, emit_events: bool = True, _skip_queue: bool = False) -> None`
- **输入参数**:
  - `stage`: 阶段名称（"render"）
  - `episode_id`: 期数ID
  - `channel_id`: 频道ID
  - 其他参数：recipe路径、事件发射标志等
- **输出形式**: 生成 `{episode_id}_youtube.mp4` 和 `{episode_id}_render_complete.flag`
- **是否使用 Plugin 系统**: 否，直接调用渲染函数
- **是否依赖 Legacy Stage Executor**: 否，使用StageflowExecutor

### 3.3 render_episode
- **模块路径**: `scripts/render_video_original.py`
- **函数签名**: `def render_episode(episode_id: str, channel_id: str = "kat_lofi") -> bool`
- **输入参数**:
  - `episode_id`: 期数ID
  - `channel_id`: 频道ID
- **输出形式**: 返回布尔值表示成功与否，生成视频文件
- **是否使用 Plugin 系统**: 否，这是独立脚本
- **是否依赖 Legacy Stage Executor**: 是，这是旧版本的渲染函数

### 3.4 render_video_from_mp3
- **模块路径**: `scripts/render_video_from_mp3.py`
- **函数签名**: `async def render_video_from_mp3(episode_id: str, channel_id: str = "kat_lofi") -> bool`
- **输入参数**:
  - `episode_id`: 期数ID
  - `channel_id`: 频道ID
- **输出形式**: 返回布尔值，生成视频文件
- **是否使用 Plugin 系统**: 否，这是独立脚本
- **是否依赖 Legacy Stage Executor**: 是，这是旧版本的渲染函数

### 3.5 EpisodeFlow.render
- **模块路径**: `src/core/episode_flow.py`
- **函数签名**: `async def render(self) -> None`
- **输入参数**: 无（使用实例的render_engine）
- **输出形式**: 更新episode.paths["render"]，生成视频文件
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否，使用Protocol-based依赖注入

---

## 4. 文案描述和标题

### 4.1 generate_youtube_title_desc
- **模块路径**: `src/core/youtube_assets.py`
- **函数签名**: `def generate_youtube_title_desc(original_title: str, playlist_data: PlaylistDataDict, api_key: Optional[str] = None, api_base: Optional[str] = None, model: Optional[str] = None, logger: Optional[LoggerProtocol] = None) -> Tuple[str, str]`
- **输入参数**:
  - `original_title`: 原始专辑标题
  - `playlist_data`: 歌单数据字典（包含tracks_a, tracks_b, clean_timeline）
  - `api_key`, `api_base`, `model`: OpenAI API配置
  - `logger`: 日志记录器
- **输出形式**: 返回元组 `(title, description)`，两个字符串
- **是否使用 Plugin 系统**: 否，这是核心生成函数
- **是否依赖 Legacy Stage Executor**: 否

### 4.2 build_title_prompt
- **模块路径**: `src/core/youtube_assets.py`
- **函数签名**: `def build_title_prompt(original_title: str, total_tracks: int, tracks_a_count: int, tracks_b_count: int, track_titles: Optional[List[str]] = None) -> str`
- **输入参数**:
  - `original_title`: 原始专辑标题
  - `total_tracks`: 总曲目数
  - `tracks_a_count`, `tracks_b_count`: Side A和B的曲目数
  - `track_titles`: 曲目标题列表（可选）
- **输出形式**: 返回用于生成标题的prompt字符串
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 4.3 build_description_prompt
- **模块路径**: `src/core/youtube_assets.py`
- **函数签名**: `def build_description_prompt(original_title: str, total_tracks: int, tracks_a_count: int, tracks_b_count: int, track_list: str, tracklist_text: str) -> str`
- **输入参数**:
  - `original_title`: 原始专辑标题
  - `total_tracks`: 总曲目数
  - `tracks_a_count`, `tracks_b_count`: Side A和B的曲目数
  - `track_list`: 曲目列表文本
  - `tracklist_text`: 时间轴文本
- **输出形式**: 返回用于生成描述的prompt字符串
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 4.4 clean_youtube_description
- **模块路径**: `src/core/youtube_assets.py`
- **函数签名**: `def clean_youtube_description(description: str) -> str`
- **输入参数**:
  - `description`: 原始描述文本
- **输出形式**: 返回清理后的描述文本（移除markdown、分隔符等）
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 4.5 _filler_generate_youtube_title_desc
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `def _filler_generate_youtube_title_desc(original_title: str, playlist_data: Dict, api_key: Optional[str] = None, api_base: Optional[str] = None, model: Optional[str] = None) -> Tuple[str, str]`
- **输入参数**:
  - `original_title`: 原始专辑标题
  - `playlist_data`: 歌单数据字典
  - `api_key`, `api_base`, `model`: API配置
- **输出形式**: 返回元组 `(title, description)`
- **是否使用 Plugin 系统**: 否，这是包装函数
- **是否依赖 Legacy Stage Executor**: 否

### 4.6 regenerate_asset (asset_type="title" 或 "description")
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `async def regenerate_asset(request: RegenerateAssetRequest) -> Dict`
- **输入参数**:
  - `request.episode_id`: 期数ID
  - `request.channel_id`: 频道ID
  - `request.asset_type`: 资产类型（"title" 或 "description"）
  - `request.overwrite`: 是否覆盖已存在文件
- **输出形式**: 返回字典，包含生成的文件路径
  - Title: `{episode_id}_youtube_title.txt`
  - Description: `{episode_id}_youtube_description.txt`
- **是否使用 Plugin 系统**: 否，直接调用生成函数
- **是否依赖 Legacy Stage Executor**: 否

### 4.7 filler_generate_text_assets
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `async def filler_generate_text_assets(request: FillerGenerateRequest) -> Dict`
- **输入参数**:
  - `request.episode_id`: 期数ID
  - `request.channel_id`: 频道ID
  - `request.asset_types`: 资产类型列表（["title", "description", "captions", "tags"]）
  - `request.overwrite`: 是否覆盖已存在文件
- **输出形式**: 返回字典，包含所有生成的文件路径
- **是否使用 Plugin 系统**: 否，这是FILLER工作流的函数
- **是否依赖 Legacy Stage Executor**: 否

### 4.8 _filler_generate_title_desc_srt_tags
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `async def _filler_generate_title_desc_srt_tags(episode_id: str, episode_output_dir: Path, playlist_path: Optional[Path], timeline_csv_path: Optional[Path], original_title: str, api_key: Optional[str] = None, api_base: Optional[str] = None, model: Optional[str] = None, asset_types: Optional[List[str]] = None, overwrite: bool = True) -> Dict[str, Any]`
- **输入参数**:
  - `episode_id`: 期数ID
  - `episode_output_dir`: 期数输出目录
  - `playlist_path`: 歌单文件路径
  - `timeline_csv_path`: 时间轴CSV路径
  - `original_title`: 原始标题
  - `api_key`, `api_base`, `model`: API配置
  - `asset_types`: 要生成的资产类型列表
  - `overwrite`: 是否覆盖
- **输出形式**: 返回字典，包含title、description、srt_path、tags等
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 4.9 async_generate_youtube_title_desc
- **模块路径**: `kat_rec_web/backend/t2r/utils/async_youtube_assets.py`
- **函数签名**: `async def async_generate_youtube_title_desc(original_title: str, playlist_data: Dict, api_key: Optional[str] = None, api_base: Optional[str] = None, model: Optional[str] = None, logger_param: Optional[logging.Logger] = None) -> Tuple[str, str]`
- **输入参数**: 与 `generate_youtube_title_desc` 相同
- **输出形式**: 返回元组 `(title, description)`
- **是否使用 Plugin 系统**: 否，这是异步包装版本
- **是否依赖 Legacy Stage Executor**: 否

### 4.10 TextAssetsPlugin.execute
- **模块路径**: `kat_rec_web/backend/t2r/plugins/text_assets_plugin.py`
- **函数签名**: `async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]`
- **输入参数**:
  - `context.episode_id`: 期数ID
  - `context.channel_id`: 频道ID
  - `context.asset_types`: 资产类型列表
- **输出形式**: 返回执行结果字典，包含所有生成的文件路径
- **是否使用 Plugin 系统**: 是，这是Plugin系统的实现
- **是否依赖 Legacy Stage Executor**: 否

### 4.11 generate_youtube_title_desc (旧版本)
- **模块路径**: `scripts/local_picker/generate_youtube_assets.py`
- **函数签名**: `def generate_youtube_title_desc(original_title: str, playlist_data: Dict, api_key: Optional[str] = None, api_base: Optional[str] = None) -> tuple[str, str]`
- **输入参数**: 与新版类似
- **输出形式**: 返回元组 `(title, description)`
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 是，这是旧版本，包含废弃的规则（"Kat Records × Vibe Coding"、"This is Vibe Coding..."）

---

## 5. 字幕与歌词文件

### 5.1 _filler_generate_srt
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `async def _filler_generate_srt(playlist_data: Dict, output_path: Path, api_key: Optional[str] = None, api_base: Optional[str] = None, model: Optional[str] = None) -> None`
- **输入参数**:
  - `playlist_data`: 歌单数据字典（包含tracks_a, tracks_b, clean_timeline）
  - `output_path`: 输出SRT文件路径
  - `api_key`, `api_base`, `model`: API配置（用于生成欢迎消息，可选）
- **输出形式**: 生成SRT字幕文件（格式：`{episode_id}_youtube.srt`），包含曲目时间轴
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.2 generate_welcoming_messages
- **模块路径**: `src/core/youtube_assets.py`
- **函数签名**: `def generate_welcoming_messages(api_key: Optional[str] = None, api_base: Optional[str] = None, model: Optional[str] = None, logger: Optional[LoggerProtocol] = None) -> Tuple[str, str]`
- **输入参数**:
  - `api_key`, `api_base`, `model`: OpenAI API配置
  - `logger`: 日志记录器
- **输出形式**: 返回元组 `(intro_msg, outro_msg)`，欢迎和结束消息
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.3 _filler_format_srt_time
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `def _filler_format_srt_time(hours: int, minutes: int, seconds: int, milliseconds: int) -> str`
- **输入参数**:
  - `hours`, `minutes`, `seconds`, `milliseconds`: 时间分量
- **输出形式**: 返回格式化的SRT时间戳字符串（格式：`HH:MM:SS,mmm` 或 `MM:SS,mmm`）
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.4 _filler_parse_timestamp
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `def _filler_parse_timestamp(timestamp: str) -> Tuple[int, int, int, int]`
- **输入参数**:
  - `timestamp`: 时间戳字符串（格式：`H:MM:SS` 或 `MM:SS`）
- **输出形式**: 返回元组 `(hours, minutes, seconds, milliseconds)`
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.5 regenerate_asset (asset_type="captions")
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `async def regenerate_asset(request: RegenerateAssetRequest) -> Dict`
- **输入参数**:
  - `request.episode_id`: 期数ID
  - `request.channel_id`: 频道ID
  - `request.asset_type`: 资产类型（"captions"）
  - `request.overwrite`: 是否覆盖已存在文件
- **输出形式**: 返回字典，包含 `file_path`（SRT文件路径：`{episode_id}_youtube.srt`）
- **是否使用 Plugin 系统**: 否，直接调用生成函数
- **是否依赖 Legacy Stage Executor**: 否

### 5.6 generate_srt (旧版本)
- **模块路径**: `scripts/local_picker/generate_youtube_assets.py`
- **函数签名**: `def generate_srt(playlist_data: Dict, output_path: Path, api_key: Optional[str] = None, api_base: Optional[str] = None) -> None`
- **输入参数**: 与 `_filler_generate_srt` 类似
- **输出形式**: 生成SRT字幕文件
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 是，这是旧版本，可能包含不同的规则

### 5.7 generate_welcoming_messages (旧版本)
- **模块路径**: `scripts/local_picker/generate_youtube_assets.py`
- **函数签名**: `def generate_welcoming_messages(api_key: Optional[str] = None, api_base: Optional[str] = None) -> tuple[str, str]`
- **输入参数**: API配置
- **输出形式**: 返回元组 `(intro_msg, outro_msg)`
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 是，这是旧版本

### 5.8 parse_srt_file
- **模块路径**: `kat_rec_web/backend/t2r/services/srt_service.py`
- **函数签名**: `def parse_srt_file(file_path: Path) -> List[SRTSubtitle]`
- **输入参数**:
  - `file_path`: SRT文件路径
- **输出形式**: 返回SRTSubtitle对象列表（用于解析和检查，不用于生成）
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.9 save_srt_file
- **模块路径**: `kat_rec_web/backend/t2r/services/srt_service.py`
- **函数签名**: `def save_srt_file(subtitles: List[SRTSubtitle], output_path: Path) -> bool`
- **输入参数**:
  - `subtitles`: SRTSubtitle对象列表
  - `output_path`: 输出文件路径
- **输出形式**: 返回布尔值表示成功与否，保存SRT文件
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.10 _filler_generate_tags_file
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `def _filler_generate_tags_file(tags: List[str], output_path: Path, min_tags: int = 20) -> None`
- **输入参数**:
  - `tags`: 标签列表（从描述中提取或手动提供）
  - `output_path`: 输出标签文件路径
  - `min_tags`: 最小标签数量（默认20）
- **输出形式**: 生成标签文件（格式：`{episode_id}_youtube_tags.txt`），每行一个标签，确保至少有min_tags个标签
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.11 async_generate_tags_file
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `async def async_generate_tags_file(tags: List[str], output_path: Path, min_tags: int = 20) -> None`
- **输入参数**: 与 `_filler_generate_tags_file` 相同
- **输出形式**: 生成标签文件（异步版本）
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.12 _filler_extract_tags_from_description
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `def _filler_extract_tags_from_description(description: str) -> List[str]`
- **输入参数**:
  - `description`: 描述文本（包含hashtag部分）
- **输出形式**: 返回从描述中提取的标签列表
- **是否使用 Plugin 系统**: 否
- **是否依赖 Legacy Stage Executor**: 否

### 5.13 regenerate_asset (asset_type="tags")
- **模块路径**: `kat_rec_web/backend/t2r/routes/automation.py`
- **函数签名**: `async def regenerate_asset(request: RegenerateAssetRequest) -> Dict`
- **输入参数**:
  - `request.episode_id`: 期数ID
  - `request.channel_id`: 频道ID
  - `request.asset_type`: 资产类型（"tags"）
  - `request.overwrite`: 是否覆盖已存在文件
- **输出形式**: 返回字典，包含 `file_path`（标签文件路径：`{episode_id}_youtube_tags.txt`）
- **是否使用 Plugin 系统**: 否，直接调用生成函数
- **是否依赖 Legacy Stage Executor**: 否

---

## 总结

### Plugin 系统使用情况
- **使用 Plugin 系统**:
  - 封面生成：`CoverPlugin`
  - 音频混音：`RemixPlugin`
  - 文本资产：`TextAssetsPlugin`
- **不使用 Plugin 系统**:
  - 视频渲染：直接调用函数，无专门Plugin
  - 大部分底层生成函数

### Legacy Stage Executor 依赖情况
- **不依赖 Legacy Stage Executor**（使用新系统）:
  - 所有在 `src/core/` 和 `kat_rec_web/backend/t2r/routes/automation.py` 中的新版本函数
  - 使用 `StageflowExecutor` 的函数
  - Plugin 系统的实现
- **依赖 Legacy Stage Executor**（旧版本）:
  - `scripts/render_video_original.py` 中的 `render_episode`
  - `scripts/render_video_from_mp3.py` 中的 `render_video_from_mp3`
  - `scripts/local_picker/generate_youtube_assets.py` 中的所有函数（旧版本，包含废弃规则）

### 推荐使用的函数
- **封面生成**: `generate_cover` (automation.py) → `compose_cover` (create_mixtape.py)
- **音频混音**: `_execute_stage` (plan.py, stage="remix") → `remix_mixtape.py`
- **视频渲染**: `render_video_direct_from_playlist` (direct_video_render.py)
- **标题和描述**: `generate_youtube_title_desc` (src/core/youtube_assets.py)
- **字幕生成**: `_filler_generate_srt` (automation.py)

### 应避免使用的函数
- `scripts/local_picker/generate_youtube_assets.py` 中的所有函数（旧版本，包含废弃规则）
- `scripts/render_video_original.py` 和 `scripts/render_video_from_mp3.py`（旧版本渲染函数）

