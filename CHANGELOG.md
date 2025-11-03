# Changelog

All notable changes to Kat Records Studio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2025-11-04

### Added
- **Complete README Rewrite** - Modern, comprehensive documentation with clear structure
- **Packaging Guide** - Detailed `docs/PACKAGING.md` with distribution instructions
- **MRRC System** - Automated maintenance, refactoring, and release cycle tool
- **Version Management** - Proper semantic versioning and changelog tracking

### Changed
- **README.md**: Complete rewrite with better organization, examples, and documentation links
- **Project Version**: Upgraded from 0.1.0 to 1.2.0 (major version bump for stability)
- **Documentation Structure**: Enhanced with packaging, distribution, and MRRC documentation
- **Code Quality Metrics**: Documented (type hints: 72.2%, print statements: 2,207)

### Fixed
- Obsolete files removed (`config/pppproduction_log.json`)
- Documentation links validated and updated
- Project structure clarified in documentation

---

## [Unreleased]

### Added
- **MRRC (Maintenance, Refactoring & Release Cycle)** - Comprehensive project cleanup and standardization system
  - Automated maintenance pass for scaffolding and deprecated files
  - Refactoring pass for code quality improvements
  - Documentation pass for link validation and updates
  - Logging standardization and stability checks
  - Release preparation with dependency validation

### Changed
- Removed obsolete `config/pppproduction_log.json` file (deprecated, contained DEMO references)
- Standardized project structure and removed temporary scaffolding code

### Fixed
- Type hint coverage improved to 72.2%
- Identified and documented 2207 print() statements for future logging migration

---

## [0.1.0] - 2025-11-04

### Added
- **YouTube Upload Integration** - Complete Stage 10 workflow implementation
  - OAuth 2.0 authentication with token caching
  - Resumable video upload with retry mechanism
  - Automatic metadata reading from episode files
  - Playlist integration support
  - Subtitle upload with language detection
  - Thumbnail auto-resizing
  - Scheduled publishing support
- **CLI Integration** - Upload functionality integrated into `kat_cli.py`
- **Terminal Menu Integration** - Upload functionality added to interactive terminal (`kat_terminal.py`)
- **Enhanced YouTube Metadata Builder** - Comprehensive metadata payload with all standard fields
- **State Management** - Added `STATUS_UPLOADING` and YouTube metadata fields to `state_manager.py`
- **Event Bus** - Upload-related events (`UPLOAD_STARTED`, `UPLOAD_COMPLETED`, `UPLOAD_FAILED`)

### Changed
- Refactored upload logic from subprocess calls to direct function imports
- Improved error messages for API configuration and authentication failures
- Enhanced auto-detection logic for video files and metadata

### Fixed
- Removed `topicDetails` from YouTube API payload (read-only field)
- Fixed import errors in `kat_cli.py` with proper `sys.path` configuration
- Improved subtitle language detection from filename patterns

---

## [0.0.1] - 2025-11-02

### Added
- **Phase IV Completion** - Architecture consistency and cleanup
  - Removed all DEMO-related logic and folder structure
  - Unified state management architecture
  - Documentation consistency fixes
  - Complete migration from `production_log` to unified state
- **Unified Workflow Dashboard** - 9-stage workflow visualization
- **Real-time Status Sync** - Automatic file change detection and status updates
- **Breadth-First Generation** - Stage-by-stage batch processing across all episodes

### Changed
- **State Management**: Migrated from multi-source to single source of truth (`schedule_master.json`)
- **Documentation**: Consolidated 27 documents to 16 (-41% reduction)
- **Output Directory**: Unified structure to `output/{YYYY-MM-DD}_{Title}/`

### Fixed
- File existence checks in breadth-first generation
- Event bus state manager null handling
- Broken documentation links
- Function signature consistency

---

---

## Notes

### MRRC Cycle

The project now follows a regular **MRRC (Maintenance, Refactoring & Release Cycle)** to ensure code quality and consistency:

1. **Maintenance Pass**: Remove scaffolding, deprecated files, and unused imports
2. **Refactoring Pass**: Apply PEP8, type hints, replace print() with logging
3. **Documentation Pass**: Update docs, validate links, generate changelog
4. **Logging & Stability Pass**: Standardize log levels, verify state transitions
5. **Release Preparation**: Run tests, check dependencies, validate system

Run MRRC cycle:
```bash
python scripts/mrrc_cycle.py [--dry-run] [--phase PHASE]
```

---

