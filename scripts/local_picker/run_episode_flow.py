#!/usr/bin/env python3
# coding: utf-8
"""
Run EpisodeFlow for selected episodes via CLI.

Example:
    python scripts/local_picker/run_episode_flow.py --channel kat_lofi 20251110 20251111
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_ROOT = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts" / "local_picker"
for path in (REPO_ROOT, SRC_ROOT, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.channel_context import resolve_channel_id, resolve_schedule_path  # noqa: E402
from schedule_master import ScheduleMaster  # type: ignore  # noqa: E402
from src.core.episode_model import EpisodeModel  # noqa: E402
from src.core.event_bus import EventBus  # noqa: E402
from src.core.episode_flow import EpisodeFlow  # noqa: E402
from src.core.flow_bus import EpisodeFlowBus, EpisodeFlowCommand  # noqa: E402


def load_schedule(channel_id: str) -> ScheduleMaster:
    path = resolve_schedule_path(channel_id)
    schedule = ScheduleMaster.load(path=path)
    if not schedule:
        raise RuntimeError(f"schedule_master not found for channel {channel_id}")
    return schedule


def find_episode(schedule: ScheduleMaster, episode_id: str) -> Dict:
    return next((ep for ep in schedule.episodes if ep["episode_id"] == episode_id), None)


def build_episode_model(channel_id: str, episode_data: Dict) -> EpisodeModel:
    episode_id = episode_data["episode_id"]
    date = episode_data.get("schedule_date") or episode_id
    output_dir = REPO_ROOT / "channels" / channel_id / "output" / episode_id
    paths = {"output": str(output_dir)}
    ctx = {"source": "cli.episode_flow"}
    return EpisodeModel(
        id=episode_id,
        channel=channel_id,
        date=date,
        paths=paths,
        ctx=ctx,
    )


async def run_flow(channel_id: str, episode_ids: List[str]) -> None:
    """
    Run EpisodeFlow for specified episodes with actual business logic integration.
    
    This function demonstrates how to use EpisodeFlow with adapters to execute
    the complete workflow: playlist → remix → render → upload.
    """
    # Import adapters (lazy import to avoid circular dependencies)
    import sys
    backend_root = REPO_ROOT / "kat_rec_web" / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    
    from t2r.services.episode_flow_adapters import (
        AutomationPlaylistGenerator,
        PlanRemixEngine,
        PlanRenderEngine,
        PlanUploadService,
    )
    
    event_bus = EventBus(channel_id=channel_id)
    flow_bus = EpisodeFlowBus(channel_id=channel_id)

    async def start_handler(episode: EpisodeModel, payload: Dict) -> None:
        """
        Handler for 'start' command that executes complete EpisodeFlow workflow.
        
        Creates EpisodeFlow with actual business logic adapters and executes
        the full pipeline: playlist → remix → render → upload.
        """
        # Create EpisodeFlow with actual business logic implementations
        flow = EpisodeFlow(
            episode=episode,
            event_bus=event_bus,
            playlist_generator=AutomationPlaylistGenerator(),
            remix_engine=PlanRemixEngine(),
            render_engine=PlanRenderEngine(),
            upload_service=PlanUploadService(),
        )
        
        # Execute complete workflow (now async)
        await flow.start_generation()

    flow_bus.register_handler("start", start_handler)

    schedule = load_schedule(channel_id)
    for eid in episode_ids:
        episode_data = find_episode(schedule, eid)
        if not episode_data:
            print(f"⚠️  Episode {eid} not found in schedule, skipping")
            continue
        model = build_episode_model(channel_id, episode_data)
        command = EpisodeFlowCommand(
            name="start",
            episode=model,
            payload={"source": "cli"},
        )
        await flow_bus.publish(command)

    await flow_bus.wait_for_idle()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run EpisodeFlow pipeline for specified episodes")
    parser.add_argument("--channel", "-c", help="Channel ID (default: resolve from env)")
    parser.add_argument("episode_ids", nargs="+", help="Episode IDs (e.g., 20251110)")
    args = parser.parse_args()

    channel_id = resolve_channel_id(args.channel)
    if not channel_id:
        raise RuntimeError("Unable to determine channel_id; pass --channel or set KATREC_CHANNEL_ID")
    os.environ["KATREC_CHANNEL_ID"] = channel_id

    asyncio.run(run_flow(channel_id, args.episode_ids))


if __name__ == "__main__":
    main()
