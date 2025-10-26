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


🌱 How to Reuse the Vibe Coding Infra Template

🌱 如何复用 Vibe Coding Infra 模板

⸻

🧩 1. What Is It? / 它是什么？

English:
Vibe Coding Infra is a reproducible project template designed for creative automation, AI tools, and media systems.
It gives you a ready-made structure — code, prompts, deployment, and documentation — so every new project starts from a clean, consistent base.

中文：
Vibe Coding Infra 是一个可复现的工程模板，用于创意自动化、AI 工具与媒体系统。
它提供统一的目录结构、提示词规范、部署脚本与文档体系，让每个新项目都能从清晰一致的基础出发。

⸻

⚙️ 2. Reuse Steps / 复用步骤

Step	English Description	中文说明
1️⃣ Copy Template	Clone or copy the Vibe-Coding-Infra folder to a new location.	复制或克隆 Vibe-Coding-Infra 文件夹到新目录。
2️⃣ Rename Project	Rename the folder to your new project name (e.g. rbr-autostream-system).	将文件夹重命名为新项目名称（如 rbr-autostream-system）。
3️⃣ Open in VS Code	In VS Code: File → Open Folder.	在 VS Code 中选择 “文件 → 打开文件夹”。
4️⃣ Initialize Environment	Run: python3 -m venv .venvsource .venv/bin/activatepip install -r requirements.txt	初始化虚拟环境并安装依赖：创建虚拟环境 → 激活 → 安装依赖。
5️⃣ Create Prompt File	In /vibe_prompt/, duplicate master_prompt.json and rename it. Fill in your GOAL, OBJECTIVE, STACK, etc.	在 /vibe_prompt/ 中复制 master_prompt.json 并改名。填写项目目标、任务描述、技术栈等。
6️⃣ Add Modules	Add or import modules under /src/modules/.	在 /src/modules/ 下添加或导入模块。
7️⃣ Run the Project	Run main.py via Ctrl + Alt + N or in terminal: python main.py.	使用 Ctrl + Alt + N 或终端命令运行 main.py。
8️⃣ Version Control (Optional)	Initialize Git: git init && git add . && git commit -m "init"	初始化 Git 仓库并提交版本。
9️⃣ Update README	Describe your new project and how to run it.	更新 README.md，记录项目说明与运行方式。


⸻

🧰 3. Useful VS Code Shortcuts / 实用 VS Code 快捷键

Action	Shortcut	中文说明
Open Terminal	Ctrl + `	打开终端
Run Code	Ctrl + Alt + N	运行当前文件（需安装 Code Runner 插件）
Save File	Ctrl + S	保存文件
Show Sidebar	Ctrl + B	展开/隐藏文件树
Global Search	Ctrl + Shift + F	全局搜索文本
Go to Definition	F12	跳转到定义
Start Debugging	F5	启动调试模式


⸻

🚀 4. Quick Checklist / 快速清单

English

✅ Copy template
✅ Rename project
✅ Open in VS Code
✅ Setup virtual environment
✅ Fill new master prompt
✅ Add / import modules
✅ Run and debug
✅ Update README
✅ Commit to Git

