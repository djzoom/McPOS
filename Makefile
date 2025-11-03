.PHONY: help install test clean monitor dashboard metrics-api app:dev app:build app:verify

help:
	@echo "Kat Records Studio - 可用命令"
	@echo ""
	@echo "安装和配置:"
	@echo "  make install         安装依赖"
	@echo ""
	@echo "桌面应用:"
	@echo "  make app:dev          开发模式运行桌面应用"
	@echo "  make app:build        构建桌面应用"
	@echo "  make app:verify       验证桌面应用配置"
	@echo ""
	@echo "监控和仪表板:"
	@echo "  make monitor         启动CLI监控（持续模式）"
	@echo "  make dashboard       启动Web仪表板服务器"
	@echo "  make metrics-api     启动指标API服务器"
	@echo ""
	@echo "其他:"
	@echo "  make test            运行测试"
	@echo "  make clean           清理临时文件"

install:
	pip install -r requirements.txt

monitor:
	python scripts/local_picker/cli_monitor.py --watch

dashboard:
	python web/dashboard/dashboard_server.py

metrics-api:
	uvicorn src.api.metrics_api:app --reload --port 8000

app:dev:
	pnpm -C desktop/tauri tauri dev

app:build:
	cd kat_rec_web/frontend && NEXT_OUTPUT_MODE=export pnpm build && cd ../../ && pnpm -C desktop/tauri tauri build

app:verify:
	bash scripts/verify_app.sh

test:
	pytest tests/ -v

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
