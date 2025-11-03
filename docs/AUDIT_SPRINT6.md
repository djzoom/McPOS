# Kat Rec Web – Sprint 6 Audit (Independent Review)

## Executive Summary
- T2R router never loads in production runs because relative imports in `t2r/routes/*` climb past the package root, so every `/api/episodes/*`, `/metrics/*`, `/api/t2r/*` endpoint returns 404 (see `audit/plan_response.json`, `audit/metrics_system.json`, `audit/openapi_2025-11-03.json` – SHA1 `b8a472bbd059eb41b3edf05c937e701778a75089`).
- WebSocket broadcasting is silent in practice: buffered sends are never flushed and no events arrive (`audit/ws_stats.json` message_count 0), leaving Mission Control without live telemetry.
- SRT tooling exposes arbitrary-file read/write because user input is joined with `OUTPUT_ROOT` without normalisation; a crafted `../` path reaches outside the intended directory (`t2r/routes/srt.py:54`).
- Build pipeline blocks at `pnpm -C frontend build` because ESLint references `@typescript-eslint/no-unused-vars` without installing the plugin (`audit/build_stats.txt`), so a production bundle cannot be produced.
- Front-end expects status payloads (`message.data.channels`) that the backend never sends, so channel cards stay frozen even if WS begins to flow (`frontend/hooks/useWebSocket.ts:26`, `backend/routes/websocket.py:118`).
- Front-end dependency footprint is 484 MB (`audit/size_node_modules.txt`), exceeding the 300 MB budget called out in the sprint brief; `recharts`, `react-virtuoso`, and `framer-motion` dominate per `audit/deps_frontend.txt`.
- System health script reports “mock mode” and missing metrics because environment validation is never surfaced (`audit/verify_sprint6_output.txt`), masking filesystem misconfiguration.
- Total counted LOC for `kat_rec_web` (excluding `node_modules`/`.venv`) is 14 244 lines (`audit/loc_summary.json`); no previous baseline exists.

## Findings Table
| ID | Severity/Confidence | Area | Symptom | Evidence | Impact | Fix Strategy |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | S0/H | Backend API | All T2R endpoints (plan/run/metrics/websocket) return 404; OpenAPI snapshot lacks `/api/episodes/*` and metrics paths. | `backend/t2r/routes/plan.py:17`, `audit/openapi_2025-11-03.json`, `audit/plan_response.json`, `audit/metrics_system.json`, `audit/resume_result.json` | Mission control cannot plan, execute, or monitor runs; verify script and frontend fail. | Switch triple-dot relative imports in `t2r/routes/*` to absolute `routes.*` so `t2r.router` loads. |
| F2 | S1/H | WebSocket integrity | No events delivered (0 messages in 12 s sample); ConnectionManager never starts buffer flush. | `audit/ws_stats.json`, `backend/routes/websocket.py:150-211`, `core/websocket_manager.py:148` | Mission control feed remains blank; backpressure logic idle. | Start buffer flush tasks during startup and include channel payloads in status broadcasts. |
| F3 | S1/H | Security (SRT) | `inspect_srt` accepts `../` paths and opens arbitrary files; `fix_srt` writes alongside user path. | `t2r/routes/srt.py:54-121` | Remote readers can exfiltrate or clobber files outside `OUTPUT_ROOT`. | Resolve inputs, enforce containment under `OUTPUT_ROOT`, and reject escapes with 400. |
| F4 | S2/M | Concurrency & recovery | Crash-resume flow absent: journaling helper exists but API lacks `resume_run_id`, script-mandated `/api/episodes/resume` 404s. | `audit/resume_result.json`, `t2r/services/runbook_journal.py:120`, `t2r/routes/plan.py:383-399` | Failed runs cannot be resumed; retry policy wastes previous work. | Extend `RunRequest` with `resume_run_id` and add a thin `/api/episodes/resume` wrapper that reuses the recorded run. |
| F5 | S2/H | Frontend build & deploy size | `pnpm -C frontend build` halts (missing `@typescript-eslint` plugin); node_modules footprint is 484 MB. | `audit/build_stats.txt`, `audit/size_node_modules.txt`, `audit/deps_frontend.txt` | Cannot ship production bundle; deploy artifacts exceed Infra limits. | Add the ESLint plugin devDependency + config, then prune/optionally lazy-load `recharts`, `react-virtuoso`, `framer-motion` or split via `next/dynamic`. |
| F6 | S2/M | Observability | Health endpoint omits path validation details; metrics endpoints absent due to F1, causing `scripts/verify_sprint6.sh` to return nulls. | `audit/verify_sprint6_output.txt`, `backend/main.py:102-131` | Ops scripts cannot detect missing directories or metrics regressions. | Surface env check results in `/health` and ensure metrics routers load (after F1). |
| F7 | S3/M | WS client semantics | FE dedupe checks `message.data.version`, but backend emits `version` at top level; ping/pong mismatched (`"ping"` vs raw `pong`). | `frontend/services/wsClient.ts:69-87`, `routes/websocket.py:195-210`, `core/websocket_manager.py:100-118` | Duplicate suppression & latency metrics never function; stale connections churn. | Align schema (read `message.version`) and exchange JSON ping/pong frames. |

## Patches
```diff
--- a/backend/t2r/routes/plan.py
+++ b/backend/t2r/routes/plan.py
@@
-from ...routes.websocket import broadcast_t2r_event
+from routes.websocket import broadcast_t2r_event
--- a/backend/t2r/routes/scan.py
+++ b/backend/t2r/routes/scan.py
@@
-from ...routes.websocket import broadcast_t2r_event
+from routes.websocket import broadcast_t2r_event
--- a/backend/t2r/routes/srt.py
+++ b/backend/t2r/routes/srt.py
@@
-from ...routes.websocket import broadcast_t2r_event
+from routes.websocket import broadcast_t2r_event
--- a/backend/t2r/routes/metrics.py
+++ b/backend/t2r/routes/metrics.py
@@
-from ...routes.websocket import status_manager, events_manager
+from routes.websocket import status_manager, events_manager
```

```diff
--- a/backend/routes/websocket.py
+++ b/backend/routes/websocket.py
@@
 async def broadcast_status_updates():
@@
-        # Calculate queue status
-        total_channels = 10
+        total_channels = 10
         active_channels = random.randint(5, 8)
         queue_status = {
             "total": total_channels,
             "active": active_channels,
             "pending": random.randint(0, 3),
             "processing": random.randint(1, 4),
             "completed": random.randint(2, 6),
             "failed": random.randint(0, 2),
         }
+        channels = [
+            generate_mock_channel_status(f"CH-{i:03d}") for i in range(total_channels)
+        ]
@@
         message = {
             "type": "status_update",
             "data": {
                 "queue_status": queue_status,
                 "success_rate": round(success_rate, 2),
                 "last_event": last_event,
-                "timestamp": datetime.utcnow().isoformat(),
+                "timestamp": datetime.utcnow().isoformat(),
+                "channels": channels,
             },
         }
@@
 async def start_broadcast_tasks():
     """Start background broadcast tasks"""
     global status_task, events_task
     if status_task is None:
         status_task = asyncio.create_task(broadcast_status_updates())
     if events_task is None:
         events_task = asyncio.create_task(broadcast_events())
+    await status_manager.start_buffer_flush()
+    await events_manager.start_buffer_flush()
```

```diff
--- a/backend/t2r/routes/srt.py
+++ b/backend/t2r/routes/srt.py
@@
-from fastapi import APIRouter, UploadFile, File
+from fastapi import APIRouter, UploadFile, File, HTTPException
@@
-OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", str(REPO_ROOT / "output")))
+OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", str(REPO_ROOT / "output"))).resolve()
+
+
+def _resolve_output_path(path: Path) -> Path:
+    candidate = path if path.is_absolute() else OUTPUT_ROOT / path
+    candidate = candidate.resolve()
+    try:
+        candidate.relative_to(OUTPUT_ROOT)
+    except ValueError:
+        raise HTTPException(status_code=400, detail=f"Path outside OUTPUT_ROOT: {candidate}")
+    return candidate
@@
     if request.file_path:
-        file_path = Path(request.file_path)
-        if not file_path.is_absolute():
-            file_path = OUTPUT_ROOT / file_path
+        file_path = _resolve_output_path(Path(request.file_path))
@@
     elif request.episode_id:
         # Try to find SRT file in output directory
         possible_paths = [
-            OUTPUT_ROOT / request.episode_id / f"{request.episode_id}.srt",
-            OUTPUT_ROOT / f"{request.episode_id}.srt",
-            OUTPUT_ROOT / request.episode_id / "sub.srt",
+            OUTPUT_ROOT / request.episode_id / f"{request.episode_id}.srt",
+            OUTPUT_ROOT / f"{request.episode_id}.srt",
+            OUTPUT_ROOT / request.episode_id / "sub.srt",
         ]
         for path in possible_paths:
-            if path.exists():
-                file_path = path
+            resolved = _resolve_output_path(path)
+            if resolved.exists():
+                file_path = resolved
                 break
@@
-    subtitles = parse_srt_file(file_path)
+    subtitles = parse_srt_file(_resolve_output_path(file_path))
@@
-        output_path = file_path.parent / f"{file_path.stem}_fixed.srt"
+        output_path = _resolve_output_path(file_path.parent / f"{file_path.stem}_fixed.srt")
         success = save_srt_file(fixed_subtitles, output_path)
```

```diff
--- a/frontend/package.json
+++ b/frontend/package.json
@@
   "devDependencies": {
+    "@typescript-eslint/eslint-plugin": "^8.12.1",
     "@types/node": "^20.19.24",
     "@types/react": "^19.2.2",
     "@types/react-dom": "^19.2.2",
@@
--- a/frontend/.eslintrc.json
+++ b/frontend/.eslintrc.json
@@
 {
   "extends": [
     "next/core-web-vitals",
     "prettier"
   ],
+  "plugins": [
+    "@typescript-eslint"
+  ],
   "rules": {
     "react/no-unescaped-entities": "off",
     "@typescript-eslint/no-unused-vars": [
       "warn",
       {
         "argsIgnorePattern": "^_",
         "varsIgnorePattern": "^_"
       }
     ]
   }
 }
```

## Validation Steps
- Restart backend in non-mock mode and confirm OpenAPI advertises T2R routes: `curl -s http://localhost:8000/openapi.json | jq '.paths | keys[]' | grep '/api/episodes/plan'`.
- Re-run the baseline script: `bash scripts/verify_sprint6.sh` (expect concrete JSON, no `null` entries).
- WebSocket smoke: `. backend/.venv/bin/activate && python audit/ws_probe.py` (use prior snippet, expect `message_count >= 20`, strictly increasing versions, avg latency < 0.5 s).
- Security regression: `curl -s -X POST http://localhost:8000/api/t2r/srt/inspect -H 'Content-Type: application/json' -d '{"file_path":"../config/schedule_master.json"}'` should now return HTTP 400.
- Frontend build: `pnpm -C frontend install` (to pick up the plugin) then `pnpm -C frontend build` – ensure Next outputs bundle stats and exits 0; record size in `audit/build_stats.txt`.
- Optional slimming check: `pnpm -C frontend prune --prod && du -sh frontend/node_modules` to verify staying below the 300 MB target.

## Residual Risk & Defer List
- Resume orchestration still requires endpoint work (F4); implementation should persist requested stage order in the journal to drive resumptions safely.
- Node_modules remains >300 MB until large charting/virtualisation libraries are split or made optional; consider `next/dynamic` + vendor chunking.
- WS client/server ping schema (F7) still needs harmonising to avoid stale connection churn; track as follow-up once core stream is restored.
- Health endpoint currently reports `mode: "mock"` because Redis/database dependencies fail to load locally; prod-ready environment variables must be validated before release.
