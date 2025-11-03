# Packaging & Distribution Guide

**Version**: 1.2.0  
**Last Updated**: 2025-11-04

---

## 📦 Overview

This guide explains how to package and distribute Kat Records Studio for deployment or sharing.

---

## 🎯 Packaging Options

### 1. Source Distribution (Recommended)

**Purpose**: Share the complete source code with all assets

**Files Included**:
- All Python source code
- Configuration templates
- Documentation
- Required assets (fonts, design templates)
- Scripts and utilities

**Files Excluded**:
- `.venv/` and virtual environments
- `output/` (generated content)
- `logs/` (runtime logs)
- `config/*_api_key.txt` (API secrets)
- `config/client_secrets.json` (OAuth credentials)
- `config/youtube_token.json` (OAuth tokens)
- `config/schedule_master.json` (runtime data)
- `data/song_library.csv` (personal data)

### 2. Application Bundle (macOS)

**Purpose**: Create a standalone macOS application

**Requirements**:
- macOS development environment
- Xcode Command Line Tools

**Files**:
- `Kat Records.app` - Standalone application bundle
- `scripts/create_app.sh` - Application creation script

---

## 🚀 Quick Package

### Using Package Script

```bash
# Create versioned package
bash scripts/package.sh v1.2.0

# Output files:
# - kat-rec-v1.2.0.tar.gz
# - kat-rec-v1.2.0.zip
```

**Package Script Features**:
- ✅ Excludes sensitive data automatically
- ✅ Creates version information file
- ✅ Generates both tar.gz and zip formats
- ✅ Calculates package sizes
- ✅ Validates package contents

### Manual Packaging

```bash
# 1. Clean temporary files
python scripts/mrrc_cycle.py --phase maintenance

# 2. Create distribution directory
mkdir -p dist/kat-rec-1.2.0

# 3. Copy files (exclude sensitive data)
rsync -av \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='output' \
  --exclude='.git' \
  --exclude='config/*_api_key.txt' \
  --exclude='config/client_secrets.json' \
  --exclude='config/youtube_token.json' \
  --exclude='logs' \
  . dist/kat-rec-1.2.0/

# 4. Create archives
cd dist
tar -czf kat-rec-1.2.0.tar.gz kat-rec-1.2.0/
zip -r kat-rec-1.2.0.zip kat-rec-1.2.0/
```

---

## 📋 Package Contents Checklist

### Required Files

- ✅ `README.md` - Project documentation
- ✅ `CHANGELOG.md` - Version history
- ✅ `requirements.txt` - Python dependencies
- ✅ `pyproject.toml` - Project metadata
- ✅ `config/config.example.yaml` - Configuration template
- ✅ `scripts/` - All executable scripts
- ✅ `src/` - Core modules
- ✅ `assets/` - Design assets (fonts, templates)
- ✅ `docs/` - Documentation

### Excluded Files

- ❌ `.venv/` - Virtual environment
- ❌ `output/` - Generated content
- ❌ `logs/` - Runtime logs
- ❌ `.git/` - Version control
- ❌ `__pycache__/` - Python cache
- ❌ `*.pyc` - Compiled Python files
- ❌ API keys and secrets
- ❌ Personal data files

### Version Information

The package script automatically creates `VERSION.txt`:

```
Kat Records Studio
Version: 1.2.0
Packaged: 2025-11-04 12:00:00
Python: 3.11.x
```

---

## 🍎 macOS Application Bundle

### Creating the App

```bash
# Run the app creation script
bash scripts/create_app.sh

# Output: Kat Records.app
```

### App Bundle Structure

```
Kat Records.app/
├── Contents/
│   ├── Info.plist        # Application metadata
│   ├── MacOS/
│   │   └── kat_rec       # Main executable
│   └── Resources/
│       └── AppIcon.icns  # Application icon
```

### Installing the App

1. Drag `Kat Records.app` to `/Applications/`
2. Right-click → Open (first time only, to bypass Gatekeeper)
3. Or use: `xattr -cr Kat\ Records.app` to remove quarantine

---

## 📤 Distribution Methods

### 1. Archive Files

**Best for**: Source code sharing, development setup

**Formats**:
- `.tar.gz` - Standard Unix archive
- `.zip` - Universal archive

**Usage**:
```bash
# Extract
tar -xzf kat-rec-1.2.0.tar.gz
# or
unzip kat-rec-1.2.0.zip

# Setup
cd kat-rec-1.2.0
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Git Repository

**Best for**: Version control, collaborative development

```bash
# Clone
git clone <repository-url>

# Checkout specific version
git checkout v1.2.0
```

### 3. Application Bundle

**Best for**: End-user distribution (macOS only)

- Drag-and-drop installation
- No command-line setup required
- Includes all dependencies (if bundled)

---

## 🔒 Security Considerations

### Sensitive Data Exclusion

The packaging scripts automatically exclude:

- **API Keys**: `config/*_api_key.txt`, `config/*_secret.txt`
- **OAuth Credentials**: `config/client_secrets.json`, `config/youtube_token.json`
- **Personal Data**: `data/song_library.csv`, `config/schedule_master.json`
- **Runtime Logs**: `logs/*.log`

### Configuration Templates

Always include:
- ✅ `config/config.example.yaml` - Template with placeholder values
- ✅ `config/workflow.yml` - Workflow definitions (no secrets)

### Verification

Before distribution, verify:

```bash
# Check for accidentally included secrets
grep -r "sk-" dist/kat-rec-1.2.0/  # OpenAI keys
grep -r "AIza" dist/kat-rec-1.2.0/  # Google API keys
grep -r "client_secret" dist/kat-rec-1.2.0/

# Should return no results
```

---

## 📊 Package Validation

### Size Check

```bash
# Check package sizes
ls -lh kat-rec-*.tar.gz kat-rec-*.zip

# Expected sizes (approximate):
# - tar.gz: 5-10 MB (depending on assets)
# - zip: 6-12 MB
```

### Content Validation

```bash
# List package contents
tar -tzf kat-rec-1.2.0.tar.gz | head -20

# Check for required files
tar -tzf kat-rec-1.2.0.tar.gz | grep -E "(README|CHANGELOG|requirements|pyproject)"
```

### Installation Test

```bash
# Test installation in clean environment
mkdir test_install
cd test_install
tar -xzf ../kat-rec-1.2.0.tar.gz
cd kat-rec-1.2.0

# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify
python scripts/kat_cli.py --help
```

---

## 🔄 Version Management

### Version Numbering

Follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.x.x): Breaking changes
- **MINOR** (x.2.x): New features, backward compatible
- **PATCH** (x.x.0): Bug fixes, backward compatible

### Version Files

Update these files for each release:

1. `pyproject.toml` - `version = "1.2.0"`
2. `README.md` - Version badge and changelog reference
3. `CHANGELOG.md` - Add new version entry
4. `docs/ARCHITECTURE.md` - Update last modified date

### Release Checklist

- [ ] Run full MRRC cycle
- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md`
- [ ] Update `README.md` version references
- [ ] Run tests: `pytest tests/ -v`
- [ ] Create package: `bash scripts/package.sh v1.2.0`
- [ ] Verify package contents
- [ ] Test installation in clean environment
- [ ] Create git tag: `git tag v1.2.0`
- [ ] Push tag: `git push origin v1.2.0`

---

## 📝 Distribution Notes

### For End Users

Include a `INSTALL.txt` or `SETUP.md` with:

1. System requirements
2. Installation steps
3. Configuration instructions
4. First-time setup guide
5. Troubleshooting tips

### For Developers

Include:

1. Development setup guide
2. Architecture documentation
3. Contribution guidelines
4. Testing instructions
5. MRRC cycle documentation

---

## 🛠️ Advanced Packaging

### Docker Container

```dockerfile
# Dockerfile example (if needed)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "scripts/kat_terminal.py"]
```

### Python Package

```bash
# Build Python package
python -m build

# Install locally
pip install dist/kat_rec-1.2.0-py3-none-any.whl
```

---

## 📞 Support

For packaging issues or questions:

1. Check `scripts/package.sh` for exclusion patterns
2. Review `CHANGELOG.md` for recent changes
3. See `docs/ARCHITECTURE.md` for system structure
4. Run MRRC cycle for code quality validation

---

**Last Updated**: 2025-11-04  
**Version**: 1.2.0

