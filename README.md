# 🌐 Vibe Coding Infra Template

The **Vibe Coding Infra** template delivers a structured, reproducible, maintainable, deployable, and extensible foundation for creative automation, media tooling, and interactive systems.

## 🧠 Why Vibe Coding
- Repeatable scaffolds for web, automation, media, and experimental projects
- Convention-driven organization aligned to the Vibe Coding Master Prompt v1.0
- Ready-to-extend configuration, testing, and deployment blueprints

## 🗂️ Repository Layout
| Path | Purpose |
|------|---------|
| `src/` | Application source modules |
| `blueprints/` | JSON / YAML automation recipes |
| `config/` | Environment variables and runtime settings |
| `automation/` | Task runners, CLI tools, schedulers |
| `media/` | Audio, video, and creative assets |
| `docs/` | Architecture, ADRs, onboarding notes |
| `tests/` | Unit and integration tests |
| `deploy/` | CI/CD, Docker, and infrastructure manifests |
| `.vscode/` | Workspace defaults for editors |

## 🚀 Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

## 🧪 Quality Gateway
```bash
pytest
```

## 🔄 Deployment & Automation
- `docker-compose up` spins up the sample service topology.
- `make bootstrap` installs dependencies and prepares the environment.
- `make lint` runs static checks (plug-in your preferred tools).

## 🤝 Contributing
See `CONTRIBUTING.md` for full guidelines and commit conventions.
