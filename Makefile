.PHONY: dev db api worker web migrate test lint eval seed

db:            ## start postgres + mailpit in docker
	docker compose up -d db mailpit

api:           ## run the FastAPI server (hot reload)
	cd backend && uv run uvicorn app.main:app --reload

worker:        ## run the procrastinate background worker
	cd backend && uv run procrastinate --app=app.workers.tasks.pq_app worker

web:           ## run the Next.js frontend
	cd frontend && npm run dev

dev: db        ## start db, then print how to run the rest
	@echo "db + mailpit up. Now run in separate terminals:"
	@echo "  make api      (backend on :8000)"
	@echo "  make web      (frontend on :3000)"
	@echo "  make worker   (background jobs — from Phase 2)"

migrate:       ## apply database migrations
	cd backend && uv run alembic upgrade head

test:          ## run backend tests
	cd backend && uv run pytest -q

lint:          ## lint backend
	cd backend && uv run ruff check app

eval:          ## run the invoice-extraction eval harness (Phase 3+)
	cd backend && uv run python evals/run_extraction_eval.py

seed:          ## seed demo data (Phase 4+)
	cd backend && uv run python -m app.seed
