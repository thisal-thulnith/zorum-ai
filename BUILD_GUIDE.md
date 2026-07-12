# Zorum AI — A-to-Z Build Instructions (Do It Yourself Guide)

Follow this top to bottom. Every step tells you: **what to do → the exact command or file → how to verify it worked.**
Companion document: `ZORUM_TECHNICAL_PLAN.md` (the architecture — read Section 4 before Phase 3 here).

---

## STEP 0 — Prerequisites (30 min)

You already have: `uv`, Node 24, npm 11, Docker 29, git. Do these now:

```bash
# 1. Install Python 3.12 (your pyenv default is 3.11)
uv python install 3.12

# 2. Accounts to create (all free tiers to start):
#    - console.anthropic.com  → create API key           (agent brain)
#    - dash.cloudflare.com    → R2 bucket "zorum-docs"   (invoice PDF storage) — needed from Phase 2
#    - railway.app            → sign up                  (deploy) — needed in Phase 6
#    - resend.com             → API key                  (emails) — needed in Phase 6
#    - voyageai.com           → API key                  (embeddings) — needed in Phase 5

# 3. Make the project a real git repo (right now it's inside your home-dir repo)
cd /Users/thisalthulnith/zorum_ai
git init
```

✅ **Verify:** `uv python list | grep 3.12` shows an installed 3.12; `git status` inside zorum_ai shows its own empty repo.

---

# PHASE 0 — Skeleton & Rails (Week 1)

### 0.1 Create the folder structure

```bash
cd /Users/thisalthulnith/zorum_ai
mkdir -p backend/app/{core/{tenancy,auth,modules,events,audit,approvals,documents,agents},modules/finance,workers} \
         backend/tests backend/evals/golden_invoices \
         frontend packages/contracts .github/workflows
```

### 0.2 Bootstrap the backend

```bash
cd backend
uv init --python 3.12 --name zorum-backend
uv add fastapi "uvicorn[standard]" "sqlalchemy[asyncio]" alembic asyncpg \
       pydantic pydantic-settings procrastinate anthropic pgvector \
       pwdlib[argon2] pyjwt httpx python-multipart boto3
uv add --dev pytest pytest-asyncio ruff mypy respx httpx import-linter
```

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Zorum AI")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
```

✅ **Verify:** `uv run uvicorn app.main:app --reload` → open http://localhost:8000/healthz → `{"status":"ok"}`. Stop it (Ctrl-C).

### 0.3 Bootstrap the frontend

```bash
cd /Users/thisalthulnith/zorum_ai
npx create-next-app@latest frontend --typescript --tailwind --app --src-dir --eslint --no-import-alias
cd frontend
npx shadcn@latest init
npm install @tanstack/react-query zod
```

✅ **Verify:** `npm run dev` → http://localhost:3000 loads. Stop it.

### 0.4 Docker Compose for local dev

Create `/Users/thisalthulnith/zorum_ai/docker-compose.yml`:

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: zorum
      POSTGRES_PASSWORD: zorum
      POSTGRES_DB: zorum
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U zorum"]
      interval: 3s
      retries: 10
  mailpit:                       # catches all dev emails — open http://localhost:8025
    image: axllent/mailpit
    ports: ["8025:8025", "1025:1025"]
volumes:
  pgdata:
```

(API/worker/web run natively with hot-reload during dev; you'll add their Dockerfiles in Phase 6 for deploy.)

### 0.5 Makefile — your daily commands

Create `/Users/thisalthulnith/zorum_ai/Makefile`:

```makefile
dev:            ## start db+mailpit, api, worker, web (run each in its own terminal, or use this with tmux)
	docker compose up -d db mailpit
	cd backend && uv run uvicorn app.main:app --reload &
	cd backend && uv run procrastinate --app=app.workers.tasks.pq_app worker &
	cd frontend && npm run dev

migrate:
	cd backend && uv run alembic upgrade head

test:
	cd backend && uv run pytest -q

eval:
	cd backend && uv run python evals/run_extraction_eval.py

seed:
	cd backend && uv run python -m app.seed
```

### 0.6 Environment file

Create `backend/.env` (and add `.env` to `.gitignore`):

```
DATABASE_URL=postgresql+asyncpg://zorum:zorum@localhost:5432/zorum
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=<run: openssl rand -hex 32>
```

Create `backend/app/config.py` with a `pydantic-settings` `Settings` class that reads those. **Instruction:** every secret ever used goes in `.env` + `Settings`, never hardcoded.

### 0.7 CI

Create `.github/workflows/ci.yml`: jobs for `ruff check`, `mypy app`, `pytest` (with a `pgvector/pgvector:pg16` service container), and `cd frontend && npx tsc --noEmit && npm run build`. Push to GitHub.

### 0.8 CLAUDE.md

Create `/Users/thisalthulnith/zorum_ai/CLAUDE.md` recording: the stack, "core/ never imports modules/", "all money math in code never LLM", "every table has tenant_id + RLS", file layout. This keeps every Claude Code session you use consistent.

✅ **PHASE 0 DONE when:** `docker compose up -d` + backend + frontend all run together; CI is green on GitHub with one trivial test.

---

# PHASE 1 — Tenancy, Auth, RBAC, Module Registry (Weeks 2–3)

**Order matters here. Build in exactly this sequence.**

### 1.1 Database session + Alembic

1. `cd backend && uv run alembic init alembic` — configure `alembic/env.py` for async SQLAlchemy and your `DATABASE_URL`.
2. Create `app/db.py`: async engine, `async_session_factory`, and a `Base` declarative class.

### 1.2 First migration — kernel tables

Create SQLAlchemy models then `uv run alembic revision --autogenerate -m "kernel"` for:
`tenants`, `users`, `roles`, `user_roles`, `refresh_tokens`, `invitations`, `modules`, `tenant_modules`, `audit_log`
(column lists are in ZORUM_TECHNICAL_PLAN.md §5 — copy them exactly).

### 1.3 Row-Level Security — the tenant-isolation guarantee ⚠️ most important step in the whole build

Write this as **hand-written SQL in a migration** (autogenerate can't do it):

```sql
-- 1. A dedicated NON-superuser role the app connects as
CREATE ROLE zorum_app LOGIN PASSWORD 'app_pw_from_env';
GRANT USAGE ON SCHEMA public TO zorum_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO zorum_app;
REVOKE UPDATE, DELETE ON audit_log FROM zorum_app;   -- audit log is append-only

-- 2. For EVERY tenant table (repeat this block):
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON users
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

Then in `app/db.py` add the request dependency:

```python
async def tenant_session(current_user=Depends(get_current_user)):
    async with async_session_factory() as session:
        await session.execute(
            text("SET LOCAL app.tenant_id = :tid"), {"tid": str(current_user.tenant_id)}
        )
        yield session
```

**Rule from now on:** every API route that touches tenant data uses `Depends(tenant_session)`. The app's `DATABASE_URL` must use the `zorum_app` role, NOT the postgres superuser (superusers bypass RLS).

### 1.4 Auth

Build in `app/core/auth/`, in this order:
1. `passwords.py` — argon2 hash/verify via `pwdlib`.
2. `jwt.py` — issue access token (15 min, claims: `sub`, `tenant_id`, `roles`) + refresh token (random 256-bit, store only its sha256 in `refresh_tokens`, rotate on every use).
3. `router.py` — `POST /auth/signup` (creates tenant + owner user in one transaction), `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`.
4. `rbac.py` — `require_permission("finance.approve")`-style dependency; seed roles: owner, admin, finance_manager, approver, viewer.
5. `invitations.py` — `POST /invitations` emails a tokenized link (to Mailpit in dev), `POST /invitations/accept` creates the user with the invited role.

### 1.5 Module registry

In `app/core/modules/registry.py`: the `ModuleManifest` Pydantic model (plan §4.1), a startup hook that upserts every manifest into `modules`, and endpoints `GET /api/v1/modules`, `POST /api/v1/modules/{key}/install`, `POST /{key}/uninstall` (sets `enabled=false`). Create the finance manifest stub in `app/modules/finance/manifest.py` with `default_autonomy=1`.

### 1.6 Audit writer

`app/core/audit/`: `write_audit(session, actor, action, entity, before, after, ...)` + `GET /api/v1/audit` (filterable). Call it from the install endpoint as its first consumer.

### 1.7 Frontend auth + settings

Pages: `/login`, `/signup`, `/invite/[token]`; a protected `(app)/` layout that redirects when no session; `settings/modules` page listing modules with an install toggle and an autonomy slider (locked to L1 for now).

### 1.8 ✋ THE ISOLATION TEST — do not skip

Write `backend/tests/test_tenant_isolation.py`:
1. Seed tenant A and tenant B, each with users.
2. As tenant A, call every endpoint that exists — assert zero tenant-B rows ever appear.
3. **The adversarial part:** open a raw session as `zorum_app`, `SET LOCAL app.tenant_id = <A>`, then run `SELECT * FROM users` with NO where-clause — assert only A's rows return. Then attempt an `UPDATE` on a B row — assert 0 rows affected.

✅ **PHASE 1 DONE when:** signup→login→invite→login-as-invitee all work through the UI; isolation test passes; audit rows appear for module install.

---

# PHASE 2 — Events, Workers, Documents (Weeks 4–5)

### 2.1 Procrastinate worker

`app/workers/tasks.py`: create the Procrastinate app (`pq_app`) pointed at the same Postgres. First task: `@pq_app.task async def ping(): ...`. Run `uv run procrastinate --app=app.workers.tasks.pq_app schema --apply` once to install its tables.

### 2.2 Transactional outbox

1. Migration: `events` + `event_deliveries` tables (plan §5).
2. `app/core/events/outbox.py`:

```python
async def emit_event(session, tenant_id, name: str, payload: dict, actor: dict):
    event = Event(tenant_id=tenant_id, name=name, payload=payload, actor=actor)
    session.add(event)
    await session.flush()
    await dispatch_event.defer_async(event_id=str(event.id))  # same tx → atomic
```

3. `dispatcher.py`: `dispatch_event` task reads subscribers from the module registry, inserts an `event_deliveries` row per subscriber (unique on event_id+subscriber = idempotency), and defers `handle_event(subscriber, event_id)` each with retry/backoff.

### 2.3 Document storage (Cloudflare R2)

1. Create the R2 bucket + API token; add `R2_ENDPOINT/R2_ACCESS_KEY/R2_SECRET/R2_BUCKET` to `.env`.
2. `app/core/documents/storage.py`: boto3 S3 client → `put_object`, `presigned_get_url`. Keys namespaced `tenant/{tenant_id}/documents/{doc_id}.pdf`.
3. `POST /api/v1/documents` — accepts upload, computes sha256, rejects duplicates (unique constraint), stores to R2, creates `documents` row, **emits `finance.document.uploaded`**.
4. Frontend: drag-and-drop upload zone on `finance/invoices`.

### 2.4 LLM usage metering table

Migration for `llm_usage` (plan §5) — empty for now, Phase 3 fills it.

✅ **PHASE 2 DONE when:** uploading a PDF in the UI creates the R2 object + document row + event, and a stub worker handler logs it. **Crash test:** kill the worker mid-job, restart, confirm the job completes exactly once (check `event_deliveries`).

---

# PHASE 3 — Invoice Extraction + Review UI + Evals (Weeks 6–8) ← THE WEDGE

### 3.1 Finance tables

Migration: `vendors`, `invoices`, `invoice_line_items` (plan §5) + RLS blocks for each.

### 3.2 Extraction schema

`app/modules/finance/schemas.py`:

```python
class ExtractedField(BaseModel):
    value: str | None
    confidence: float          # 0..1
    source_page: int

class LineItem(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    confidence: float

class InvoiceExtraction(BaseModel):
    vendor_name_raw: ExtractedField
    invoice_number: ExtractedField
    issue_date: ExtractedField
    due_date: ExtractedField
    currency: ExtractedField
    subtotal: ExtractedField
    tax_amount: ExtractedField
    total_amount: ExtractedField
    line_items: list[LineItem]
    notes: str | None
```

### 3.3 The Anthropic wrapper

`app/core/agents/llm.py` — ONE place that calls Claude. Responsibilities: client creation; system prompt + tools marked with `cache_control: {"type": "ephemeral"}` (keep that prefix byte-stable and >4096 tokens); retry on 429/5xx with backoff; on every response write a `llm_usage` row (tokens incl. `cache_read_input_tokens`, computed cost).

### 3.4 Extraction task

`app/modules/finance/ingestion.py`, worker task `extract_invoice(document_id)`:
1. Fetch PDF bytes from R2, base64-encode.
2. Call Claude with a `document` content block (`{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": ...}}`) placed BEFORE the instruction text, using `client.messages.parse(..., output_format=InvoiceExtraction)` for validated structured output. Include tenant currency default + the vendor's `extraction_hints` in the prompt.
3. **Validation layer (plain Python — never the model):** line items sum to subtotal ±0.01; subtotal+tax == total; issue_date ≤ due_date; date not far-future; currency in whitelist; duplicate check on (vendor, invoice_number) and fuzzy (amount+date). Failures → recorded on the extraction + force overall confidence low.
4. Auto-create/normalize vendor (uppercase, strip punctuation for `normalized_name`).
5. Create invoice with `status=extracted_pending_review`, full raw extraction in `extraction jsonb`; emit `finance.invoice.extracted`.

### 3.5 Review UI — the heart of the L1 product

`frontend/src/app/(app)/finance/invoices/[id]/page.tsx` — split view:
- LEFT: the PDF (`react-pdf`, loaded via presigned URL).
- RIGHT: every extracted field as an editable input with a confidence badge; fields <0.85 highlighted amber; line-item table; validation errors banner; **Approve** and **Save corrections** buttons.
- `POST /api/v1/invoices/{id}/review` saves corrections. **Every corrected field also:** (a) appends to `evals/golden_invoices/` as a labeled example, (b) writes a `vendor_correction` row you'll wire into memories in Phase 5.

### 3.6 Eval harness

1. Collect **50 real invoice PDFs** (your own, design partners', public samples — mix quality levels). For each, hand-write the correct JSON. This is boring and non-negotiable.
2. `evals/run_extraction_eval.py`: submit all 50 through the exact production prompt via Anthropic's **Batch API**; score per field (Decimal-exact for money/dates, fuzzy-normalized for vendor name, alignment F1 for line items); print a table + write `report.json`.
3. `evals/thresholds.yml`: `total_amount_exact: 0.98`, `invoice_number_exact: 0.95`, `line_item_f1: 0.90`. CI job fails if below. Iterate on the prompt until you pass.

✅ **PHASE 3 DONE when:** upload → extracted invoice on the review screen in <2 min; evals ≥ thresholds; `llm_usage` shows cost <$0.15/invoice (check cache_read is nonzero from the second call onward).

---

# PHASE 4 — POs, Bank Import, Matching, Approvals Inbox (Weeks 9–10)

### 4.1 Migrations
`purchase_orders`, `po_line_items`, `bank_accounts`, `bank_transactions`, `matches`, `proposed_actions` (+RLS each).

### 4.2 CSV importers
`POST /api/v1/finance/purchase-orders/import` and `/bank-transactions/import`: upload CSV → column-mapping UI step (user maps their headers to your fields) → rows inserted with hash dedupe (`sha256(account|date|amount|description)`).

### 4.3 Deterministic match scorer — plain Python, no LLM
`app/modules/finance/matching.py`:
- **invoice↔PO:** same vendor (+0.4), total within 2% (+0.3), line-description overlap via token match (+0.2), date proximity (+0.1). Score ≥0.85 → auto-suggest; 0.5–0.85 → send to agent for adjudication; <0.5 → no match.
- **invoice↔bank:** exact amount + date within terms window + fuzzy counterparty name.

### 4.4 Agent adjudication (first real agent task)
Worker task `match_invoice_to_po(invoice_id)`: run scorer; for ambiguous candidates only, call Claude with the invoice + candidate POs + vendor history, tools `propose_invoice_po_match` / `notify_user`. All proposals land in `proposed_actions` (status=proposed) — nothing auto-confirms at L1.

### 4.5 Approvals inbox
- API: `GET /api/v1/approvals?status=pending`, `GET /{id}`, `POST /{id}/approve`, `POST /{id}/reject {reason}`. Approve → RBAC check (approver+) → worker `execute_approved_action(id)` runs the stored tool handler → audit row.
- UI: `(app)/approvals` — list with badge count, each item shows payload diff + agent rationale + link to source; one-click approve/reject. Plus `(app)/finance/reconciliation` for bank matching.

### 4.6 Seed script
`app/seed.py`: demo tenant with 20 POs, 60 invoices, 200 bank transactions (make ~80% cleanly matchable, ~15% ambiguous, ~5% unmatchable).

✅ **PHASE 4 DONE when:** on the seeded data ≥80% of clean matches are suggested correctly with ZERO auto-confirmed; approve/reject round-trips write audit rows; a Playwright spec covers upload→review→match→approve.

---

# PHASE 5 — Agent Runtime, Forecast, Anomalies, L2 (Weeks 11–12)

### 5.1 Generalize the agent loop
Migrations: `agent_runs`, `agent_steps`, `agent_memories` (vector(1024)).
`app/core/agents/loop.py` — `run_agent(agent_spec, task)`: builds messages, calls Claude in a loop, on every `tool_use` → policy engine → handler, persists each step, stops on `end_turn` / `max_iterations` / token budget. **Refactor Phase 3's extraction and Phase 4's adjudication onto this loop** — they become task handlers, not bespoke code.

### 5.2 Policy engine — the chokepoint
`app/core/agents/policy.py` exactly as in plan §4.3: `evaluate(action, cfg) → EXECUTE | EXECUTE_AND_NOTIFY | REQUIRE_APPROVAL | SUGGEST_ONLY | DENY`, plus guardrails (money caps from `tenant_modules.settings`, per-level denylist, `paused` kill switch, `shadow_mode`). **Write the unit-test matrix first** — one test per (level × risk) cell — then implement until green.

### 5.3 Pause/resume for L2
Tool dispatcher on REQUIRE_APPROVAL: save run `status=awaiting_approval` + pending proposed_action, stop the loop. On approve: worker executes the tool, appends a synthetic tool_result ("approved and executed"), reloads message history, resumes the loop. Enable L2 on the settings slider.

### 5.4 Memory
`app/core/agents/memory.py`: embed with Voyage (`voyage-3.5`, 1024 dims) → insert into `agent_memories`; `recall_memories(query, entity_ref, k)` = cosine search scoped to tenant+module. Wire Phase 3's saved corrections in, and inject top-k into extraction/adjudication prompts.

### 5.5 Cash-flow forecast
Nightly Procrastinate periodic task: deterministic 13-week series from invoice due dates + payment terms + historical payment lag (code), then one agent call to write the narrative + assumptions + risks. Store in `cashflow_forecasts`; chart it at `finance/cashflow` (recharts).

### 5.6 Anomaly detection
`anomalies.py` rules (code): duplicate suspicion, price >2× vendor's 12-month average, new vendor + large amount, round-amount patterns, terms violations. Agent triages candidates → `flag_anomaly` with explanation → surfaces in dashboard + notifications.

### 5.7 Agent activity UI
`(app)/agents/activity`: timeline of `agent_runs` (status, trigger, cost), expandable to `agent_steps` — your governance/audit window.

✅ **PHASE 5 DONE when:** an L2 run visibly pauses → appears in inbox → resumes on approve and completes; injected test anomalies (duplicate, 3× price jump) get flagged with sane explanations; policy matrix tests all green.

---

# PHASE 6 — Onboarding, Shadow Mode, Deploy, Beta (Weeks 13–14)

### 6.1 Onboarding wizard
`frontend/src/app/onboarding/` — 6 steps reusing what you built: industry → module toggle → import data (CSV/PDF uploaders) → autonomy slider → invite team → go live. New signups route here.

### 6.2 Shadow mode
`tenants.shadow_mode=true` by default: policy engine treats EVERYTHING as SUGGEST_ONLY regardless of level; persistent banner "Shadow mode — agents are suggesting only". Owner can graduate from settings.

### 6.3 Deploy to Railway
1. Write `backend/Dockerfile` (uv-based) and `frontend/Dockerfile` (multi-stage next build).
2. Railway project with 4 services from your GitHub repo: **api** (uvicorn), **worker** (procrastinate worker), **web** (next start), **Postgres** (enable pgvector). Add a cron service/schedule for nightly tasks.
3. Set all env vars (DATABASE_URL with the `zorum_app` role, ANTHROPIC_API_KEY, JWT_SECRET, R2_*, RESEND_API_KEY). Run migrations as a release step.
4. Swap Mailpit → Resend for production email. Add Sentry (backend + frontend). Point a domain (e.g. app.zorum.ai).

### 6.4 Cost guardrails
Per-tenant monthly token budget in `tenant_modules.settings`; a daily job sums `llm_usage` and alerts you (and soft-stops agents) past budget.

### 6.5 Beta
Seed the demo tenant in prod. Recruit 3–5 businesses (design partners). Watch their first sessions. **Success metric: signup → first reviewed invoice < 30 minutes, unassisted.**

✅ **PHASE 6 DONE = BETA LIVE.**

---

## Golden Rules (pin these)

1. **RLS first, always** — new table = tenant_id + RLS policy in the same migration, no exceptions.
2. **Money math in code, never in the model.** The agent perceives, adjudicates, explains.
3. **Every agent write goes through `policy.evaluate()`.** No side doors.
4. **Every human correction becomes an eval example.** Your golden set grows itself.
5. **No non-finance module code before beta.** The registry seam is proven by discipline, not by module #2.
6. **Each phase's ✅ check is a gate.** Don't start the next phase until it passes.

## When you get stuck
Work phase by phase with Claude Code: give it `CLAUDE.md` + the relevant section of `ZORUM_TECHNICAL_PLAN.md` and ask for one step at a time (e.g. "implement step 1.3 RLS migration"). Verify each ✅ checkpoint yourself before moving on.
