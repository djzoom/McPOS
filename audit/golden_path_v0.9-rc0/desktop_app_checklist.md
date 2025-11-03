# 桌面应用验证清单

## 前提条件
- [ ] 后端已稳定运行（端口8010）
- [ ] 前端已静态导出（kat_rec_web/frontend/out目录存在）
- [ ] Tauri CLI已安装（`cd desktop/tauri && pnpm install`）

## 验证步骤

### 1. 安装Tauri依赖（如果未安装）
```bash
cd desktop/tauri
pnpm install
```

### 2. 构建前端静态导出
```bash
cd kat_rec_web/frontend
NEXT_OUTPUT_MODE=export pnpm build
```

### 3. 启动桌面应用
```bash
make app:dev
```

### 4. 验证点
- [ ] 应用窗口自动打开（标题："Kat Rec Control Center"）
- [ ] 控制台日志显示后端进程启动
- [ ] 等待 /health 端点就绪（≤20秒）
- [ ] 应用自动导航到 /t2r 页面
- [ ] 在浏览器控制台（DevTools）验证：
  - `window.__API_BASE__` 存在且指向正确端口
  - `window.__WS_BASE__` 存在且指向正确端口
- [ ] GUI功能正常（可以执行scan等操作）

### 5. 验证后端自动启动
检查日志中的：
- Python进程启动（uvicorn）
- 端口选择（8000-8010范围）
- /health 端点就绪

### 6. 验证优雅关闭
关闭应用窗口时：
- [ ] 后端进程被正确终止
- [ ] 没有遗留的uvicorn进程

