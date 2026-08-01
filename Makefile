# 智能问答平台

.PHONY: help lint test security format clean

# 默认显示帮助
help:
	@echo "智能问答平台 - Makefile"
	@echo ""
	@echo "后端命令:"
	@echo "  make lint-backend      后端代码检查 (black + isort + ruff + mypy)"
	@echo "  make format-backend    后端代码格式化 (black + isort)"
	@echo "  make test-backend      后端测试 (pytest)"
	@echo "  make security-backend  后端安全扫描 (bandit + detect-secrets)"
	@echo ""
	@echo "前端命令:"
	@echo "  make lint-frontend     前端代码检查 (eslint + prettier)"
	@echo "  make format-frontend   前端代码格式化 (prettier)"
	@echo "  make test-frontend     前端测试 (vitest)"
	@echo ""
	@echo "综合命令:"
	@echo "  make lint              全部代码检查"
	@echo "  make format            全部代码格式化"
	@echo "  make test              全部测试"
	@echo "  make security          全部安全扫描"
	@echo "  make check             完整门禁 (提交前必跑，与CI一致)"
	@echo "  make setup-dev         安装开发工具 (首次使用)"
	@echo "  make clean             清理缓存和构建产物"
	@echo ""
	@echo "开发命令:"
	@echo "  make dev-backend       启动后端开发服务器"
	@echo "  make dev-frontend      启动前端开发服务器"
	@echo "  make dev               一键启动全部 (docker-compose)"

# ============================================
# 后端
# ============================================
# ============================================
# 后端（在容器 rag-qa-backend 内执行：Python 3.11 + 全依赖）
# 首次使用先 `make setup-dev` 在容器内安装 lint/安全工具
# ============================================
lint-backend:
	@echo "==> 后端代码检查 (ruff + black + isort + mypy)..."
	docker exec rag-qa-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && ruff check app tests && black --check app tests && isort --check-only app tests && mypy --strict app'

format-backend:
	@echo "==> 格式化后端代码 (black + isort)..."
	docker exec rag-qa-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && black app tests && isort app tests'

test-backend:
	@echo "==> 运行后端测试 (单元 + 集成)..."
	docker exec rag-qa-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && pytest -v --cov=app --cov-report=term-missing'

security-backend:
	@echo "==> 后端安全扫描 (bandit + detect-secrets)..."
	docker exec rag-qa-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && bandit -ll -c .bandit -r app/'
	@echo "==> 密钥泄露检查 (detect-secrets, 基于基线)..."
	detect-secrets-hook --baseline .secrets.baseline

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ============================================
# 前端
# ============================================
lint-frontend:
	@echo "==> 检查前端代码..."
	cd frontend && npm run lint
	@echo "==> 前端类型检查..."
	cd frontend && npm run type-check

format-frontend:
	@echo "==> 格式化前端代码..."
	cd frontend && npm run format

test-frontend:
	@echo "==> 运行前端单元测试..."
	cd frontend && npm run test:unit -- --run

lint-frontend-check:
	@echo "==> 检查前端代码格式..."
	cd frontend && npx prettier --check "src/**/*"

dev-frontend:
	cd frontend && npm run dev

# ============================================
# 综合
# ============================================
lint: lint-backend lint-frontend

format: format-backend format-frontend

test: test-backend test-frontend

security: security-backend

# 完整质量门禁（提交前必跑，与 CI 一致）：后端 lint+类型+测试+安全 + 前端 类型+lint+单测
check:
	@echo "==> [1/2] 后端门禁（容器内）：ruff + black + isort + mypy + bandit + pytest..."
	docker exec rag-qa-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && ruff check app tests && black --check app tests && isort --check-only app tests && mypy --strict app && bandit -ll -c .bandit -r app/ && pytest -v --cov=app --cov-report=term-missing'
	@echo "==> [2/2] 前端门禁：vue-tsc + eslint + vitest..."
	cd frontend && npm run type-check && npm run lint && npm run test:unit -- --run
	@echo "==> 全部门禁通过"

# 安装开发工具（首次使用或容器重建后执行）
setup-dev:
	@echo "==> 容器内安装 lint/安全工具..."
	docker exec rag-qa-backend pip install -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r /app/requirements-dev.txt
	@echo "==> 本机启用 pre-commit 钩子（需本机已装 pre-commit/ruff/black/isort/bandit/detect-secrets）..."
	pre-commit install
	@echo "==> 完成。commit 时将自动触发质量门禁。"

dev:
	cd deployment && docker-compose up -d

dev-down:
	cd deployment && docker-compose down

# ============================================
# 清理
# ============================================
clean:
	@echo "==> 清理缓存..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "==> 清理完成"
