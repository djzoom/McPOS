# EpisodeFlow 业务逻辑集成修复计划

**目标**: 修复内容产品产生机制，确保 EpisodeFlow 真正执行所有业务逻辑，而不是只更新状态。

**优先级**: 🔴 P0 - 立即修复

---

## 📋 问题概述

### 当前问题

`EpisodeFlow` 的所有阶段方法（`generate_playlist`, `remix`, `render`, `upload`）都只是更新状态和发出事件，但**不执行实际的业务逻辑**。这导致：

1. **工作流不完整** - 只执行了部分阶段（如 remix），其他阶段（封面、文本资产、视频）被跳过
2. **状态不一致** - 状态显示完成，但实际文件未生成
3. **自动化失效** - `start_generation()` 创建 episodes 但工作流永远不会真正完成

### 根本原因

- EpisodeFlow 是架构骨架，业务逻辑是 TODO
- 实际业务逻辑在 `kat_rec_web/backend/t2r/routes/` 中，但未集成到 EpisodeFlow
- 工作流执行机制依赖外部调用，而不是通过 EpisodeFlow 统一管理

---

## 🎯 修复方案

### 方案 1: 依赖注入（推荐）

**优点**:
- 解耦业务逻辑和流程控制
- 易于测试和替换实现
- 保持 EpisodeFlow 的通用性

**实现**:

```python
# src/core/episode_flow.py

from typing import Protocol, Optional
from pathlib import Path

class PlaylistGenerator(Protocol):
    """Playlist generation protocol."""
    async def generate(self, episode_id: str, channel_id: str) -> Path:
        """Generate playlist and return path."""
        ...

class RemixEngine(Protocol):
    """Remix engine protocol."""
    async def remix(self, playlist_path: Path, episode_id: str, channel_id: str) -> Path:
        """Remix audio and return path."""
        ...

class RenderEngine(Protocol):
    """Render engine protocol."""
    async def render(
        self, 
        audio_path: Path, 
        cover_path: Path, 
        episode_id: str, 
        channel_id: str
    ) -> Path:
        """Render video and return path."""
        ...

class UploadService(Protocol):
    """Upload service protocol."""
    async def upload(self, video_path: Path, episode_id: str, channel_id: str) -> str:
        """Upload video and return video ID."""
        ...

class EpisodeFlow:
    """Unified pipeline controller (playlist → mix → render → upload)."""
    
    def __init__(
        self, 
        episode: EpisodeModel, 
        event_bus: EventBus,
        *,
        playlist_generator: Optional[PlaylistGenerator] = None,
        remix_engine: Optional[RemixEngine] = None,
        render_engine: Optional[RenderEngine] = None,
        upload_service: Optional[UploadService] = None,
    ) -> None:
        self.episode = episode
        self.event_bus = event_bus
        self.playlist_generator = playlist_generator
        self.remix_engine = remix_engine
        self.render_engine = render_engine
        self.upload_service = upload_service
    
    async def generate_playlist(self) -> None:
        """Generate playlist for the episode."""
        with self.stage_guard("playlist", on_error=self._checkpoint_on_error):
            if not self.playlist_generator:
                raise ValueError("PlaylistGenerator not provided")
            
            # Execute actual business logic
            playlist_path = await self.playlist_generator.generate(
                episode_id=self.episode.id,
                channel_id=self.episode.channel,
            )
            
            # Update episode model
            self.episode.paths["playlist"] = str(playlist_path)
            self.episode.status = "playlist_ready"
            
            # Emit event with actual path
            self._emit("playlist_ready", {"path": str(playlist_path)})
    
    async def remix(self) -> None:
        """Remix audio for the episode."""
        with self.stage_guard("mix", on_error=self._checkpoint_on_error):
            if not self.remix_engine:
                raise ValueError("RemixEngine not provided")
            
            playlist_path = Path(self.episode.paths.get("playlist", ""))
            if not playlist_path.exists():
                raise FileNotFoundError(f"Playlist not found: {playlist_path}")
            
            # Execute actual business logic
            audio_path = await self.remix_engine.remix(
                playlist_path=playlist_path,
                episode_id=self.episode.id,
                channel_id=self.episode.channel,
            )
            
            # Update episode model
            self.episode.paths["mix"] = str(audio_path)
            self.episode.status = "mixed"
            
            # Emit event with actual path
            self._emit("mix_ready", {"path": str(audio_path)})
    
    async def render(self) -> None:
        """Render video for the episode."""
        with self.stage_guard("render", on_error=self._checkpoint_on_error):
            if not self.render_engine:
                raise ValueError("RenderEngine not provided")
            
            audio_path = Path(self.episode.paths.get("mix", ""))
            cover_path = Path(self.episode.paths.get("cover", ""))
            
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio not found: {audio_path}")
            if not cover_path.exists():
                raise FileNotFoundError(f"Cover not found: {cover_path}")
            
            # Execute actual business logic
            video_path = await self.render_engine.render(
                audio_path=audio_path,
                cover_path=cover_path,
                episode_id=self.episode.id,
                channel_id=self.episode.channel,
            )
            
            # Update episode model
            self.episode.paths["render"] = str(video_path)
            self.episode.status = "rendered"
            
            # Emit event with actual path
            self._emit("render_done", {"path": str(video_path)})
    
    async def upload(self) -> None:
        """Upload video to YouTube for the episode."""
        with self.stage_guard("upload", on_error=self._checkpoint_on_error):
            if not self.upload_service:
                raise ValueError("UploadService not provided")
            
            video_path = Path(self.episode.paths.get("render", ""))
            if not video_path.exists():
                raise FileNotFoundError(f"Video not found: {video_path}")
            
            # Execute actual business logic
            video_id = await self.upload_service.upload(
                video_path=video_path,
                episode_id=self.episode.id,
                channel_id=self.episode.channel,
            )
            
            # Update episode model
            self.episode.ctx["video_id"] = video_id
            self.episode.status = "uploaded"
            
            # Emit event with actual video ID
            self._emit("upload_done", {"video_id": video_id})
    
    async def start_generation(self) -> None:
        """Entry point for FlowBus or FastAPI routes."""
        self._emit("episode_created", {})
        await self.generate_playlist()
        await self.remix()
        await self.render()
        await self.upload()
```

**适配器实现**:

```python
# kat_rec_web/backend/t2r/services/episode_flow_adapters.py

from pathlib import Path
from typing import Protocol
from src.core.episode_flow import PlaylistGenerator, RemixEngine, RenderEngine, UploadService

class AutomationPlaylistGenerator:
    """Adapter for automation.generate_playlist."""
    
    async def generate(self, episode_id: str, channel_id: str) -> Path:
        from ..routes.automation import generate_playlist, GeneratePlaylistRequest
        
        request = GeneratePlaylistRequest(
            episode_id=episode_id,
            channel_id=channel_id,
        )
        result = await generate_playlist(request)
        
        if result["status"] != "ok":
            raise RuntimeError(f"Playlist generation failed: {result.get('errors')}")
        
        playlist_path = Path(result["playlist_path"])
        if not playlist_path.exists():
            raise FileNotFoundError(f"Playlist file not found: {playlist_path}")
        
        return playlist_path

class PlanRemixEngine:
    """Adapter for plan._execute_stage_core('remix')."""
    
    async def remix(self, playlist_path: Path, episode_id: str, channel_id: str) -> Path:
        from ..routes.plan import _execute_stage_core
        
        await _execute_stage_core(
            stage="remix",
            episode_id=episode_id,
            emit_events=False,  # EpisodeFlow will emit events
        )
        
        # Find generated audio file
        from ..utils.path_helpers import get_episode_output_dir
        output_dir = get_episode_output_dir(episode_id, channel_id)
        audio_path = output_dir / f"{episode_id}_full_mix.mp3"
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        return audio_path

class PlanRenderEngine:
    """Adapter for plan._execute_stage_core('render')."""
    
    async def render(
        self, 
        audio_path: Path, 
        cover_path: Path, 
        episode_id: str, 
        channel_id: str
    ) -> Path:
        from ..routes.plan import _execute_stage_core
        
        await _execute_stage_core(
            stage="render",
            episode_id=episode_id,
            emit_events=False,  # EpisodeFlow will emit events
        )
        
        # Find generated video file
        from ..utils.path_helpers import get_episode_output_dir
        output_dir = get_episode_output_dir(episode_id, channel_id)
        video_path = output_dir / f"{episode_id}_youtube.mp4"
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        return video_path

class PlanUploadService:
    """Adapter for plan._execute_stage_core('upload')."""
    
    async def upload(self, video_path: Path, episode_id: str, channel_id: str) -> str:
        from ..routes.plan import _execute_stage_core
        
        await _execute_stage_core(
            stage="upload",
            episode_id=episode_id,
            emit_events=False,  # EpisodeFlow will emit events
        )
        
        # Get video ID from schedule_master or upload result
        from ..services.schedule_service import load_schedule_master
        schedule = load_schedule_master(channel_id)
        episode = next((e for e in schedule.get("episodes", []) if e.get("episode_id") == episode_id), None)
        
        video_id = episode.get("youtube_video_id") if episode else None
        if not video_id:
            raise ValueError(f"YouTube video ID not found for episode {episode_id}")
        
        return video_id
```

**使用示例**:

```python
# kat_rec_web/backend/t2r/services/channel_automation.py

from src.core.episode_flow import EpisodeFlow
from .episode_flow_adapters import (
    AutomationPlaylistGenerator,
    PlanRemixEngine,
    PlanRenderEngine,
    PlanUploadService,
)

async def run_episode_flow(episode_id: str, channel_id: str) -> None:
    """Run complete episode flow with actual business logic."""
    from src.core.episode_model import EpisodeModel
    from src.core.event_bus import EventBus
    
    # Build episode model
    episode = EpisodeModel(
        id=episode_id,
        channel=channel_id,
        # ... other fields
    )
    
    event_bus = EventBus(channel_id=channel_id)
    
    # Create flow with actual implementations
    flow = EpisodeFlow(
        episode=episode,
        event_bus=event_bus,
        playlist_generator=AutomationPlaylistGenerator(),
        remix_engine=PlanRemixEngine(),
        render_engine=PlanRenderEngine(),
        upload_service=PlanUploadService(),
    )
    
    # Execute complete workflow
    await flow.start_generation()
```

---

### 方案 2: 服务层调用（备选）

**优点**:
- 直接调用现有服务
- 实现简单快速

**缺点**:
- 紧耦合
- 难以测试

**实现**:

```python
# src/core/episode_flow.py

class EpisodeFlow:
    """Unified pipeline controller (playlist → mix → render → upload)."""
    
    def __init__(self, episode: EpisodeModel, event_bus: EventBus) -> None:
        self.episode = episode
        self.event_bus = event_bus
        # Lazy import to avoid circular dependencies
        self._playlist_service = None
        self._remix_service = None
        self._render_service = None
        self._upload_service = None
    
    def _get_playlist_service(self):
        """Lazy load playlist service."""
        if self._playlist_service is None:
            from kat_rec_web.backend.t2r.routes.automation import generate_playlist
            self._playlist_service = generate_playlist
        return self._playlist_service
    
    async def generate_playlist(self) -> None:
        """Generate playlist for the episode."""
        with self.stage_guard("playlist", on_error=self._checkpoint_on_error):
            from kat_rec_web.backend.t2r.routes.automation import GeneratePlaylistRequest
            
            service = self._get_playlist_service()
            request = GeneratePlaylistRequest(
                episode_id=self.episode.id,
                channel_id=self.episode.channel,
            )
            
            result = await service(request)
            
            if result["status"] != "ok":
                raise RuntimeError(f"Playlist generation failed: {result.get('errors')}")
            
            playlist_path = Path(result["playlist_path"])
            self.episode.paths["playlist"] = str(playlist_path)
            self.episode.status = "playlist_ready"
            self._emit("playlist_ready", {"path": str(playlist_path)})
    
    # Similar for remix, render, upload...
```

---

## 📝 实施步骤

### 阶段 1: 准备阶段（1-2 天）

1. **创建 Protocol 定义**
   - 定义 `PlaylistGenerator`, `RemixEngine`, `RenderEngine`, `UploadService` protocols
   - 在 `src/core/episode_flow.py` 中添加

2. **修改 EpisodeFlow 构造函数**
   - 添加依赖注入参数
   - 更新所有阶段方法为 async
   - 添加实际业务逻辑调用

### 阶段 2: 适配器实现（2-3 天）

3. **创建适配器模块**
   - `kat_rec_web/backend/t2r/services/episode_flow_adapters.py`
   - 实现所有适配器类

4. **集成现有服务**
   - 包装 `automation.generate_playlist`
   - 包装 `plan._execute_stage_core`
   - 处理路径和错误

### 阶段 3: 集成测试（1-2 天）

5. **更新调用点**
   - 更新 `channel_automation.py` 使用新的 EpisodeFlow
   - 更新 `EpisodeFlowBus` handlers

6. **测试完整工作流**
   - 端到端测试
   - 验证所有文件生成
   - 验证状态更新

### 阶段 4: 错误处理和恢复（1 天）

7. **改进错误处理**
   - 确保部分失败不影响其他阶段
   - 添加重试机制
   - 改进错误消息

---

## ✅ 验收标准

修复完成后，应该满足：

1. **完整工作流执行**
   - ✅ `start_generation()` 执行所有阶段
   - ✅ 每个阶段真正调用业务逻辑
   - ✅ 所有必需文件都生成

2. **状态一致性**
   - ✅ `EpisodeModel.paths` 包含所有生成的文件路径
   - ✅ `EpisodeModel.status` 正确反映当前阶段
   - ✅ 事件包含实际文件路径

3. **错误处理**
   - ✅ 部分失败不影响其他阶段
   - ✅ 错误信息清晰
   - ✅ 支持恢复和重试

4. **测试覆盖**
   - ✅ 单元测试覆盖所有阶段
   - ✅ 集成测试验证完整工作流
   - ✅ 错误场景测试

---

## 🔗 相关文档

- `docs/PROJECT_ISSUES_ANALYSIS.md` - EpisodeFlow 架构问题
- `src/core/episode_flow.py` - EpisodeFlow 实现
- `kat_rec_web/backend/t2r/routes/automation.py` - 实际业务逻辑
- `kat_rec_web/backend/t2r/routes/plan.py` - 实际业务逻辑

---

**优先级**: 🔴 P0 - 立即修复  
**预计时间**: 5-8 天  
**负责人**: 待分配

