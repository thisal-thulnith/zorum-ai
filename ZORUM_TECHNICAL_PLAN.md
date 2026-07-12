# Zorum AI — Complete Technical Plan & Step-by-Step Build Guide

**MVP: Agentic Finance & Accounting Module · Solo founder + Claude Code · ~14 weeks to beta**

---

## 1. What We're Building

Zorum AI is an **agentic, plug-and-play, all-in-one business platform**: each business function (finance, HR, inventory, sales, support) is run by a dedicated AI agent that perceives data, reasons, and acts — humans supervise rather than operate. Modules install like apps, all sharing one unified data layer and event bus, governed by a 4-level autonomy model:

| Level | Behavior | Example |
|---|---|---|
| **L1 — Suggest only** | Agent recommends, human approves everything | Draft invoice record for review |
| **L2 — Approve-to-act** | Agent prepares action, one-click approval | Match ready to confirm |
| **L3 — Act-then-notify** | Agent executes, notifies afterward | Auto-flag anomaly |
| **L4 — Fully autonomous** | Agent executes, periodic audit only | Routine invoice matching |

**The MVP strategy (per the reference document's own warning against overbuilding):** launch ONE module — **Finance & Accounting** — fully agentic end-to-end, in L1 suggest-only mode, before expanding to the catalog. The platform kernel (module registry, event bus, agent runtime, policy engine, audit log) is built as a real seam from day one, so module #2 is purely additive.

Finance module capabilities at launch:
1. **Invoice ingestion & extraction** — upload PDF → Claude extracts structured data with per-field confidence
2. **Invoice ↔ PO matching** — deterministic scoring + agent adjudication of ambiguous cases
3. **Bank reconciliation** — CSV import → proposed invoice↔transaction matches
4. **Cash-flow forecasting** — nightly deterministic projection + agent narrative
5. **Anomaly detection** — duplicates, price jumps, unusual patterns, flagged with explanations

---

## 2. Locked Technical Decisions (with rationale)

| Decision | Choice | Why |
|---|---|---|
| Backend | **Python 3.12 / FastAPI**, SQLAlchemy 2 + Alembic, Pydantic v2 | Best ecosystem for agent-heavy logic and document processing; first-class Anthropic SDK; Pydantic for structured agent outputs |
| Frontend | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui** | New product app, separate from the `zorum-react` marketing site (which stays untouched) |
| Database | **PostgreSQL + pgvector** | One database for domain data, job queue, event outbox, AND agent memory — minimal infra |
| LLM | **Claude (`claude-opus-4-8`)**, structured outputs via `messages.parse()`, adaptive thinking, effort tuned per task | Financial extraction is where you don't cheap out on the model; cost is controlled by caching/batching/effort, not model downgrade |
| Embeddings | **Voyage AI `voyage-3.5`** → pgvector | Anthropic has no embeddings endpoint; Voyage is their recommended partner |
| Job queue / events | **Procrastinate** (Postgres-native queue) + transactional **outbox `events` table** | Zero extra infra (no Redis/Kafka/RabbitMQ); jobs enqueue in the SAME Postgres transaction as domain writes → exactly-once handoff for free. The outbox table is the stable seam if you ever outgrow it |
| Multi-tenancy | Single DB, `tenant_id` on every row, **Postgres RLS** as the hard guarantee | App connects as non-superuser role with `FORCE ROW LEVEL SECURITY`; each request runs `SET LOCAL app.tenant_id`. App-level filtering alone is one forgotten WHERE clause away from a breach in a financial product |
| Auth | **Self-rolled JWT** (15-min access + rotating refresh tokens hashed in DB), argon2id, email via Resend | ERP users are tenant-owned; Clerk/Auth0 org models fight your tenancy model and add per-MAU cost. SSO deferred to post-beta |
| Deploy | **Railway** (api, worker, cron, Postgres, web) + **Cloudflare R2** for documents | Git-push Dockerfile deploys, managed pgvector Postgres, private networking, no Kubernetes ops. R2 = S3 API with zero egress fees |
| Payments | Stripe — **deferred until after beta** | Validate first |
| NOT at MVP | Kafka, Kubernetes, Redis, microservices, second module, L3/L4 autonomy | Scope discipline — see risks |

---

## 3. Monorepo Layout — `/Users/thisalthulnith/zorum_ai`

```
zorum_ai/
├── docker-compose.yml          # postgres(pgvector), api, worker, web, mailpit (dev email)
├── Makefile                    # make dev / test / migrate / eval / seed
├── .github/workflows/ci.yml    # ruff, mypy, pytest, eval regression gate, tsc, playwright
├── CLAUDE.md                   # repo conventions for Claude Code sessions
│
├── backend/
│   ├── pyproject.toml          # uv-managed: fastapi, sqlalchemy2, alembic, procrastinate,
│   │                           #   anthropic, pgvector, pwdlib, pyjwt, httpx
│   ├── Dockerfile
│   ├── alembic/                # migrations (RLS policies live here as DDL)
│   ├── app/
│   │   ├── main.py             # app factory, router mounting, lifespan
│   │   ├── config.py           # pydantic-settings (DATABASE_URL, ANTHROPIC_API_KEY, R2…)
│   │   ├── db.py               # engine, async session, tenant_session() dependency
│   │   ├── core/               # ── PLATFORM KERNEL (never imports from modules/) ──
│   │   │   ├── tenancy/        # tenant model, RLS helpers, TenantScopedRepository
│   │   │   ├── auth/           # jwt, passwords, router, invitations, rbac
│   │   │   ├── modules/        # registry.py (ModuleManifest, install/uninstall)
│   │   │   ├── events/         # outbox.py (emit_event), dispatcher.py, subscriptions
│   │   │   ├── audit/          # append-only audit_log writer + query router
│   │   │   ├── approvals/      # proposed_actions service + approve/reject router
│   │   │   ├── documents/      # upload, R2 storage adapter
│   │   │   └── agents/         # ── AGENT RUNTIME ──
│   │   │       ├── loop.py     #   Claude tool loop, step persistence, pause/resume
│   │   │       ├── tools.py    #   ToolSpec base, strict JSON-schema registration
│   │   │       ├── policy.py   #   L1–L4 policy engine (single enforcement chokepoint)
│   │   │       ├── memory.py   #   pgvector memory store (Voyage embeddings)
│   │   │       ├── llm.py      #   Anthropic wrapper: caching, retries, usage metering
│   │   │       └── runs.py     #   agent_runs / agent_steps persistence
│   │   ├── modules/
│   │   │   └── finance/        # ── THE ONE MVP MODULE ──
│   │   │       ├── manifest.py #   ModuleManifest("finance", events, tools, L1 default)
│   │   │       ├── models.py   #   vendors, invoices, POs, bank tx, matches…
│   │   │       ├── router.py   #   /api/v1/finance/*
│   │   │       ├── ingestion.py#   PDF → Claude extraction → validation
│   │   │       ├── matching.py #   deterministic match scorer (invoice↔PO, bank recon)
│   │   │       ├── forecasting.py
│   │   │       ├── anomalies.py
│   │   │       └── agent.py    #   FinanceAgent: system prompt, tools, task handlers
│   │   └── workers/tasks.py    # procrastinate tasks: dispatch_event, extract_invoice,
│   │                           #   run_agent_task, execute_approved_action, nightly jobs
│   ├── tests/                  # unit, api, tenancy-isolation, policy matrix, matching
│   └── evals/
│       ├── golden_invoices/    # labeled PDF + ground-truth JSON pairs
│       ├── run_extraction_eval.py   # Batch-API harness, per-field accuracy report
│       └── thresholds.yml      # CI regression gates
│
├── frontend/                   # NEW product app
│   └── src/app/
│       ├── (auth)/login, invite/[token], reset/
│       ├── (app)/dashboard/
│       ├── (app)/approvals/            # approval inbox — the L1/L2 heart of the product
│       ├── (app)/finance/invoices/     # list + [id] split review screen
│       ├── (app)/finance/reconciliation/
│       ├── (app)/finance/cashflow/
│       ├── (app)/agents/activity/      # agent run timeline / audit view
│       ├── (app)/settings/modules/     # autonomy sliders per module
│       └── onboarding/                 # wizard
│   └── e2e/                            # Playwright smoke specs
│
└── packages/contracts/         # OpenAPI export + shared event-name/enum constants
```

**Architecture style: modular monolith.** One FastAPI process + one Procrastinate worker sharing code and DB. Modules communicate ONLY via events and the registry — an import-linter contract in CI enforces that `core/` never imports `modules/*` and modules never import each other. That contract IS the plug-and-play guarantee.

---

## 4. Core Platform Architecture

### 4.1 Module registry (the plug-and-play seam)
```python
class ModuleManifest(BaseModel):
    key: str                      # "finance"
    name: str
    version: str
    emits: list[str]              # ["finance.invoice.extracted", ...]
    subscribes: list[str]
    agent: AgentSpec | None       # system prompt ref, tool names
    default_autonomy: AutonomyLevel   # L1
    settings_schema: dict         # JSON schema for per-tenant settings
```
Synced to a `modules` table at startup; tenants install via `tenant_modules` rows (`POST /api/v1/modules/{key}/install`). Uninstall = disable flag, data retained. Routers/tools/subscriptions only active for tenants where installed.

### 4.2 Event bus: transactional outbox + Procrastinate
- `emit_event(session, tenant_id, name, payload)` inserts into `events` and enqueues `dispatch_event(event_id)` **in the same transaction** (Procrastinate stores jobs in Postgres → atomic).
- Dispatcher looks up subscribers in the registry, fans out one job per subscriber with independent retry/backoff.
- Consumers are idempotent: dedupe on `(event_id, subscriber)` in `event_deliveries`.
- The future orchestrator ("sales order → inventory check → cash-flow update") rides this same mechanism as just another subscriber.

### 4.3 Agent runtime
**Loop (`core/agents/loop.py`)** — hand-owned tool loop (not the SDK runner) because every tool call must: pass the policy engine, persist as an `agent_steps` row, and support pausing at an approval and resuming later.

1. Load AgentSpec + tenant config (autonomy level, settings) + relevant memories.
2. Call Claude with adaptive thinking, effort per task, strict tools, and **prompt caching**: byte-stable system prompt + tool list marked `cache_control` (design the prefix > 4096 tokens); volatile context (date, task payload) in the first user message.
3. Each `tool_use` → `policy.evaluate()` → execute / propose / pause → append `tool_result`, persist step, loop until `end_turn`.
4. Hard caps: `max_iterations` per run, per-run token budget; all usage metered to `llm_usage`.

**Policy engine (`core/agents/policy.py`) — the single autonomy chokepoint:**
```python
def evaluate(action: ProposedAction, cfg: TenantModuleConfig) -> Decision:
    # Decision ∈ {EXECUTE, EXECUTE_AND_NOTIFY, REQUIRE_APPROVAL, SUGGEST_ONLY, DENY}
```
- `risk == read` → EXECUTE at any level.
- **L1** → SUGGEST_ONLY: writes a `proposed_actions` row, returns a synthetic tool_result ("proposal recorded"); nothing mutates.
- **L2** → REQUIRE_APPROVAL: writes `proposed_actions(pending)`, pauses run (`awaiting_approval`); approval executes + resumes via worker.
- **L3** → EXECUTE_AND_NOTIFY; **L4** → EXECUTE. All paths audit.
- **Guardrails that outrank levels:** money-amount caps ("never auto-execute above $X regardless of level"), per-level tool denylist, tenant kill switch (`tenant_modules.paused`), and `tenants.shadow_mode` (propose everything, execute nothing).

**Memory (`core/agents/memory.py`)** — `agent_memories` with `vector(1024)`. When a human corrects an extraction or match, write a structured memory (`vendor_correction`, `matching_rule`); before each run, retrieve top-k scoped to (tenant, module, entity) and inject. The per-vendor corrections are what actually move accuracy.

**Audit** — append-only `audit_log` written by the tool dispatcher and approval service; app DB role has no UPDATE/DELETE grant on it.

---

## 5. Database Schema

All tenant tables carry `tenant_id UUID NOT NULL` + RLS policy + `(tenant_id, …)` index.

**Platform kernel**
- `tenants(id, name, slug, industry, status, shadow_mode, created_at)`
- `users(id, tenant_id, email, password_hash, full_name, status)` · `roles` (seeded: owner, admin, finance_manager, approver, viewer) · `user_roles` · `refresh_tokens` · `invitations`
- `modules(key, name, version, manifest jsonb)` · `tenant_modules(tenant_id, module_key, enabled, autonomy_level 1..4, settings jsonb, paused, installed_at)`
- `events(id, tenant_id, name, payload, actor, created_at)` · `event_deliveries(event_id, subscriber, status, attempts, last_error)`
- `audit_log(id, tenant_id, occurred_at, actor_type ∈ {agent,user,system}, actor_id, module_key, action, entity_type, entity_id, before, after, agent_run_id, proposed_action_id, autonomy_level)` — append-only
- `agent_runs(id, tenant_id, module_key, agent_key, trigger ∈ {event,schedule,manual,approval_resume}, task_type, input, status ∈ {running, awaiting_approval, succeeded, failed, cancelled}, usage, started_at, finished_at, error)`
- `agent_steps(id, run_id, idx, kind ∈ {model_call, tool_call, tool_result, decision}, tool_name, payload, result, policy_decision, tokens)`
- `proposed_actions(id, tenant_id, run_id, module_key, tool_name, payload, rationale, confidence, risk, status ∈ {proposed, pending_approval, approved, rejected, executed, failed, expired}, decided_by, decided_at, executed_at, expires_at)`
- `agent_memories(id, tenant_id, module_key, kind, entity_ref, content, embedding vector(1024))`
- `documents(id, tenant_id, kind, storage_key, filename, sha256 UNIQUE(tenant_id, sha256), status, uploaded_by)`
- `llm_usage(id, tenant_id, run_id, model, input_tokens, output_tokens, cache_read_tokens, cost_usd)` — cost metering from day one

**Finance domain**
- `vendors(id, tenant_id, name, normalized_name, tax_id, default_currency, payment_terms_days, extraction_hints jsonb)`
- `invoices(id, tenant_id, vendor_id, document_id, invoice_number, issue_date, due_date, currency, subtotal, tax_amount, total_amount, status ∈ {uploaded, extracting, extracted_pending_review, approved, matched, paid, rejected, duplicate}, extraction jsonb /* raw output + per-field confidence */, reviewed_by, UNIQUE(tenant_id, vendor_id, invoice_number))` · `invoice_line_items`
- `purchase_orders` + `po_line_items(…, received_quantity)`
- `bank_accounts` · `bank_transactions(…, hash UNIQUE(tenant_id, hash))`
- `matches(id, tenant_id, kind ∈ {invoice_po, invoice_bank_tx}, invoice_id, po_id, bank_transaction_id, score, method ∈ {deterministic, agent}, status ∈ {suggested, confirmed, rejected}, rationale)`
- `cashflow_forecasts(id, tenant_id, generated_at, horizon_days, series jsonb, assumptions jsonb, agent_run_id)`
- `anomalies(id, tenant_id, kind ∈ {duplicate_invoice, price_jump, unusual_vendor, round_amount, terms_violation}, severity, entity_type, entity_id, detail, status)`

---

## 6. Finance Agent — Concrete Design

**Principle: deterministic code computes; the agent perceives, adjudicates, and explains. Money math never comes from the model.**

### Tasks (each an `agent_runs.task_type`)
| Task | Trigger | What happens |
|---|---|---|
| `extract_invoice` | `finance.document.uploaded` | PDF → structured extraction → validation → `extracted_pending_review` |
| `match_invoice_to_po` | `finance.invoice.reviewed` | Deterministic candidate scoring first; agent adjudicates ambiguous cases with rationale |
| `reconcile_bank_transactions` | bank CSV import | Propose invoice↔transaction matches |
| `forecast_cashflow` | nightly cron | Deterministic projection from due dates/terms; agent writes narrative + assumptions |
| `detect_anomalies` | new invoice + nightly sweep | Rules engine feeds candidates; agent triages and explains |

### Tool set (strict JSON schemas)
**Read (auto-allowed at all levels):** `get_invoice`, `search_invoices`, `get_vendor_history`, `list_open_purchase_orders`, `list_unmatched_bank_transactions`, `get_cash_position`, `recall_memories`

**Write (policy-gated):** `create_invoice_record`, `propose_invoice_po_match`, `propose_bank_match`, `flag_anomaly`, `mark_invoice_duplicate`, `save_memory`, `notify_user`

### PDF extraction pipeline
1. Upload → `documents` row + R2 object; sha256 dedupe rejects re-uploads.
2. Worker sends PDF as a base64 `document` content block to Claude — handles text AND layout/vision, **no separate OCR step**.
3. `client.messages.parse(output_format=InvoiceExtraction)` — Pydantic model with header fields, line items, **per-field confidence + source page**. Prompt includes tenant currency defaults, per-vendor `extraction_hints`, and recalled correction memories.
4. **Deterministic validation (code, not model):** line items sum to subtotal (±0.01); subtotal + tax == total; date sanity; currency whitelist; duplicate check (exact + fuzzy).
5. Result flows through the policy engine → at L1 lands as a suggestion pending review → emits `finance.invoice.extracted`.

### Human approval wiring (this IS the L1 product)
- **API:** `GET /api/v1/approvals?status=pending` (inbox) · `POST /approvals/{id}/approve` · `POST /approvals/{id}/reject` · `POST /invoices/{id}/review` (field-level corrections)
- **UI:** `/approvals` inbox with one-click approve/reject; `/finance/invoices/[id]` **split view** — PDF left (react-pdf), editable extracted fields with confidence badges right, fields < 0.85 confidence highlighted.
- Every correction writes BOTH a vendor-correction memory (improves next run) AND a labeled eval example (measures it).
- L2 is the same machinery + run pause/resume — a config change, not a rebuild.

### Extraction evaluation
- **Golden set:** 50 labeled invoices to start (scanned + native PDFs, multi-page, multi-currency, credit notes, degraded scans) → grows to 200+ by auto-harvesting review-screen corrections.
- **Harness:** runs the exact production prompt/schema via the **Batch API (50% cost)**; scores per field (exact match for numbers/dates as Decimals, fuzzy for vendor name, alignment score for line items).
- **CI gate (`thresholds.yml`):** e.g. `total_amount_exact ≥ 0.98`, `invoice_number_exact ≥ 0.95`, `line_item_f1 ≥ 0.90`. Any prompt/schema/model change must pass; nightly run catches drift.
- **Calibration:** track whether model-reported confidence correlates with correctness; tune the UI highlight threshold from data.

---

## 7. Step-by-Step Build Plan (~14 weeks to beta)

### Phase 0 — Skeleton & rails (Week 1)
Monorepo scaffold · docker-compose (postgres+api+worker+web) · Makefile · GitHub Actions CI · CLAUDE.md conventions.
**Done when:** fresh clone → `make dev` → web reaches API `/healthz`; CI green.

### Phase 1 — Tenancy, auth, RBAC, module registry (Weeks 2–3)
Migrations (tenants, users, roles, refresh_tokens, invitations) · RLS policies + `tenant_session()` dependency + non-superuser app role · JWT + argon2 + refresh rotation · invitation emails · modules + tenant_modules + install endpoint · audit_log writer · frontend auth pages + module settings page with autonomy slider (L1 only enabled).
**Done when:** the **adversarial isolation suite passes** — two seeded tenants, zero cross-tenant reads/writes even with app-level filters deliberately removed (RLS catches it).

### Phase 2 — Events, workers, documents (Weeks 4–5)
Outbox + dispatcher + retry/backoff + dead-letter visibility · R2 storage adapter + presigned uploads · documents endpoint + sha256 dedupe · drag-drop upload UI · llm_usage metering table.
**Done when:** uploading a PDF emits an event a worker consumes; killing the worker mid-job and restarting produces exactly-once effect.

### Phase 3 — Invoice extraction + review UI + evals (Weeks 6–8) ← **THE WEDGE**
Finance migrations · InvoiceExtraction schema · Anthropic wrapper (caching layout, retries, usage capture, refusal handling) · extraction task + deterministic validation · vendor auto-create/normalize · duplicate detection · split review screen · corrections → memories + eval examples · 50-invoice golden set · eval harness + CI thresholds.
**Done when:** 10 real invoices process end-to-end in < 2 min each; evals ≥ thresholds; a correction on vendor X visibly improves the next extraction for X; measured cost < $0.15/invoice.

### Phase 4 — POs, bank import, matching, approvals inbox (Weeks 9–10)
PO/bank CSV importers (column-mapping UI, hash dedupe) · deterministic match scorer · agent adjudication of ambiguous candidates only · approvals endpoints + inbox UI + reconciliation screen · audit view of decisions.
**Done when:** seeded dataset (20 POs, 60 invoices, 200 transactions) → ≥ 80% of clean matches auto-suggested correctly, ZERO auto-confirmed at L1; Playwright covers upload→review→match→approve.

### Phase 5 — Full agent runtime, forecast, anomalies, L2 (Weeks 11–12)
Refactor Phase 3–4 code onto the generalized `loop.py` · policy chokepoint + guardrail caps + kill switch · agent_runs/steps persistence + `/agents/activity` UI · pause/resume on approval · nightly cash-flow forecast + chart · anomaly rules + agent triage · enable L2 on the slider.
**Done when:** an L2 run demonstrably pauses at a write tool, appears in the inbox, resumes on approve; injected anomalies (duplicate invoice, 3× price jump) are flagged with sane explanations; policy unit tests cover every level × risk cell.

### Phase 6 — Onboarding wizard, shadow mode, deploy, beta (Weeks 13–14)
Wizard (industry → modules → CSV/PDF import → autonomy slider → invite team → go live) · `shadow_mode` (agents propose everything, execute nothing, banner in UI) · Railway deploy (api, worker, cron, Postgres, web) + R2 + Resend + Sentry + per-tenant LLM budget alarms · demo tenant · onboard 3–5 design partners.
**Done when:** a new company self-serves from signup to first reviewed invoice in < 30 minutes without founder touch; production is rebuildable from documented steps.

### Explicitly parked for post-beta
Stripe billing · Xero/QuickBooks sync · SSO/OIDC · second module (Inventory or HR next, per the catalog) · orchestrator agent beyond the event dispatcher · L3/L4 autonomy · module marketplace SDK · open third-party API.

---

## 8. Testing & Verification Strategy

| Layer | Tooling | Coverage |
|---|---|---|
| Unit | pytest | Policy matrix (every level × risk), validation math, match scorer, JWT rotation |
| Tenancy | pytest vs dockerized Postgres (same image as prod) | Permanent adversarial RLS isolation suite; migration smoke; outbox idempotency |
| API | httpx AsyncClient | Auth flows, RBAC 403s, approvals lifecycle, module install |
| LLM boundary | respx-recorded Claude responses | Deterministic CI; real API only in evals |
| Agent evals | Batch-API harness + `thresholds.yml` CI gate + nightly drift run | Extraction accuracy per field; later: matching adjudication set |
| E2E | Playwright vs compose stack (mocked-LLM flag) | signup→login; upload→extract→review→approve; L2 pause→resume; onboarding wizard |
| Production | Sentry, structured logs (tenant_id/run_id), worker heartbeat, llm_usage dashboards | Per-tenant cost + error visibility |

---

## 9. Key Risks & Mitigations

1. **LLM extraction errors on financial data** (wrong totals = dead product)
   → L1 + shadow-mode launch; deterministic arithmetic validation independent of the model; per-field confidence UI with review thresholds; eval gate in CI + nightly drift; every human correction becomes both a memory and an eval example; money caps outrank autonomy level.

2. **Tenant data isolation failure** (one leak ends a financial SaaS)
   → Postgres RLS as the structural guarantee, not app filters; `SET LOCAL` inside per-request transactions (no pool bleed); no raw SQL; permanent adversarial test suite; tenant-namespaced R2 keys + presigned URLs only.

3. **LLM cost blowout**
   → Prompt caching on the frozen system prompt + tools (verify `cache_read` in metering); Batch API for evals/nightly sweeps; effort tuned down for routine steps; per-tenant monthly budgets with alerts + soft cutoff; measured $/invoice from Phase 3 so pricing is grounded in data.

4. **Scope creep** (the vision is an entire ERP; the MVP is one module)
   → Hard rule: no non-finance domain tables/routes/agents before beta. The registry is a *seam*, proven by finance consuming only public core APIs (import-linter enforced) — not by building module #2. Phase gates with written definitions of done; parked backlog.

5. **Solo-founder velocity**
   → Boring, documented stack; CLAUDE.md + contracts package keep Claude Code sessions consistent; everything reproducible from `make dev`; each phase ships a deployable increment.

---

## 10. Post-Beta Roadmap (maps back to the reference document)

| Reference-doc phase | Zorum equivalent |
|---|---|
| Phase 3 — Module Marketplace | Module SDK + marketplace UI; add Inventory or HR as module #2 using the proven registry seam |
| Phase 4 — Autonomy Graduation | Enable L3/L4 for agents with proven reliability metrics; governance dashboards |
| Phase 5 — Scale & Ecosystem | Open API for third-party modules; multi-tenancy hardening (schema-per-tenant for large customers); connector library (Xero/QBO, Shopify, banks, carriers); swap outbox dispatcher for Kafka/NATS only when volume demands it |
