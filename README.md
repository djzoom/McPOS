# 🎵 Kat Records Studio

**Version**: 1.2.0  
**Automated Lo-Fi Music Mixtape Generation System**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

---

## 📋 Overview

Kat Records Studio is a fully automated Lo-Fi music mixtape generation system that produces professional-quality albums from your music library. The system automatically selects tracks, generates album covers, mixes audio, renders 4K videos, and uploads to YouTube—all with minimal manual intervention.

### Key Features

- 🎵 **Intelligent Track Selection** - Smart A/B-side grouping from your music library
- 🎨 **AI-Powered Cover Generation** - Beautiful 4K album covers with title integration
- 🎬 **4K Video Rendering** - Professional video production with multiple encoder support
- 📊 **Unified State Management** - Single source of truth architecture for data consistency
- 📈 **Real-time Metrics** - Comprehensive monitoring and analytics system
- 🔄 **Automatic Recovery** - One-click recovery for failed episodes
- 📝 **Structured Logging** - JSON-formatted logs for all system events
- 📤 **YouTube Integration** - Complete Stage 10 workflow with OAuth, resumable uploads, and playlist support
- 🧹 **MRRC System** - Automated maintenance and code quality management

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- FFmpeg (for audio/video processing)
- ImageMagick or Pillow (for image processing)
- OpenAI API key (for AI-generated titles)
- Google OAuth credentials (for YouTube upload)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd Kat_Rec

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Initial Setup

1. **Generate Song Library Index**
```bash
python scripts/local_picker/generate_song_library.py
```

2. **Configure API Keys**
```bash
# Copy example config
cp config/config.example.yaml config/config.yaml

# Edit config.yaml with your API keys
# Or use interactive setup:
python scripts/kat_terminal.py  # Select "System Config" → "Configure API Keys"
```

3. **Create Schedule**
```bash
# Create a 15-episode schedule (releases every 2 days)
python scripts/local_picker/create_schedule_master.py --episodes 15

# Or use interactive terminal:
python scripts/kat_terminal.py  # Select "Schedule Management" → "Create Schedule"
```

---

## 🎯 Usage

### Interactive Terminal (Recommended for Beginners)

The easiest way to use Kat Records Studio:

```bash
python scripts/kat_terminal.py
```

**Features**:
- Beautiful menu-driven interface
- Real-time status displays
- Built-in help system
- Safe defaults for all operations

**Main Menu Options**:
1. 📊 View Schedule Status
2. 🎬 Quick Generate Episode
3. 🔍 Check File Status
4. 📚 Resource Library Management
5. 📅 Schedule Management
6. 🎵 Content Generation (Stages 3-10)
7. ⚙️ System Configuration & Status
8. 📖 Help Documentation

### Command Line Interface (CLI)

For automation and scripting:

```bash
# Generate a single episode
python scripts/kat_cli.py generate --episode 20251104

# Batch generate all pending episodes
python scripts/kat_cli.py batch --all

# Upload to YouTube
python scripts/kat_cli.py upload --episode 20251104 --privacy unlisted

# View schedule status
python scripts/kat_cli.py status

# Check system health
python scripts/kat_cli.py health
```

### Breadth-First Generation (Recommended for Production)

Generate all episodes stage-by-stage across all episodes:

```bash
python scripts/local_picker/breadth_first_generate.py --all

# Or with specific options:
python scripts/local_picker/breadth_first_generate.py \
  --force \              # Force regeneration
  --skip-stage 4,5 \    # Skip specific stages
  --no-pause            # Run without pauses
```

**Stages**:
1. Track Selection & Scheduling
2. Image Extraction
3. Title Generation
4. YouTube Title Creation
5. Description Generation
6. Cover Rendering
7. Audio Mixing
8. Video Rendering
9. YouTube Assets Generation
10. **YouTube Upload** ← Complete publishing pipeline

---

## 📂 Project Structure

```
Kat_Rec/
├── assets/                    # Resource files
│   ├── design/               # Cover image library
│   ├── fonts/                # Font files
│   └── sfx/                  # Sound effects
├── config/                   # Configuration files
│   ├── config.yaml           # Main configuration (create from example)
│   ├── config.example.yaml   # Configuration template
│   ├── workflow.yml          # Workflow stage definitions
│   └── schedule_master.json  # Single source of truth (episode states)
├── data/                     # Data files
│   ├── song_library.csv      # Music library index
│   ├── metrics.json          # System metrics
│   └── workflow_status.json  # Workflow execution status
├── output/                    # Generated content
│   └── {YYYY-MM-DD}_{Title}/ # Per-episode folders
│       ├── {episode_id}_youtube.mp4
│       ├── {episode_id}_youtube_title.txt
│       ├── {episode_id}_youtube_description.txt
│       ├── {episode_id}_youtube.srt
│       ├── {episode_id}_cover.png
│       └── {episode_id}_youtube_upload.json
├── logs/                      # System logs
│   ├── katrec.log            # Structured JSON logs
│   └── system_events.log     # Event history
├── src/                       # Core modules
│   └── core/
│       ├── state_manager.py   # Unified state management
│       ├── event_bus.py       # Event-driven architecture
│       ├── metrics_manager.py # Metrics collection
│       └── logger.py         # Structured logging
├── scripts/                   # Executable scripts
│   ├── kat_cli.py            # Command-line interface
│   ├── kat_terminal.py       # Interactive terminal
│   ├── mrrc_cycle.py         # Maintenance & refactoring cycle
│   ├── local_picker/         # Core generation scripts
│   └── uploader/             # YouTube upload module
├── tests/                     # Test suite
│   └── test_consistency.py   # System consistency tests
└── docs/                      # Documentation
    ├── ARCHITECTURE.md       # System architecture
    ├── DEVELOPMENT.md        # Development log
    ├── ROADMAP.md           # Future plans
    └── ...
```

---

## 🔧 Core Features

### 1. Unified State Management

**Single Source of Truth**: `config/schedule_master.json`

- ✅ **Atomic Writes**: Temporary files → rename to prevent corruption
- ✅ **Concurrency Control**: Prevents simultaneous updates
- ✅ **Event-Driven**: Automatic state updates via event bus
- ✅ **Automatic Rollback**: Failed operations restore previous state

### 2. Event-Driven Architecture

All state changes flow through the event bus:

```
Action → Event Bus → State Manager → schedule_master.json
              ↓
       Metrics Manager → metrics.json
              ↓
       Structured Logger → logs/katrec.log
```

**Event Types**:
- `REMIX_STARTED`, `REMIX_COMPLETED`, `REMIX_FAILED`
- `VIDEO_RENDER_STARTED`, `VIDEO_RENDER_COMPLETED`, `VIDEO_RENDER_FAILED`
- `UPLOAD_STARTED`, `UPLOAD_COMPLETED`, `UPLOAD_FAILED`
- `STAGE_STARTED`, `STAGE_COMPLETED`, `STAGE_FAILED`

### 3. YouTube Integration (Stage 10)

Complete end-to-end publishing pipeline:

**Features**:
- OAuth 2.0 authentication with automatic token refresh
- Resumable video upload (supports files >256MB)
- Automatic metadata reading from episode files
- Playlist integration
- Subtitle upload with language detection
- Thumbnail auto-resizing
- Scheduled publishing support

**Usage**:
```bash
# Basic upload
python scripts/kat_cli.py upload --episode 20251104

# With options
python scripts/kat_cli.py upload \
  --episode 20251104 \
  --privacy unlisted \
  --schedule \
  --playlist-id PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Or via interactive terminal
python scripts/kat_terminal.py
# Select: Content Generation → Upload to YouTube
```

### 4. MRRC (Maintenance, Refactoring & Release Cycle)

Automated code quality and maintenance system:

```bash
# Preview changes
python scripts/mrrc_cycle.py --dry-run

# Run specific phase
python scripts/mrrc_cycle.py --phase maintenance

# Full cycle
python scripts/mrrc_cycle.py
```

**Phases**:
1. **Maintenance Pass**: Remove deprecated files and scaffolding
2. **Refactoring Pass**: Code quality improvements, type hints, PEP8
3. **Documentation Pass**: Update docs, validate links
4. **Logging & Stability Pass**: Standardize logging, verify state transitions
5. **Release Preparation**: Run tests, check dependencies

---

## 📊 State Management

### Episode States

```python
STATUS_PENDING = "pending"      # Awaiting production
STATUS_REMIXING = "remixing"    # Mixing audio
STATUS_RENDERING = "rendering"  # Rendering video
STATUS_UPLOADING = "uploading"  # Uploading to YouTube
STATUS_COMPLETED = "completed"  # Fully completed
STATUS_ERROR = "error"          # Requires manual intervention
```

### State Transitions

Valid state transitions:

```
pending → remixing → rendering → uploading → completed
   ↓         ↓          ↓           ↓
  error     error      error      error
   ↓
(recovers to pending or remixing)
```

---

## 🛠️ Development

### Adding New Features

1. **State Updates**: Use `StateManager.update_status()`
2. **Event Triggering**: Use `EventBus.emit_xxx()`
3. **Metrics**: Automatically collected by event bus
4. **Logging**: Structured logs automatically recorded

### Running Tests

```bash
# All tests
pytest tests/ -v

# Consistency tests
pytest tests/test_consistency.py -v

# Specific test
pytest tests/test_consistency.py::test_state_transitions -v
```

### Code Quality

```bash
# Run MRRC cycle
python scripts/mrrc_cycle.py

# Check code quality metrics
python scripts/mrrc_cycle.py --phase refactoring
```

**Current Metrics**:
- Type hint coverage: 72.2% (target: 80%+)
- Print statements: 2,207 (gradual migration to logging)
- PEP8 compliance: Validated

---

## 📦 Packaging & Distribution

See [Packaging Guide](docs/PACKAGING.md) for detailed instructions.

### Quick Package

```bash
# Create distribution package
bash scripts/package.sh v1.2.0

# Output: kat-rec-v1.2.0.tar.gz and kat-rec-v1.2.0.zip
```

### Package Contents

- All source code and scripts
- Configuration templates
- Documentation
- Required assets (fonts, templates)
- **Excludes**: `.venv/`, `output/`, `logs/`, API keys, personal data

---

## 📚 Documentation

### Essential Reading

- **[Architecture Guide](docs/ARCHITECTURE.md)** - System architecture and design principles
- **[Development Log](docs/DEVELOPMENT.md)** - Development history and achievements
- **[Roadmap](docs/ROADMAP.md)** - Future plans and improvements
- **[Changelog](CHANGELOG.md)** - Version history and changes
- **[Packaging Guide](docs/PACKAGING.md)** - Distribution and deployment

### Quick References

- **[Command Line Workflow](docs/COMMAND_LINE_WORKFLOW.md)** - Production workflows
- **[Schedule Master Guide](docs/SCHEDULE_MASTER_GUIDE.md)** - Schedule management
- **[Terminal Guide](docs/TERMINAL_GUIDE.md)** - Interactive terminal usage
- **[YouTube Upload Guide](docs/YOUTUBE_UPLOAD_GUIDE.md)** - YouTube integration
- **[Quick Start YouTube](docs/QUICK_START_YOUTUBE.md)** - YouTube setup guide

### Complete Documentation Index

See [docs/README.md](docs/README.md) for the full documentation catalog.

---

## ⚠️ Important Notes

### Data Integrity

1. **Single Source of Truth**: Always use `StateManager` for state updates—never modify JSON files directly
2. **Atomic Writes**: All file operations use temporary files → rename for safety
3. **Concurrency**: The system handles concurrent access, but avoid simultaneous updates to the same episode
4. **Log Rotation**: Logs automatically rotate (max 5MB, keep 5 files)

### Best Practices

- ✅ Use interactive terminal for exploration and learning
- ✅ Use CLI for automation and scripting
- ✅ Use breadth-first generation for production batches
- ✅ Run MRRC cycle regularly (recommended: every 2-4 weeks)
- ✅ Keep configuration files version-controlled (exclude secrets)

---

## 🔄 Version History

**Current Version**: 1.2.0

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

### Recent Versions

- **1.2.0** (Current) - MRRC system, comprehensive cleanup, documentation overhaul
- **0.1.0** - YouTube upload integration (Stage 10), CLI integration
- **0.0.1** - Unified state management, breadth-first generation

---

## 📝 License

Copyright © 2025 Kat Records. All rights reserved.

---

## 🙏 Acknowledgments

Special thanks to all contributors and the open-source community for inspiration and tools that made this project possible.

---

## 🆘 Support

- **Documentation**: See `docs/` directory
- **Issues**: Check existing documentation and logs first
- **Development**: See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for technical details

---

**Last Updated**: 2025-11-04  
**MRRC Cycle**: 2025-11-04  
**Status**: ✅ Stable & Production Ready
