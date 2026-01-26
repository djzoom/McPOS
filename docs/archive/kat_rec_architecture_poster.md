```mermaid
flowchart LR
    %% ========== SYSTEM ROOT STRUCTURE ==========
    subgraph USER[User]
        U1(User clicks cell)
        U2(User opens TaskPanel)
        U3(User watches progress)
    end

    %% ========== FRONTEND UI ==============
    subgraph FE[Frontend (Next.js + React)]
        OG[OverviewGrid]
        TP[TaskPanel]
        GPS[GridProgressSimple]

        subgraph Hooks[Hooks (Stateflow V4)]
            UA[useEpisodeAssets]
            VP[useVideoProgress]
            US[useUploadState]
        end

        FE_STACK[Zustand Stores]
    end

    USER --> U1 --> OG
    USER --> U2 --> TP
    USER --> U3 --> GPS

    %% ========== BACKEND API ==============
    subgraph BE[Backend API Layer (FastAPI)]
        EP_API[/GET /episodes/{id}/assets/]
        VP_API[/GET /episodes/{id}/video-progress/]
        META_API[/GET /episodes/{id}/metadata/]

        WS_API[/WebSocket Hub/]

        RQ_API[/render_queue/]
        UQ_API[/upload_queue/]
        VW_API[/verify_worker/]
    end

    OG --> FE_STACK
    TP --> FE_STACK

    %% ========== FILESYSTEM (SSOT) ============
    subgraph FS[Filesystem SSOT (Single Source of Truth)]
        DIR[channels/<channel>/output/<episode>/]
        MIX[episode_full_mix.mp3]
        TIMELINE[episode_timeline.csv]
        COVER[cover.png]
        VIDEO[episode_youtube.mp4]
        RFLAG[render_complete.flag]
        ULOG[upload_log.json]
        DESC[description.txt]
    end

    %% API to FS
    EP_API --> FS
    VP_API --> FS
    META_API --> FS

    %% Hooks to API
    UA --> EP_API
    VP --> VP_API
    US --> ULOG

    OG --> UA
    OG --> VP
    OG --> US

    TP --> UA
    TP --> VP
    TP --> US

    GPS --> UA
    GPS --> VP
    GPS --> US

    %% ========== RENDER PIPELINE ============
    subgraph RENDER[Render Pipeline]
        RQ_SVC[RenderQueue Service]
        RPS[render_progress_service.py]
    end

    RQ_API --> RQ_SVC
    RQ_SVC --> FS
    FS --> RPS
    RPS --> VP_API

    %% ========== UPLOAD / VERIFY PIPELINE ============
    subgraph UPLOAD[Upload + Verify Pipeline]
        UQ_SVC[UploadQueue Service]
        VW_SVC[Verify Worker]
    end

    UQ_API --> UQ_SVC --> FS
    FS --> VW_SVC --> FS

    FS --> ULOG --> US

    %% ========== SCHEDULE SYSTEM ============
    subgraph SCHED[Schedule Mapping]
        SCH[/schedule_master.json/]
    end

    SCH --> OG
    SCH --> TP

    %% ========== EPISODE FLOW (V4 reduced) ============
    subgraph FLOW[EpisodeFlow (V4 Simplified)]
        INIT[init_episode]
        REMIX[remix_audio]
        COVER_ST[cover_generate]
        TEXT[text_assets]
        RENDER_ST[render_queue_trigger]
        UPLOAD_ST[upload_queue_trigger]
        VERIFY_ST[verify_worker_trigger]
        DONE[complete]
    end

    INIT --> REMIX --> COVER_ST --> TEXT --> RENDER_ST --> UPLOAD_ST --> VERIFY_ST --> DONE

    %% EpisodeFlow triggers real queues
    RENDER_ST --> RQ_API
    UPLOAD_ST --> UQ_API
    VERIFY_ST --> VW_API

    %% ========== WEBSOCKET EVENT SYSTEM ============
    subgraph WS[WebSocket Events (Unified V4)]
        ASSET_EV[t2r.episode.assets_updated]
        RENDER_EV[t2r.episode.render_updated]
        UPLOAD_EV[t2r.episode.upload_updated]
        VERIFY_EV[t2r.episode.verify_updated]
    end

    WS_API --> FE
    RQ_SVC --> RENDER_EV --> WS_API
    UQ_SVC --> UPLOAD_EV --> WS_API
    VW_SVC --> VERIFY_EV --> WS_API

    EP_API --> ASSET_EV --> WS_API

    %% FE refresh
    WS_API --> OG
    WS_API --> TP
    WS_API --> GPS
```
