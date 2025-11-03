# Web 控制台使用指南

## 概述

Kat Records Studio 现在支持通过命令行工具启动 Web 控制台，提供可视化的管理和监控界面。

## 快速开始

### 启动简单 Dashboard

```bash
# 默认启动（端口 8080，自动打开浏览器）
python scripts/kat_cli.py web

# 自定义端口
python scripts/kat_cli.py web --port 9000

# 不自动打开浏览器
python scripts/kat_cli.py web --no-open

# 开发模式（自动重载）
python scripts/kat_cli.py web --reload
```

### 启动完整版 Web 应用

完整版 Web 应用需要 Docker，提供更丰富的功能（前端、后端、Redis等）：

```bash
# 启动完整版（前台运行）
python scripts/kat_cli.py web --full

# 后台运行
python scripts/kat_cli.py web --full --detach
```

## 命令选项

### `web` 命令参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--host` | 服务器主机地址 | `127.0.0.1` |
| `--port` | 服务器端口 | `8080` |
| `--open` | 自动打开浏览器 | `true` |
| `--no-open` | 不自动打开浏览器 | - |
| `--reload` | 启用自动重载（开发模式） | `false` |
| `--full` | 启动完整版 kat_rec_web（需要Docker） | `false` |
| `--docker` | 使用Docker模式 | `false` |
| `--detach`, `-d` | 后台运行（仅Docker模式） | `false` |

## 两种模式

### 1. 简单 Dashboard 模式（默认）

**特点**：
- 轻量级，无需 Docker
- 快速启动
- 提供基本的监控和管理功能
- 适用于单机部署

**访问地址**：
- Dashboard: http://127.0.0.1:8080
- API: http://127.0.0.1:8080/api/

**功能**：
- 查看排播表状态
- 恢复失败的期数
- 查看指标

### 2. 完整版 Web 应用模式

**特点**：
- 基于 Docker Compose
- 包含前端（Next.js）和后端（FastAPI）
- 支持 Redis 缓存和任务队列
- 适用于多频道管理（可扩展至100个频道）

**访问地址**：
- 前端 Dashboard: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

**功能**：
- 完整的频道管理
- 歌库和图片库管理
- 上传状态监控
- 任务队列管理

## 配置

Web 控制台的配置可以在 `config/config.yaml` 中设置：

```yaml
web:
  host: "127.0.0.1"
  port: 8080
  auto_open_browser: true
  access_token: null  # 可选：设置访问令牌
  allowed_hosts:
    - "127.0.0.1"
    - "::1"
    - "localhost"
```

## 停止服务器

### 简单 Dashboard

按 `Ctrl+C` 停止服务器。

### 完整版（Docker）

如果使用 `--detach` 后台运行：

```bash
cd kat_rec_web
docker-compose down
```

或者使用 CLI：

```bash
# 如果添加了停止命令（未来版本）
python scripts/kat_cli.py web --stop
```

## 故障排除

### 端口被占用

如果默认端口被占用，使用 `--port` 指定其他端口：

```bash
python scripts/kat_cli.py web --port 9090
```

### FastAPI 未安装

如果遇到 "FastAPI未安装" 错误：

```bash
pip install fastapi uvicorn
```

### Docker 未安装

如果使用 `--full` 模式但 Docker 未安装：

```bash
# macOS
brew install docker docker-compose

# Linux
sudo apt-get install docker.io docker-compose

# 或使用 Docker Desktop
```

### 依赖问题

确保所有依赖已安装：

```bash
pip install -r requirements.txt
```

## 开发模式

启用自动重载以便开发：

```bash
python scripts/kat_cli.py web --reload
```

这样修改代码后服务器会自动重启。

## 示例

```bash
# 基本使用
kat web

# 自定义配置
kat web --host 0.0.0.0 --port 9000

# 开发模式
kat web --reload --no-open

# 启动完整版
kat web --full

# 完整版后台运行
kat web --full --detach
```

## 下一步

- 查看 [架构文档](ARCHITECTURE.md) 了解系统设计
- 查看 [API 文档](../kat_rec_web/README.md) 了解完整版 API
- 查看 [开发指南](DEVELOPMENT.md) 了解如何扩展 Web 控制台

