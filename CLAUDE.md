# Zorum AI — Conventions

Agentic all-in-one business platform. MVP = Finance module (invoice extraction, matching,
reconciliation, forecasting, anomalies) in L1 suggest-only autonomy.

Plans: `ZORUM_TECHNICAL_PLAN.md` (architecture + schema), `BUILD_GUIDE.md` (step-by-step).

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, Procrastinate,
  Postgres 16 + pgvector. Package manager: `uv` (run things with `uv run ...`).
- Frontend: Next.js App Router + TypeScript + Tailwind v4 + shadcn/ui + TanStack Query + zod.
- LLM: Anthropic Claude via the single wrapper `backend/app/core/agents/llm.py` (once it exists).
- Dev: `docker compose up -d` for db+mailpit; `make api` / `make web` / `make worker`.

## Layout
- `backend/app/core/` = platform kernel (tenancy, auth, modules registry, events, audit,
  approvals, documents, agents runtime).
- `backend/app/modules/<name>/` = business modules (finance only, until beta).

## HARD RULES
1. `core/` never imports from `modules/`. Modules never import each other — events only.
2. Every tenant table: `tenant_id UUID NOT NULL` + RLS policy in the SAME migration.
   App connects as non-superuser role `zorum_app`; requests use `SET LOCAL app.tenant_id`.
3. Money math is computed in Python code, NEVER by the LLM. The agent perceives,
   adjudicates, and explains — it does not calculate totals.
4. Every agent write action goes through `core/agents/policy.evaluate()`. No side doors.
5. All secrets via `backend/.env` + `app/config.py` Settings. Never hardcoded, never committed.
6. `audit_log` is append-only (no UPDATE/DELETE grants).
7. No non-finance module code before beta.
