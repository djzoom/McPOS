import asyncio
import json
import time
from pathlib import Path

import websockets


async def collect(destination: Path, stats_path: Path, duration: float = 12.0, target: int = 20):
    destination.parent.mkdir(parents=True, exist_ok=True)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    uri = "ws://localhost:8000/ws/events"
    messages = []
    versions = []
    dup_count = 0
    min_version = None
    max_version = None
    start = time.time()
    async with websockets.connect(uri) as ws:
        while len(messages) < target and (time.time() - start) < duration:
            remaining = duration - (time.time() - start)
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            if raw in ('"ping"', "ping", '"pong"', "pong"):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") in ("ping", "pong"):
                continue
            msg["_received_at"] = time.time()
            messages.append(msg)
            version = msg.get("version")
            if version is None and isinstance(msg.get("data"), dict):
                version = msg["data"].get("version")
            if version is not None:
                if min_version is None or version < min_version:
                    min_version = version
                if max_version is None or version > max_version:
                    max_version = version
                if versions and version <= versions[-1]:
                    dup_count += 1
                versions.append(version)
    destination.write_text("\n".join(json.dumps(m) for m in messages), encoding="utf-8")
    latency_samples = []
    for msg in messages:
        ts = msg.get("ts") or (msg.get("data") or {}).get("ts")
        if ts:
            try:
                from datetime import datetime

                sent = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                latency = msg["_received_at"] - sent.timestamp()
                latency_samples.append(latency)
            except Exception:
                pass
    avg_latency = sum(latency_samples) / len(latency_samples) if latency_samples else None
    increasing = all(versions[i] < versions[i + 1] for i in range(len(versions) - 1)) if versions else False
    stats_path.write_text(
        json.dumps(
            {
                "message_count": len(messages),
                "version_samples": versions,
                "min_version": min_version,
                "max_version": max_version,
                "duplicate_or_non_increasing_steps": dup_count,
                "strictly_increasing": increasing,
                "avg_latency_sec": avg_latency,
                "duration_sec": time.time() - start,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(
        collect(
            Path("audit/ws_sample.jsonl"),
            Path("audit/ws_stats.json"),
        )
    )
