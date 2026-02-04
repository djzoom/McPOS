# McPOS CLI 快速开始

## 问题：`mcpos: command not found`

这是因为 CLI 还没有安装到系统路径。有两种解决方案：

## 方法 1：使用临时脚本（推荐，无需安装）

```bash
# 1. 安装依赖（包含 OpenAI client，用于 TEXT_BASE）
pip install -r requirements.txt

# 2. 直接运行脚本
python3 mcpos_cli.py init-episode kat kat_2025test01
python3 mcpos_cli.py run-episode kat kat_2025test01
```

## 方法 2：安装 CLI 命令（永久方案）

```bash
# 1. 安装依赖（包含 OpenAI client，用于 TEXT_BASE）
pip install -r requirements.txt

# 2. 以开发模式安装项目（会注册 mcpos 命令）
pip install -e .

# 3. 现在可以直接使用 mcpos 命令
mcpos init-episode kat kat_2025test01
mcpos run-episode kat kat_2025test01
```

## 可用命令

- `init-episode <channel_id> <episode_id>` - 初始化单期节目（生成 playlist.csv 和 recipe.json）
- `run-episode <channel_id> <episode_id>` - 处理单期节目（完整流程：INIT → TEXT_BASE → COVER → MIX → TEXT_SRT → RENDER）
- `run-day <channel_id> <date>` - 处理某一天的所有节目
- `run-month <channel_id> <year> <month>` - 处理某个月的所有节目
- `check-status [--channel-id] [--year] [--month]` - 检查节目完成状态

## 示例

```bash
# 初始化一期节目
python3 mcpos_cli.py init-episode kat kat_20241201

# 运行完整流程
python3 mcpos_cli.py run-episode kat kat_20241201

# 查看帮助
python3 mcpos_cli.py --help
python3 mcpos_cli.py init-episode --help
```

## 依赖说明

- `openai` Python package 用于 TEXT_BASE（AI 生成标题/描述/标签）
- 需要设置 `OPENAI_API_KEY` 或写入 `config/openai_api_key.txt`
