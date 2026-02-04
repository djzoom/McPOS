# McPOS CLI 使用指南

## 快速开始

### 前提条件

1. **激活虚拟环境**（如果使用 `.venv311`）：
   ```bash
   source .venv311/bin/activate
   ```

2. **安装依赖**（包含 OpenAI client，用于 TEXT_BASE）：
   ```bash
   pip install -r requirements.txt
   pip install -e .  # 可选，安装后可直接用 mcpos 命令
   ```

### 使用方法

**方法 1：使用临时脚本（推荐，无需安装）**
```bash
# 确保虚拟环境已激活
source .venv311/bin/activate

# 运行 CLI
python3 mcpos_cli.py init-episode kat kat_2025test01
python3 mcpos_cli.py run-episode kat kat_2025test01
```

**方法 2：使用 mcpos 命令（需要先安装）**
```bash
# 确保虚拟环境已激活
source .venv311/bin/activate

# 安装项目（如果还没安装）
pip install -e .

# 使用 mcpos 命令
mcpos init-episode kat kat_2025test01
mcpos run-episode kat kat_2025test01
```

## 可用命令

### init-episode
初始化单期节目，生成 `playlist.csv` 和 `recipe.json`。

```bash
python3 mcpos_cli.py init-episode <channel_id> <episode_id>
```

示例：
```bash
python3 mcpos_cli.py init-episode kat kat_20241201
```

### run-episode
处理单期节目的完整流程：INIT → TEXT_BASE → COVER → MIX → TEXT_SRT → RENDER。

```bash
python3 mcpos_cli.py run-episode <channel_id> <episode_id>
```

示例：
```bash
python3 mcpos_cli.py run-episode kat kat_20241201
```

### run-day
处理某一天的所有节目。

```bash
python3 mcpos_cli.py run-day <channel_id> <date>
```

### run-month
处理某个月的所有节目。

```bash
python3 mcpos_cli.py run-month <channel_id> <year> <month>
```

### check-status
检查节目完成状态。

```bash
python3 mcpos_cli.py check-status [--channel-id] [--year] [--month]
```

## 查看帮助

```bash
python3 mcpos_cli.py --help
python3 mcpos_cli.py init-episode --help
```

## 故障排除

### 问题：`ModuleNotFoundError: No module named 'typer'`

**解决方案**：
```bash
# 确保虚拟环境已激活
source .venv311/bin/activate

# 安装依赖（包含 OpenAI client）
pip install -r requirements.txt
```

### 问题：`mcpos: command not found`

**解决方案**：
- 使用临时脚本：`python3 mcpos_cli.py <command>`
- 或者安装项目：`pip install -e .`（安装后可能需要重新加载 shell）

### 问题：找不到虚拟环境

**解决方案**：
```bash
# 检查虚拟环境是否存在
ls -la .venv311/bin/activate

# 如果不存在，创建新的虚拟环境
python3 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt

### 依赖说明

- `openai` Python package 用于 TEXT_BASE（AI 生成标题/描述/标签）
- 需要设置 `OPENAI_API_KEY` 或写入 `config/openai_api_key.txt`
```
