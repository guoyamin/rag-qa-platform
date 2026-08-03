# 智能问答平台

.PHONY: help lint test security security-check format clean setup-dev check gen-client

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
	@echo "  make security-check    依赖漏洞预检 (advisory，不阻断)"
	@echo "  make gen-client        重新生成 OpenAPI 契约 + 前端 TS 类型"
	@echo "  make setup-dev         安装开发工具 (首次使用)"
	@echo "  make clean             清理缓存和构建产物"
	@echo ""
	@echo "开发命令:"
	@echo "  make dev-backend       启动后端开发服务器"
	@echo "  make dev-frontend      启动前端开发服务器"
	@echo "  make dev               一键启动全部开发栈（docker-compose.dev.yml）"

# ============================================
# 后端
# ============================================
# ============================================
# 后端（在容器 rag_qa_platform-backend 内执行：Python 3.11 + 全依赖）
# 首次使用先 `make setup-dev` 在容器内安装 lint/安全工具
# ============================================
lint-backend:
	@echo "==> 后端代码检查 (ruff + black + isort + mypy)..."
	docker exec rag_qa_platform-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && ruff check app tests && black --check app tests && isort --check-only app tests && mypy --strict app'

format-backend:
	@echo "==> 格式化后端代码 (black + isort)..."
	docker exec rag_qa_platform-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && black app tests && isort app tests'

test-backend:
	@echo "==> 运行后端测试 (单元 + 集成)..."
	docker exec rag_qa_platform-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && pytest -v --cov=app --cov-report=term-missing'

security-backend:
	@echo "==> 后端安全扫描 (bandit + detect-secrets)..."
	docker exec rag_qa_platform-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && bandit -ll -c .bandit -r app/'
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
	@echo "==> [1/2] 后端门禁（容器内）：ruff + black + isort + mypy + bandit + pytest + alembic check..."
	docker exec rag_qa_platform-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && ruff check app tests && black --check app tests && isort --check-only app tests && mypy --strict app && bandit -ll -c .bandit -r app/ && pytest -v --cov=app --cov-report=term-missing && export DATABASE_URL=sqlite+aiosqlite:///./_alembic_check.db && alembic upgrade head && alembic check && rm -f _alembic_check.db'
	@echo "==> [2/2] 前端门禁：vue-tsc + eslint + vitest..."
	cd frontend && npm run type-check && npm run lint && npm run test:unit -- --run
	@echo "==> 全部门禁通过"

# 安装开发工具（首次使用或容器重建后执行）
setup-dev:
	@echo "==> [1/4] 自检宿主机前置..."
	@command -v python >/dev/null 2>&1 || { echo "❌ 缺 Python（需 3.10+，推荐 3.11）。装好后重跑。"; exit 1; }
	@command -v pip >/dev/null 2>&1 || { echo "❌ 缺 pip。"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "❌ 缺 docker（容器跑 mypy/pytest 用）。"; exit 1; }
	@echo "==> [2/4] 宿主机装 pre-commit 工具链（pip --user，版本对齐 requirements-dev.txt）..."
	@pip install --user -r backend/requirements-dev.txt || { echo "⚠️ 宿主机 pip 安装失败（PEP 668？试 pipx，或加 --break-system-packages）。pre-commit 钩子需 ruff/black/isort/bandit/detect-secrets/pre-commit/pyyaml 在 PATH。"; }
	@echo "==> [3/4] 容器内装 lint/安全工具..."
	docker exec rag_qa_platform-backend pip install -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r /app/requirements-dev.txt
	@echo "==> [4/4] 装 git 钩子（pre-commit + commit-msg）+ 前端依赖..."
	pre-commit install
	pre-commit install --hook-type commit-msg
	cd frontend && npm ci
	@echo "==> 完成。commit 触发秒级门禁；commit-msg 校验 Conventional Commits。"

# 依赖漏洞 advisory 预检（不阻断 CI/门禁，主力靠 Dependabot）
security-check:
	@echo "==> [advisory，不阻断] 后端依赖漏洞（pip-audit）..."
	@docker exec rag_qa_platform-backend bash -lc 'export PATH=/home/appuser/.local/bin:$$PATH && cd /app && pip-audit -r requirements.txt' || true
	@echo "==> [advisory，不阻断] 前端依赖漏洞（npm audit）..."
	@cd frontend && npm audit || true
	@echo "==> 完成（advisory，有发现见上方输出；不阻断 CI/门禁）。"

# 重新生成 OpenAPI 契约 + 前端 TS 类型（后端改路由/schema 后跑；派生物须提交）
gen-client:
	@echo "==> 重新生成 OpenAPI 契约 + 前端 TS 类型..."
	@bash tools/generate-api-client.sh
	@echo "==> 完成。记得 git add docs/api-contracts/api-schema.json frontend/src/api/types.d.ts"

dev:
	cd deployment && docker-compose -f docker-compose.dev.yml up -d

dev-down:
	cd deployment && docker-compose -f docker-compose.dev.yml down

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
