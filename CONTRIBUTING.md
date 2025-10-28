# 🤝 Contributing to Vibe Coding Infra

Thank you for your interest in advancing **Vibe Coding Infra**!  
This repository follows the **Vibe Coding Master Prompt v1.0** principles:  
**Structured · Reproducible · Maintainable · Deployable · Extensible**

## 🌍 Core Expectations
- Keep code modular, documented, and battle-tested.
- Preserve deterministic tooling (pin dependencies, document scripts).
- Extend the scaffold without breaking baseline automation.

## 🧭 Folder Overview
| Folder | Purpose |
|--------|---------|
| `src/` | Primary application code and domain modules |
| `blueprints/` | Automation recipes, prompt blueprints, and workflows |
| `config/` | Environment variables, feature flags, deployment settings |
| `automation/` | Repeatable operational scripts |
| `media/` | Creative assets for demos and validation |
| `docs/` | Architecture, design records, and onboarding |
| `tests/` | Unit, integration, and regression suites |
| `deploy/` | Deploy scripts, container configs, and infrastructure |

## 🧩 Getting Started
1. Fork or clone the repository.
2. Run `./init_vibe_repo.sh` to verify the scaffold.
3. Create a Python virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## 🛠️ Contribution Flow
1. Create a feature branch from `main`.
2. Make focused commits with descriptive messages.
3. Write or update tests with each change.
4. Run `pytest` (and additional project checks) before submitting a PR.
5. Document noteworthy design decisions in `docs/`.

## ✅ Code Review Checklist
- [ ] Code paths have deterministic behavior and clear error handling.
- [ ] Public interfaces and scripts include docstrings or header comments.
- [ ] Tests cover new logic and edge cases.
- [ ] Documentation reflects schema or workflow changes.
- [ ] Deployment manifests remain valid (check `deploy/`).

## 📬 Questions?
Open an issue with the `discussion` label or ping a maintainer directly.
