.PHONY: install dev dev-backend dev-frontend test test-unit lint lint-backend lint-frontend docker clean

install:
	pip install -e ".[dev]"
	cd frontend && npm install

dev-backend:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	@echo "Run these in separate terminals:"
	@echo "  make dev-backend"
	@echo "  make dev-frontend"

test-unit:
	python -m pytest backend/tests/ --ignore=backend/tests/run_evals.py -v

test: test-unit
	@echo "---"
	@echo "Unit tests passed. For integration tests (requires running server + API key):"
	@echo "  python -m backend.tests.run_evals"

lint-backend:
	ruff check backend/

lint-frontend:
	cd frontend && npx eslint .
	cd frontend && npx tsc -b

lint: lint-backend lint-frontend

ci: lint test-unit
	cd frontend && npm run build

docker:
	docker compose up --build

clean:
	rm -rf data/frontdesk.db
	rm -rf frontend/dist
	rm -rf backend/static
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
