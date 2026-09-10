# PROPTO — Society Complaint & Ticket Management (PRD)

## Feature (2026-06) — 4 new society tabs from Admin Dashboard reference
Added, styled to match `Propto_Admin_Dashboard.html` (blue/indigo cards, colored top-border stat cards, grid tables) using existing `DashKit` components:
- **Assets** (`/assets`): register with stat cards (total/due soon/overdue/scheduled) + table + Add Asset dialog. Backend: `GET/POST/DELETE /api/society/assets` (collection `assets`).
- **Escalated** (`/escalated`): red panel, grid table (Ticket ID/Issue/Unit/Resident/Reason/SLA/Assign) with SLABar; "Assign Now" → Tickets. Backend: `GET /api/society/tickets/escalated` (status=Escalated OR Open/Pending past sla_due).
- **Committee** (`/committee`): member cards (role-colored avatar/badge, tower/phone/email) + Add Member dialog. Backend: `GET/POST/DELETE /api/society/committee` (collection `committee`).
- **Assignment Logic** (`/assignment-logic`): read-only routing view — 6-step flow tiles, SLA-by-severity table, live vendor coverage by category. Backend: `GET /api/society/assignment-config`.
Nav + routes added in `Layout.jsx` + `App.js`. All endpoints society-scoped (super-admin scope-aware). Verified via curl (all 4) + screenshots (Assets, Assignment Logic render correctly). Frontend compiles clean.


## Architecture change (2026-06) — Redis queue + async worker + Gemini-first classification (VPS)
User moved to a VPS with Redis and requested a queue/worker pipeline (Redis+BullMQ pattern, implemented in Python) and a reordered classification.
New flow: WhatsApp → Webhook → (REDIS_URL set) LPUSH to Redis + return 200 → `worker.py` (persistent) BRPOPLPUSH → pre-filter → Gemini "is this a complaint?" (+extract) → 10,000 taxonomy enrich → if no match, Gemini generates ticket content → ticket.
Files:
- `task_queue.py` (new): redis.asyncio LPUSH/queue helpers; `redis_enabled()` gates queue vs inline. Hardened conn (socket_timeout=None, health_check_interval).
- `worker.py` (new): async consumer, reliable BRPOPLPUSH→process→LREM, retries on redis hiccups. Run as systemd `propto-worker`.
- `routers/whatsapp_router.py`: `_process_*`→public `process_whapi/process_meta`; webhooks enqueue when REDIS_URL set, else inline (cPanel fallback preserved).
- `ai_engine.py`: `prefilter()` drops greetings/spam before any LLM; `analyze_message()` reordered to Gemini-first → taxonomy enrich → Gemini content.
- `pipeline.py`: uses `prefilter()`.
- `.env.vps` (new): includes REDIS_URL + user's Gemini key. `requirements.txt`: added `redis`.
- Guide: `DEPLOYMENT_VPS.md` (Redis install/secure, gunicorn+uvicorn systemd API, systemd worker, nginx+certbot, firewall, verify, ops).
Verified e2e in preview with local Redis: complaint enqueued→worker→ticket; greeting ignored (no Gemini); webhook 200 in ~0.2s. Note: OpenAI NOT used — Gemini used for both steps per user. Preview reverted to inline (REDIS_URL removed from workspace .env).


## Taxonomy upgrade (2026-06) — 10,000-issue workbook
Replaced the 1,000-row taxonomy with the new `Propto_10000_Issue_Taxonomy.xlsx` (sheet "Issue Taxonomy", 10,000 rows, 181 categories). New columns: Issue ID, Category, Subcategory, Issue / Problem, Severity, Target SLA, Default Owner / Vendor, Asset Impact, Deduplication Rule, Propto Action.
- `situations_kb.py` rewritten: matches on **Issue / Problem** (specific); maps Severity→priority; derives `handled_by`/`vendor_required` from **Default Owner / Vendor** (external-vendor keywords → route to vendor, else in-house "Society Manager"); `app_category` via keyword heuristics → demo vendor enum (Plumbing/Electrical/Lift/Security/Housekeeping/Pest Control/Gardening/Parking/DG Set/Civil). Matching optimized: fuzzy ratio only for rows sharing a token (2–39ms at 10k rows).
- Pre-built `backend/data/taxonomy.json` (10k items) so cPanel needs no runtime Excel/pandas/network; loader falls back to fetching `_XLSX` if cache missing.
- `ai_engine.analyze_message`: `matched_situation` now = the Issue/Problem text.
- Verified: sample complaints match with correct category/severity/routing; greetings fall through to AI.
USER ACTION: redeploy `situations_kb.py`, `ai_engine.py`, and **`data/taxonomy.json`** (overwrites the old cache); Restart.


## CRITICAL FIX v2 (2026-06) — Webhook writes never reached Atlas under Passenger
User observation: they CAN create a poll (posts to WhatsApp + persists) but inbound messages create NO tickets, and "nothing updates in Atlas." Decisive: poll creation is written INSIDE the HTTP request (awaited) → persists; the webhook's detached background task (`_spawn`/ensure_future from the prior fix) never wrote because Passenger/LSAPI kills/recycles the worker right after the 200 is sent — killing the daemon-thread loop and the pending task before its Atlas write. Confirmed a2wsgi uses a per-middleware daemon-thread loop (asgi.py L130-134) and waits only for the request's own asgi_task (L300-303).
FIX (reverted to inline, guaranteed-write):
- `whatsapp_router.py`: both webhooks now `await asyncio.wait_for(_process_whapi/_process_meta(...), timeout=45)` INLINE, then return 200. Write completes before the worker can be recycled. 45s cap prevents a hung worker.
- `ai_engine.py`: `_call_llm` wrapped in `asyncio.wait_for(..., 15s)` (both Gemini-native and Emergent paths); native `generate_content(..., request_options={"timeout":12})`. No LLM call can hang a worker.
- `whatsapp_client.py`: outbound `_whapi_post`/`_meta_post` timeout 20s→8s. Sends happen AFTER the ticket is persisted, so a slow send never loses the ticket.
Verified live ingress: taxonomy complaint → 200 in 2.05s with ticket written to DB before response.
Combined with LSAPI_CHILDREN≥20, this handles real volume. USER ACTION: redeploy `routers/whatsapp_router.py`, `ai_engine.py`, `whatsapp_client.py`; Restart.


## Deployment change (2026-06) — Backend moved to its own subdomain (api.propto.app)
User asked to switch to a dedicated backend subdomain. Frontend stays on `manage.propto.app`, backend runs as its own cPanel Python App on `api.propto.app` (isolated worker pool, no .htaccess/SPA conflict). Keeps `/api` prefix → webhook `https://api.propto.app/api/whapi/webhook`.
Changes:
- `frontend/.env.production` → `REACT_APP_BACKEND_URL=https://api.propto.app` (cross-origin).
- `frontend/public/.htaccess` → pure SPA fallback (no /api passthrough needed now).
- `backend/.env.cpanel` → `CORS_ORIGINS=https://manage.propto.app` (must be exact origin; server uses allow_credentials=True so no `*`).
- `passenger_wsgi.py` unchanged — root-mount case verified (SCRIPT_NAME='' → `/api/health` 200).
- `DEPLOYMENT.md` fully rewritten for the two-subdomain setup incl. AutoSSL for api subdomain, and LSAPI_CHILDREN=20 / PassengerMaxPoolSize guidance.
NOTE: the subdomain alone does NOT fix processing — the non-blocking webhook fix (already shipped) + more workers do. Subdomain just isolates/cleans the backend.


## CRITICAL FIX (2026-06) — cPanel LSAPI worker pool exhaustion (nothing processed)
User's cPanel log: `Reached max children process limit: 6 ... busy: 8, please increase LSAPI_CHILDREN` + workers killed by signal 15. ROOT CAUSE: webhook handlers processed everything INLINE (AI/Gemini call ~5s + multiple 20s outbound WhatsApp sends) before returning 200, pinning each of the 6 LSAPI workers for many seconds. Whapi bursts (messages + chats_updates + poll patches) saturated the pool instantly → no group messages, poll votes, or anything got processed.
FIX (whatsapp_router.py): both webhooks (`/api/whapi/webhook`, `/api/webhook`) now parse the JSON, spawn `_process_whapi`/`_process_meta` as an independent task via `_spawn()` (asyncio.ensure_future on the persistent loop; kept in `_bg_tasks` set so not GC'd), and return `{"status":"ok"}` immediately. The spawned task is NOT the request's asgi_task, so a2wsgi/Passenger does not cancel it — it keeps running on the loop thread after the worker is freed.
Verified e2e through live ingress: webhook responded in 0.28s while the background task matched society, ran AI, created ticket, and logged to AI Activity.
USER ACTION: redeploy `routers/whatsapp_router.py` (+ `whatsapp_client.py` from the poll fix) and Restart. Optionally raise LSAPI_CHILDREN in cPanel, but the code fix removes the saturation. This also unblocks the earlier "no AI Activity" and "poll votes not updating" reports (the workers were simply never free to process them).


## Fix (2026-06) — Poll votes not tallying + AI Activity diagnostics
Confirmed exact Whapi poll payloads from official docs:
- `messages.patch` mode → `messages_updates[].after_update.poll.results[{name,count,voters}]` (our parser already handled this; verified: yes=2/no=1).
- `messages.post` → a vote arrives as `type:"action"`, `action:{type:"vote", target:<pollMsgId>}`, usually `from_me:true` — our parser was SKIPPING it (from_me filter ran before action handling). ROOT CAUSE of votes not updating when only messages.post is enabled.
Shipped:
- `parse_whapi_inbound`: detect vote actions BEFORE the from_me filter; emit a poll item with `poll_fetch_id`.
- `whatsapp_client.get_poll_results(msg_id)` → GET `/messages/{id}` to fetch authoritative poll state; router fetches + applies on a vote action. Polls now self-heal even without messages.patch.
- Whapi webhook now logs group→society mapping: on match `"Whapi: group <chat_id> matched society <id> (<name>)"`; on miss `"NO society mapped to group chat_id=<x> -> DROPPED. Configured societies/chat_ids=[...]"` — decisive for the "no AI Activity" report.
Note (AI Activity): since the suggestion POLL posted to the group, the society's stored `chat_id` is correct, so inbound group text should match the same society. Remaining likely causes: messages sent BEFORE connecting (Whapi doesn't replay), non-complaint text (logs as "ignored"), or viewing AI Activity under a different society/account than the group is bound to. New log line confirms which.
USER ACTION: redeploy backend (`whatsapp_client.py`, `routers/whatsapp_router.py`) + restart; enable Whapi `messages.patch` (recommended); send a fresh complaint + a fresh vote; check the new log line.


## Fix (2026-06) — Group messages not reaching AI Activity
Root cause (confirmed from user's live cPanel log): Whapi webhook fires and messages parse fine (incoming `chat_id: 120363427379658951@g.us`, "Propto - Ticket Management"), but the webhook drops them because the society's stored `whatsapp_group.chat_id` didn't match → `continue` in `whatsapp_router.whapi_webhook`. No society matched, so `process_message`/`log_activity` never ran (nothing on AI Activity).
Fix shipped:
- `whatsapp_client.list_groups()` + `GET /api/society/whatsapp/groups` — live list of the linked number's Whapi groups (id + name; normalizes `@g.us`).
- `WhatsApp.jsx` — group **picker dropdown** (Load/Refresh) that auto-fills the exact Chat ID, plus a **"Change group"** button so a connected group can be corrected. Manual Chat ID input retained as fallback.
- Verified e2e in preview (picker loads real groups via user's Whapi token; selecting fills exact id) and endpoint via curl.
- NOTE: monitoring flag is NOT required for group ingestion — only `whatsapp_group.chat_id` match. Non-complaint texts ("Hi") log as "ignored" (still visible in AI Activity); send a real complaint to get a ticket.
- USER ACTION: redeploy backend (`whatsapp_client.py`, `routers/whatsapp_router.py`) + rebuild/upload frontend, then WhatsApp Integration → Change group → pick "Propto - Ticket Management" → Save.


## Deployment Update (2026-06) — Single-domain cPanel (`manage.propto.app`)
User reset their server (kept MongoDB Atlas) for a fresh single-domain install: React + FastAPI both on `manage.propto.app`.
- FastAPI Python App mounted at sub-path `/api`. `passenger_wsgi.py` folds `SCRIPT_NAME` back into `PATH_INFO` (verified via `backend/tests/subpath_probe.py`) because Starlette 0.37.2 strips root_path during routing and would 404 `/api/*`.
- `frontend/public/.htaccess`: single-domain SPA fallback that excludes `/api` (lets Passenger own the backend).
- `frontend/.env.production`: `REACT_APP_BACKEND_URL=https://manage.propto.app` (api.js appends `/api`).
- `backend/.env.cpanel`: upload-ready env template (JWT_SECRET generated, CORS + admin + Whapi pre-filled; user pastes MONGO_URL + GEMINI_API_KEY).
- Single clean guide: `/app/DEPLOYMENT.md`. Removed old `DEPLOYMENT_SUBDOMAIN.md`, `DEPLOYMENT_CPANEL.md`, `frontend/server.js`, and the `express` dependency.
- Only Whapi used (no Meta). Demo seed (Green Valley) retained.
- STATUS: package ready; USER must upload, set env, `pip install -r requirements-cpanel.txt`, `python seed.py`, Restart, then verify `/api/health` and build/upload frontend.


## Original Problem Statement
AI-powered Society Complaint Management SaaS. Residents raise maintenance complaints via WhatsApp society groups. Google Gemini AI detects complaints, extracts info (category, flat, tower, priority, preferred time), auto-creates maintenance tickets, assigns vendors, and manages the lifecycle over WhatsApp. Super Admin + Society Admin dashboards. Multi-society SaaS.

## User Choices
- WhatsApp: real WhatsApp Business Cloud API (keys pending; simulator + live webhook both built)
- AI: Google Gemini (gemini-2.5-flash) via Emergent Universal LLM key
- Auth: JWT email/password
- Payments (Razorpay): DEFERRED
- Core priority: AI detection → auto ticket → vendor assignment → dashboards

## Architecture
- Frontend: React (CRACO) + Tailwind + shadcn/ui + Recharts. JWT Bearer token in localStorage (`propto_token`).
- Backend: FastAPI, routers under /app/backend/routers (auth, super, society, ai, whatsapp, reports). Pipeline in pipeline.py, AI in ai_engine.py, WhatsApp in whatsapp_client.py.
- DB: MongoDB (users, societies, vendors, residents, tickets, ai_activity, review_queue).

## Personas
- Super Admin: manages societies, complaint categories, platform analytics. Can "Manage" (scope) into any society.
- Society Admin: manages own society's tickets, vendors, residents, WhatsApp, AI activity, HITL review, reports.

## Implemented (2026-07-24)
- JWT auth + role gating; seeded super admin + demo society (Green Valley, admin@greenvalley.com) with 5 vendors, 4 residents.
- AI pipeline: rule-engine keyword filter → Gemini JSON classification → confidence workflow (>=0.7 auto ticket; below → HITL review queue). Graceful fallback to review queue on AI failure.
- Duplicate detection (flat + category + open/pending). Vendor auto-assignment (category + availability + lowest workload). SLA by priority.
- WhatsApp: live Meta webhook (GET verify + POST with signature validation) + interactive button handling (vendor accept/reject/resolved, resident confirm/cancel) + Live Simulator panel.
- Super Admin: Society Management (CRUD, activate/deactivate, manage-into), Platform Analytics.
- Society Admin: Dashboard (6 stat cards + charts), Tickets (search/filter/detail sheet/timeline/assign/reassign/status/close), Vendors CRUD, Residents CRUD + Excel/CSV import, AI Activity command-center logs, HITL Review Queue, WhatsApp group mgmt, Reports (daily/category/resolution/vendor).
- Verified via testing agent: backend 18/18 passed, frontend all critical flows passed.

## Backlog
### P1
- Activate real WhatsApp once Meta keys provided (WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_WABA_ID, WHATSAPP_APP_SECRET); create approved message templates.
- Store dedicated `resolved_at` for accurate resolution-time analytics.
- Export reports to Excel/PDF (spec Module 13).
- Reminder/escalation notifications on SLA breach.
### P2
- Super Admin editable complaint categories (currently fixed list).
- Attachments on tickets (object storage).
- Razorpay billing / multi-society subscription.
- Feedback collection after resolution.

## Next Tasks
1. Collect Meta WhatsApp credentials and go live.
2. Add report export (Excel/PDF).
3. Add resolved_at + SLA breach escalation.

## Passenger/a2wsgi hang fix (ESOCKETTIMEDOUT, 2026-08 update)
- Symptom: on cPanel every request to the webhook hung → Whapi ESOCKETTIMEDOUT. Also fixed a prior RecursionError caused by cPanel's default self-loading `passenger_wsgi.py` stub (must use our direct-import a2wsgi version, no `imp.load_source`).
- Root cause: under a2wsgi the request path waits for FastAPI lifespan startup, and `startup()` did blocking index-creation + Atlas seeding → hang when Atlas is slow under Passenger.
- Fix: `server.py` startup is now fire-and-forget (`app.state._seed_task = asyncio.create_task(_seed_all())`), `_seed_all()` guarded with try/except. Serving never blocks on seeding. On a fresh DB, run `python seed.py` once at deploy.
- Verified by testing_agent iteration_7.json: ~0.1s first-request latency after cold restart, seeding still completes, 47/49 tests pass (2 pre-existing auth-hardening gaps).

## Webhook 500 hardening (self-host fix, 2026-06 update)
- Fixed Whapi webhook (`/api/whapi/webhook`) returning 500 on self-host: now wraps JSON parse + processing in try/except and ALWAYS returns 200 {status: ok} (tolerates empty/malformed Whapi test pings). Same hardening applied to Meta webhook (`/api/webhook`).
- `ai_engine._call_llm` degrades gracefully: uses `GEMINI_API_KEY` (own Gemini) if set, else Emergent key; returns "" instead of crashing when no LLM/emergentintegrations is available (self-host without a key → message ignored, not 500).
- `pipeline.create_ticket` confirmation send is best-effort (Whapi send failure can't crash ticket creation).
- Verified by testing_agent (iteration_5.json): all webhook payload variants return 200; AI pipeline regression clean. NOTE for self-host: set `GEMINI_API_KEY` on the server so non-taxonomy messages still get AI-classified.

## Self-host / cPanel deployment prep (2026-06 update)
- `backend/passenger_wsgi.py`: cPanel Passenger (WSGI) entry — wraps the FastAPI ASGI app via `a2wsgi`.
- `backend/seed.py`: one-time DB seeding for self-host (`python seed.py`).
- `backend/requirements-cpanel.txt`: requirements minus Emergent-only pkgs (`emergentintegrations`, custom `litellm`), plus `a2wsgi`.
- `ai_engine.py`: `emergentintegrations` import is now lazy; new `GEMINI_API_KEY` path uses `google-generativeai` (own key) for self-host, else Emergent LLM key. Both paths verified.
- `/app/DEPLOYMENT_CPANEL.md`: full step-by-step (MongoDB Atlas, Setup Python App, env vars, seed, frontend build+.htaccess SPA, webhook re-point). cPanel cannot host MongoDB (use Atlas) and needs the "Setup Python App" feature.

## Taxonomy Excel upgraded to 1,000 rows + Excel-first routing (2026-06 update)
- Replaced the old 500-situation `Issues.xlsx` with `Propto_Taxonomy_1000.xlsx` (sheet "Taxonomy (All)", 1000 rows, 41 categories). Only 5 columns used: Category, Subcategory, Severity, Vendor Required, Handled By. Cached at `backend/data/taxonomy.json`.
- **Excel-first**: `ai_engine.analyze_message` now checks the taxonomy FIRST (fuzzy match by Subcategory, threshold 0.6). On a match it uses the Excel category/sub-category/severity + regex flat extraction — no AI call. Only when there is NO match does it fall back to the Gemini AI classifier. Result carries `source_of_truth` = "excel" | "ai".
- **Handled By routing** in `pipeline.create_ticket`: "Society Manager" → ticket kept in-house (`assigned_to=Society Manager`, no vendor dispatch); "Vendor Assignment"/"Manager + Vendor" → auto-route to a matching vendor via app-category mapping. Ticket now stores `handled_by`, `vendor_required`, `assigned_to`.
- Category (41) mapped to app's vendor-routing enum via `_CAT_MAP`. Severity Critical→SLA 2h.
- Verified e2e: "Booster pump not working" → Water Supply/High/Vendor Assignment → AquaFix assigned; "water timing dispute" → Water Supply/Low/Society Manager → assigned_to Society Manager, no vendor.

## Audit Log per society (2026-06 update)
- New `audit.py` best-effort logger writes to `audit_logs` collection (society_id, category, action, summary, actor, ticket_number, meta, created_at). Never raises.
- Instrumented events: ticket raised, vendor auto-assigned & manually assigned, vendor accepted/rejected/resolved via WhatsApp, admin ticket status change/close, resident added/updated/removed, vendor added/updated/removed, suggestion created & status change, WhatsApp group connected & monitoring toggled, society created.
- Endpoint `GET /api/society/audit` (society-scoped, optional `category`, limit). Frontend `pages/society/AuditLog.jsx` at `/audit` (new "Audit Log" nav item) — filter chips + timeline with per-category icons/colors, actor and relative time.
- Verified e2e: events recorded with correct actor and rendered in UI.

## WhatsApp tab moved to Super Admin (2026-06 update)
- Removed "WhatsApp" from Society Admin nav; added it to Super Admin nav at `/super/whatsapp` (`pages/super/SuperWhatsApp.jsx`).
- Super page has a society selector dropdown; the existing WhatsApp config + Live Simulator UI is reused via a refactored `pages/society/WhatsApp.jsx` that accepts `societyId` + `embedded` props (all API calls pass the chosen `society_id`). Backend endpoints already accepted `society_id` — no backend change needed.
- Verified: selector loads per-society status (Majestique shows its bound Whapi group), embedded UI renders, society nav no longer shows WhatsApp.

## UI Redesign — Blue/Indigo Dashboards (2026-06 update)
- Rebranded the ENTIRE app from green/gold to blue/indigo (primary #2563eb, indigo #4f46e5) to match user-uploaded `Propto_Admin_Dashboard.html` reference. Theme driven via CSS vars in `index.css` + `brand.*` tokens in `tailwind.config.js` (kept token names green/gold to avoid touching every page). PROPTO logo kept.
- New reusable dashboard kit: `components/DashKit.jsx` (TopHeader, DashStat top-bordered stat cards, Panel, PriorityDot, SLABar).
- Society Dashboard (`pages/society/Dashboard.jsx`) rebuilt: greeting top-header, 6 stat cards (Total/Escalated/Open/Overdue/Assigned/Resolved Today), Assets+Vendors summary, Escalated table w/ SLA bars, Recent Tickets, Upcoming Maintenance (placeholder), right rail (Alerts, Resident Suggestions, Quick Actions).
- Super Admin Dashboard (`pages/super/SuperDashboard.jsx`) NEW at `/super/dashboard` (now the super landing page + nav item): platform stat cards, Societies Overview table w/ Manage, Overdue/Vendors rail cards, Top Categories bars.
- Backend: `/api/society/dashboard` extended (overdue/assigned/resolved_today + escalated list); NEW `/api/super/dashboard`.
- Assets & Upcoming Maintenance show "coming soon"/empty states (data not yet modeled). Verified: both endpoints + both dashboards render (screenshots) and global theme applied across pages.

## Excel Situation KB (2026-06 update)
- `Issues.xlsx` (500 situations, no header row: [#, Category, Sub-category, Situation, Priority, Time-window]) loaded into `backend/situations_kb.py`, cached at `backend/data/situations.json`.
- On a confident fuzzy match (threshold 0.6), the Excel category/sub-category/priority OVERRIDE the AI guess. Granular Excel category is mapped to the app's 11-category enum (`_CAT_MAP`) for vendor routing/analytics; raw Excel category kept in `kb_category`, sub-category in `sub_category`, matched text in `matched_situation`.
- Ticket schema now persists `sub_category`, `kb_category`, `matched_situation` (stored only; not shown in UI per user choice).
- Verified e2e via simulator: correct category/priority/sub_category + correct vendor auto-assignment. Backend-tested (agent).

## Complaint-detection safety net (2026-06 bug fix)
- BUG: clear complaints (e.g. "Building ka lift down hai", "A wing ka lift stuck hai") were logged as "AI: not a complaint" and dropped. Root cause: pipeline relied 100% on Gemini as the first gate; if Gemini said NotComplaint OR the Gemini call failed/returned empty, `_ai_classify` silently defaulted to `intent=NotComplaint` — taxonomy + keyword list never got a chance.
- FIX (`backend/ai_engine.py`): added deterministic safety net in `analyze_message`. After Gemini classify, run 10k-taxonomy match + `strong_keyword_hit()` (new). If Gemini says NotComplaint but taxonomy matches (good score) OR a domain/complaint keyword hits, override to Complaint, set category (keyword-derived if needed), bump confidence to >=0.85 so a ticket is created. Works even when Gemini is fully down (Gemini-failure fallback).
- Added safe Gemini health logging in `_call_llm` ("Gemini OK (N chars)" / "Gemini returned empty" / failure warning) — never logs the key. Visible in worker/API logs to diagnose VPS key issues.
- Kept current behavior for genuine non-complaints (greetings/ads still ignored via prefilter + no keyword hit).
- Verified: with Gemini disabled, all 3 lift msgs + "No water" -> Complaint with tickets; greetings/ads correctly ignored. E2e via simulate endpoint created ticket TKT-260906-DF5AF.

## Switched LLM Gemini -> OpenAI (2026-06 update)
- User request: use OpenAI (model gpt-5.6-luna) instead of Gemini for message processing; prefilter must drop ONLY greeting messages (everything else goes to OpenAI to decide complaint-or-not).
- `backend/ai_engine.py`: `_call_llm` now prefers user's own OPENAI_API_KEY via official openai SDK (`_openai_native`, JSON mode, model from OPENAI_MODEL env, default gpt-5.6-luna); falls back to EMERGENT_LLM_KEY via emergentintegrations openai path (preview/Emergent env only). Removed `_gemini_native` and google.generativeai usage.
- `prefilter()`: drops only empty + pure greetings; removed AD_WORDS/FESTIVAL_WORDS/length gate. Ads/spam now judged by OpenAI.
- Health logging: "OpenAI OK/empty/failed" (never logs the key) for VPS diagnosis.
- Deterministic safety net (taxonomy/keyword override) retained as backstop.
- VPS config: `.env.vps` + DEPLOYMENT.md/DEPLOYMENT_VPS.md switched from GEMINI_API_KEY to OPENAI_API_KEY + OPENAI_MODEL=gpt-5.6-luna.
- Verified e2e via simulate endpoint: Hinglish lift/leak -> tickets created; greeting + ad -> ignored (ad decided by OpenAI). VPS action: set OPENAI_API_KEY, remove GEMINI_API_KEY, restart API+worker.

## Strict complaint classification prompt (2026-06 update)
- User: almost all messages were being marked as complaints. Wanted a message classified as a complaint ONLY if it clearly reports a specific issue/complaint under a provided list of ~180 society issue topics.
- `backend/ai_engine.py`: embedded the user's issue-topic list as `ISSUE_TOPICS` (de-duplicated) and rewrote `SYSTEM_PROMPT` to a strict classifier — Complaint only if the message describes a specific problem/fault/grievance in one of those topics AND reads like a report/complaint; greetings, questions, opinions, announcements, ads, acknowledgements, and vague mentions => NotComplaint (low confidence when unsure). Category is chosen from the topic list.
- Restricted the deterministic safety net: taxonomy/keyword override now fires ONLY when the LLM call FAILED (`_llm_ok` False). A successful "NotComplaint" from OpenAI is trusted and never overridden (was a second cause of over-classification).
- Verified e2e via simulate: lift stuck / no water / dead terrace light => tickets; AGM-time question, plumber-contact question, pool-open question, thanks, picnic chit-chat, gym poll, generic praise => ignored.
