# PROPTO — Society Complaint & Ticket Management (PRD)

## Bug fix (2026-06c) — Genuine "issue/problem" messages silently skipped
Short complaints like "water issue in my flat" were sometimes dropped because the LLM inconsistently returned NotComplaint, and the keyword/taxonomy safety-net only overrode when the LLM call *failed*. Fix (`ai_engine`): the deterministic override now forces a Complaint whenever a domain keyword / generic indicator ("issue", "problem", "broken", …) or a taxonomy match is present — even if the LLM succeeded — UNLESS the message is a resolved/positive update. Added `is_resolved_context()` (RESOLVED_WORDS like "resolved/fixed/sorted", cancelled by NEGATION_WORDS like "not/still/yet/unresolved") so "swimming pool issue is resolved" stays a non-complaint while "water issue still not resolved" creates a ticket. Verified via `tests/issue_keyword_probe.py`.


The previous dedup fix only helped when the AI parsed a flat. Real group complaints usually have NO flat (`Flat: —`), and `find_duplicate` returned `None` immediately when `flat` was empty, so EVERY reworded flatless message created a new ticket. Fixed `pipeline.find_duplicate`: when flat is present it scans same-flat Open/Pending tickets (category OR similarity); when flat is absent it scans the society's Open/Pending tickets from the last 48h and matches purely on wording similarity (`_looks_similar`). Verified via `tests/dedupe_probe.py` CASE3 (flatless reworded → duplicate) and CASE4 (flatless different issue → separate ticket), plus the earlier same-flat cases.


Root cause: `find_duplicate` required an EXACT category match. The AI/taxonomy classifies slightly reworded complaints into different categories (e.g. "No light in my flat" → Electrical vendor vs "No light in flat since yesterday" → Society Manager), so the exact-category check missed the duplicate and a second ticket was created.
Fix (`pipeline.find_duplicate`): among same-flat Open/Pending tickets, a report is now a duplicate when the category matches OR the complaint wording is substantially similar — content-word Jaccard ≥ 0.45 (grammatical stopwords removed; nouns like flat/light kept) OR `difflib` string ratio ≥ 0.82. Compares the new description against each candidate's description + raw_message (category names excluded so category drift doesn't dilute the match).
Verified via `tests/dedupe_probe.py`: "No electricity in the flat since yesterday" (different category) → duplicate; "No water in the flat" (same flat) → NOT duplicate; different flat → NOT duplicate. Duplicate path replies "This is already tracked under ticket <num>".

Previously the manager-only / "Handled By: Society Manager" branch in `create_ticket` immediately marked the ticket handled-in-house (no acceptance step), so it looked auto-accepted. Now that branch calls `escalate_to_committee(doc, after_priority=0, announce_group=False)` — the ticket is assigned to the Society Manager committee member with Accept/Reject buttons and a `response_due_at` timer; `committee_accepted` stays False until they actually accept. If not accepted within their acceptance window, `check_vendor_timeouts` escalates to the next member (Secretary → …). Added an `announce_group` flag to `escalate_to_committee` so the initial routing doesn't double-post to the group (the creation ack already states the assignee). Requires a committee member with role "Society Manager"; if the chain is empty it falls back to the "Society Manager — pending acceptance" label.
Verified via `tests/manager_routing_probe.py`: new manager ticket → status Pending, committee_role=Society Manager, committee_accepted=False, response_due_at set.

Root cause (found via live `journalctl`): Whapi sends interactive quick-reply ids prefixed with `ButtonsV3:` (e.g. `ButtonsV3:vendor_accept_<tid>`). `_handle_button` matched with `button_id.startswith("vendor_accept_")`, which failed because of the prefix, so NO branch ran — vendor/committee Accept/Reject/Resolve taps were silently ignored and ticket status never changed.
Fix (`routers/whatsapp_router._handle_button`): strip any leading `prefix:` (`button_id.split(":",1)[1]`) before matching. Verified end-to-end by POSTing a `ButtonsV3:`-prefixed reply payload to `/api/whapi/webhook/send` → `vendor_accepted=True`.
NOTE: on the VPS the `propto-worker` process must be restarted after deploy to load this fix (it imports `process_whapi` at startup).

Root cause: `process_whapi` skipped every non-group message when `role == "read"` (`if role == "read" and not group_chat_id: continue`). Vendor/committee Accept/Reject/Done DM replies that arrived on the reader account — or text-fallback replies when Whapi interactive buttons fail — were silently dropped, so ticket status never updated and escalation never fired.
Fix (`routers/whatsapp_router.py`): DM replies are now processed on BOTH reader and sender webhooks, de-duplicated by message id via a `wa_processed` collection (upsert `$setOnInsert`; skip if not newly inserted). Added logging in the button dispatch and `_handle_direct_reply`. Group AI pipeline still runs only on the reader; the sender's own group echoes are still ignored.
Verified with `tests/reject_routing_probe.py`: a "Reject" DM delivered via the reader webhook clears the vendor, escalates into the committee chain, and a duplicate (same id on the sender webhook) is skipped.

- Committee members now have **`priority`** (escalation order, nullable) and **`acceptance_time_hours`** (default 2). Shown in the Committee Add/Edit dialog for every role EXCEPT **Member**; displayed on each card. Committee page gained an **Edit** dialog (was add/delete only). Persisted by `society_router` committee POST/PUT.
- Default/effective priority (`pipeline._eff_priority`): Society Manager = 1, Secretary = 2 (or **1 when no Society Manager exists**); other roles have no default; Member never gets one. Admin can override with an explicit number.
- Escalation flow: when a **vendor doesn't accept** in its window (or rejects with no other vendor), the ticket escalates into the committee chain — **Society Manager first, then Secretary**, by priority. Each assignee has its own acceptance window; no accept in time → next member. Chain exhausted → "Society Manager" label needing manual action (`pipeline.escalate_to_committee`, `_committee_chain`).
- `pipeline.check_vendor_timeouts` now handles BOTH vendor and committee-member timeouts (driven by `POST /api/cron/vendor-timeouts`). Committee members get WhatsApp Accept/Reject buttons (`committee_accept_`/`committee_reject_`) and can reply DONE to resolve (`whatsapp_router._committee_action`).
- Verified via `tests/committee_chain_probe.py`: vendor→Manager→Secretary→exhausted, no-manager→Secretary=priority 1; plus committee API create with priority/acceptance.


## Feature (2026-06) — Self-service Change Password
- Top-right **Change Password** button added to the dashboard top header (`components/DashKit.jsx` `TopHeader`) — navigates to a dedicated page (not a popup).
- New page `pages/society/ChangePassword.jsx` at route `/change-password` (Protected): shows the logged-in user's **email (read-only, non-editable)**, **New password**, and **Confirm new password** fields.
- Backend `POST /api/auth/change-password` (authenticated via JWT `get_current_user`): validates min length 6 + new==confirm, hashes with existing bcrypt `hash_password`, updates `users.password_hash`. Added `ChangePasswordRequest` model. Per user request, the current password is NOT required.
- Verified via curl (mismatch→400, change→new login 200, restore original) and screenshot.

Added a `description` prop to the shared `PageHeader` (Layout.jsx) rendered under the title. Set per page: Assets "Manage all building assets and track maintenance"; Vendors "Manage vendors to automatically assign the tickets"; Residents "Manage all residents and their details" (+ amber banner "{n} resident(s) awaiting verification — Review and approve or reject…" shown only when pending > 0); Society Committee "Manage committee members used for escalation alerts"; Reports "Monthly performance data"; Resident Suggestions "Community suggestions with live voting"; Notifications "Stay updated with important alerts"; Audit Log "Track record of every action"; Escalated Tickets "Tickets that need your manual assignment".

- **Removed "Suggest Time"** vendor button — vendors now get only **Accept** / **Reject** (pipeline `assign_vendor`). Dropped the `vendor_time_` button handler and the `awaiting_vendor_time` direct-reply branch.
- **On Accept** (`whatsapp_router._vendor_action`): vendor gets a confirmation DM with the complaint raiser's **name, phone, flat, society name** and the issue text; the **customer** is sent the vendor's contact (name + phone) personally.
- **On Reject**: vendor gets a decline confirmation; ticket reassigns to the next available vendor by priority; if none exist it is assigned to the **Society Manager**. Group is notified.
- **On Resolve/close**: the resolved confirmation now goes to the **society WhatsApp group** (quoting the original complaint) instead of a personal DM.
- **Vendor response time**: new `response_time_hours` field on vendors (default **2**), editable in Add + Edit vendor dialogs (`Vendors.jsx`), shown on the vendor card. `assign_vendor` stamps `vendor_assigned_at` + `response_due_at`.
- **Timeout → Society Manager**: `pipeline.check_vendor_timeouts()` reassigns any Pending, un-accepted ticket whose `response_due_at` has passed to the Society Manager (notifies group + the lapsed vendor). Exposed via protected `POST /api/cron/vendor-timeouts`.
  - **VPS setup required**: add a system cron (e.g. every 5 min) calling `POST /api/cron/vendor-timeouts` with `Authorization: Bearer $WEBHOOK_CRON_SECRET` — same pattern as `/api/cron/asset-alerts`. Without this cron the timeout reassignment won't fire automatically.
- Verified via API (vendor create default 2 / custom 3) and an integration probe (`tests/vendor_flow_probe.py`) covering accept, reject(+reassign), resolve, and timeout DB state transitions.

Replaced the Assets "Escalation Matrix" button + popup with an inline **Escalation Matrix** tab (3rd tab after All Assets / Asset Tickets) styled to match the uploaded `Propto_Admin_Dashboard Analytics.html` design.
- `components/EscalationMatrix.jsx`: legend bar (Health / Service Status), header with bell + "Add Contact", left **Notification Timeline** of 4 colored rule cards (blue Pre-service 7d before, amber Final 1d before, red Overdue 2d after, purple Critical 7d after) each with a pencil edit; right **Committee Contacts** list (colored initials avatar, role, phone, edit/delete) + "How it works" box.
- Backend (`society_router.py`): `GET/PUT /api/society/escalation-timeline` stores `escalation_timeline` on the society (4 rule objects: key, offset_days, direction, timing, title, description, notify[], channel, color) with `DEFAULT_TIMELINE` matching the design; added `PUT /api/society/committee/{cid}` to edit a committee member (edit was previously only add/delete).
- Edit-rule dialog: timing label, days offset + before/after, title, description, and Notify toggles (Secretary/Vendor/Chairman/Manager). Add/Edit contact dialog writes to the committee collection.
- Old `/escalation-matrix` endpoint retained (unused by UI). NOTE: `asset_alerts.py` still fires a single on/after-due alert and does not yet consume the new day-offset timeline rules — timeline is configured/persisted but alert scheduling is unchanged.
- Verified: backend GET defaults, POST/PUT committee, PUT timeline via curl; screenshot of the inline tab matches the design.

Each ticket's group/DM acknowledgement appends `📋 View ticket details: {PUBLIC_APP_URL}/t/{ticket_number}` (base from backend env `PUBLIC_APP_URL` = `https://manage.propto.app`). The public page is keyed by the **ticket number** (short, meaningful URL — no separate token).
- Public, no-login endpoints in `public_router.py` (keyed by `ticket_number`):
  - `GET /api/public/ticket/{num}` — core fields; `assigned_to` prefers `vendor_name` then `assigned_to` (fixes stale display after reassign).
  - `GET /api/public/ticket/{num}/categories` — categories with active vendors.
  - `POST /api/public/ticket/{num}/cancel` — Cancelled, notify group + vendor; 400 if already Cancelled/Resolved.
  - `POST /api/public/ticket/{num}/reassign` — `{target:"vendor",category}` → top-priority vendor (also syncs `assigned_to`); `{target:"manager"}` → Society Manager. Notifies group + previous vendor; 400 if Cancelled/Resolved.
- Frontend page `/t/:token` (`pages/public/TicketView.jsx`, unauthenticated route in `App.js`): branded card, status/priority badges, core fields, Reassign / Assign-to-Manager / Cancel with confirm dialogs; actions hidden when Cancelled/Resolved.
- `PublicReassign` model added; `reassigned` added to `_BOT_MARKERS`.
- NOTE: production `manage.propto.app` must be rebuilt/redeployed (new route + backend endpoints) and nginx needs SPA fallback (`try_files $uri /index.html`) or the link redirects to login on the stale build.
- Verified via curl (view/categories/reassign-vendor/reassign-manager/cancel + 400/404) and screenshots (active, cancelled, manager-assigned states).



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

## Tickets page filter/column enhancements (2026-06 update)
- `backend/routers/society_router.py` GET /society/tickets: added `priority` query param filter (in addition to status/category/search).
- `frontend/src/pages/society/Tickets.jsx`:
  - Added "High Priority" toggle button (Flame icon) -> filters priority=High.
  - Added "Closed" to status options in both the dropdown and pills (STATUSES const).
  - Status + Category now available as clickable pill rows AND the existing dropdowns (shared state, either works).
  - Table: added Resident (resident_name) and Date & Time (created_at, fmtDT) columns; removed the Source column.
- Verified: backend priority=High (10) / status=Closed (0) via curl; UI screenshots confirm pills, High Priority active state, resident + date columns.

## Society Admin batch: assign/priority/filters/dates + taxonomy update (2026-06)
1. Tickets: vendor assign now requires clicking an Assign/Reassign button (pendingVendor state; assign-vendor-confirm testid) instead of assigning on dropdown select.
2. Vendors: per-category assignment priority (1 = gets ticket first). Vendor doc stores `priorities:{category:int}`; UI number input per category (onBlur save). `pipeline.pick_vendor` sorts by priorities[category] asc then load; missing/<=0 -> 999 sentinel. models VendorCreate/Update gained `priorities`.
3. Residents: added search bar (name/flat/tower/phone) + All/Owner/Tenant filter buttons (client-side).
4. Audit Log: each row shows exact date & time (fmtDT) + relative time.
5. Reports: "Category-wise" recharts replaced with ranked "Top Issue Categories" horizontal bars (matches SuperDashboard/HTML reference style).
6. Suggestions: each card shows exact date & time (created_at).
7. Taxonomy: replaced with Propto_Updated_Taxonomy (3).xlsx -> rebuilt data/taxonomy.json = 16,157 items (4,736 vendor-routed / 11,421 in-house). situations_kb._XLSX updated to new URL. Backend restarted to reload cache. Match verified (electricity/leakage score 1.0).
- Verified: testing agent iteration_8.json — 100% (7/7 frontend, backend 6 passed/1 skipped). No tenant in seed data so Tenant filter shows empty (not a bug).

## Mobile/tablet responsiveness (2026-06)
- Root cause: sidebar was `fixed w-60` with `main ml-60` (always-on), pushing content off-screen on mobile with no way to reach the nav.
- `components/Layout.jsx`: sidebar is now a slide-in drawer (`-translate-x-full` on mobile, `lg:translate-x-0`) with overlay + close (X); added a `lg:hidden` sticky top bar with hamburger (data-testid=sidebar-toggle) + logo; main is `lg:ml-60` (no left margin on mobile); NavLink closes drawer on tap. PageHeader title now `text-2xl sm:text-3xl` and actions wrap.
- `components/DashKit.jsx` TopHeader: responsive padding (`px-4 sm:px-7`), wraps, smaller text on mobile.
- Dashboard & SuperDashboard: main container `flex-col ... xl:flex-row`, right rail now `w-full ... xl:w-[300px]` (was hidden), fixed-grid tables wrapped in `overflow-x-auto` + min-width so they scroll instead of clipping.
- Table pages (Tickets/Residents/Reports): wrappers changed `overflow-hidden`->`overflow-x-auto` with table `min-w-[...]`; page containers `p-8`->`p-4 sm:p-6 lg:p-8` across all society + super pages.
- Verified via screenshots at 390px (mobile) and 768px (tablet): drawer toggle, nav, stacking, and table scroll all work. Login page was already responsive (unchanged).

- 2026-06: Taxonomy re-updated with newly uploaded Propto_Updated_Taxonomy (3).xlsx (16,157 items; 4,736 vendor-routed / 11,421 in-house). situations_kb._XLSX URL updated, cache rebuilt, backend restarted. Match verified.

## Resident self-registration form + approval workflow (2026-06)
- Public form: new route /join/{token} (frontend `pages/public/Join.jsx`, outside auth) with the same fields as Add Resident (name, phone, flat, tower, Owner/Tenant). Backend `routers/public_router.py`: GET /api/public/join/{token} (society info), POST (creates resident approval=pending, source=form).
- Per-society token: society doc gains `form_token`; GET /api/society/form-link generates/returns it. Residents page shows a shareable link banner (`${origin}/join/{token}`) with Copy.
- Residents page now has two tabs: Active Residents (approval!=pending → approved/manual/import) and Pending Residents (form submissions), with counts + 'Via Form'/'Imported'/'Added' source badges.
- Pending rows: Accept → POST /api/society/residents/{id}/approve (sets approval=active, fetches Whapi group invite link via whatsapp_client.get_group_invite_link and sends it to the resident's phone; best-effort). Reject → DELETE (removes record).
- whatsapp_client.get_group_invite_link(group_id): GET /groups/{id}/invite -> https://chat.whatsapp.com/{invite_code}; returns '' if Whapi/group not configured.
- create_resident/import now set approval=active + source. Legacy residents (no approval) treated as Active.
- Verified: backend e2e via curl (form-link→public GET/POST→pending→approve, invite skipped as Whapi not connected in preview); frontend testing agent iteration_9 = 100%, no bugs. NOTE: Emergent external gateway takes ~30-60s to route brand-new API paths after adding them.

## Two Whapi accounts: split read vs send + dual webhooks (2026-06)
- User has 2 Whapi accounts: one to READ group messages, one to SEND. Group→society assignment linked to the reader.
- Env: WHAPI_TOKEN_READ (monitoring account), WHAPI_TOKEN_SEND (sending account); both fall back to legacy WHAPI_TOKEN. WHAPI_BASE shared. Added to backend/.env.vps template.
- whatsapp_client.py: added _read_token()/_send_token(); whapi_configured(role). Sending (send_text/send_buttons/send_poll, _whapi_post default) uses SEND token. Reading (list_groups, get_group_invite_link, check_connection) uses READ token. get_poll_results uses SEND token (poll owned by sender).
- whatsapp_router.py: three routes — /api/whapi/webhook/read, /api/whapi/webhook/send, and legacy /api/whapi/webhook (alias of read). process_whapi(payload, method, role) role-gates: read handles only group text -> pipeline (+society match); send handles poll votes + 1:1 vendor/resident replies + buttons; each ignores the other's events. worker.py passes job role.
- Frontend WhatsApp.jsx shows both reader & sender webhook URLs (data-testid whapi-webhook-read / whapi-webhook-send).
- Verified via curl + logs: read webhook ran group pipeline path; send webhook ignored group chatter; token role resolution OK. VPS: set WHAPI_TOKEN_READ + WHAPI_TOKEN_SEND, point reader Whapi channel to /read and sender channel to /send, restart API + worker.

## Complaint acknowledgements -> personal chat (2026-06)
- Change: for group-originated messages, the ticket acknowledgement / duplicate notice / low-confidence "team will review" reply are now sent to the complainant's PERSONAL chat (their phone) instead of into the group, for a cleaner group.
- `pipeline.py` process_message: replaced group `reply_target`/`quote` with `ack_target = phone`; create_ticket called with notify_to=phone, notify_reply_to=None; duplicate + low-confidence replies DM the person. Vendor job messages unchanged.
- Verified via /api/whapi/webhook/read with a mapped group: log shows send_text target = personal number (919812345678), not the group chat_id (delivery best-effort; failed only because preview Whapi token is a placeholder).

## Escalated Tickets page aligned with Tickets tab (2026-06)
- Rewrote `frontend/src/pages/society/Escalated.jsx` to mirror the Tickets page.
- Added vendor-assignment popup: clicking a row or the Assign button opens the same Sheet (vendor select + Assign/Reassign confirm button, Pending/Resolve actions, description, original message, timeline) using /society/tickets/:id, /assign, PUT status, /close.
- Added filters like Tickets: search (ticket/flat/resident/vendor/category), High Priority toggle, Category dropdown + pills (client-side over /society/tickets/escalated).
- Table now shows all Tickets fields incl. previously missing Vendor and Date & Time, plus Escalation Reason + Action.
- Verified via screenshot: 13 escalated rows, filters render, assignment popup opens with vendor dropdown. Frontend compiled clean.

## Fix: Tickets table double-flicker on open (2026-06)
- Cause: Tickets.jsx had two useEffects each firing load() on mount (filter effect + search effect), amplified by React StrictMode dev double-invoke -> 3 fetches on open.
- Fix: consolidated into ONE debounced effect over [status, category, priority, search] with a clearTimeout cleanup, so StrictMode's double-invoke collapses to a single fetch (search debounced 400ms, filters immediate).
- Verified via network capture: exactly 1 tickets-list fetch on open (was 3). No flicker.

## Revert ack to group + taxonomy update (2026-06)
- Reverted pipeline.py process_message: group acknowledgements/duplicate/low-confidence replies go back INTO the group (reply_target=group_chat_id, quoting original) instead of the complainant's personal chat.
- Taxonomy updated to Propto_Taxonomy_Corrected.xlsx -> data/taxonomy.json rebuilt = 16,049 items (4,619 vendor-routed / 11,430 in-house). situations_kb._XLSX updated. Backend restarted. Match verified (electricity 1.0, lift/water good).

## Vendor tab: add-time priority w/ cascade, category grouping, country codes, colored tags (2026-06)
- Backend create_vendor (society_router.py): for each selected category, if an explicit priority is given, shift existing vendors in that category with priority>=N by +1 (insert-and-cascade); if blank, append at max+1. Verified: inserting at 2 -> old 2->3, 3->4.
- Vendors.jsx rewritten: vendors grouped into sections per category (sorted by that category's priority, rank circle shown); colored category tags via CATEGORY_COLORS; Add dialog now has a country-code dropdown (COUNTRY_CODES, default India +91) + separate number field (phone submitted as dial+digits) and a per-category priority input.
- Verified: frontend compiles, grouped UI + colored tags + India-default dropdown render (screenshots); cascade shift via API. Test vendors cleaned up.

## Dashboard batch: notifications, date ranges, suggestion fixes, resident edit (2026-06)
- Residents: added Edit dialog (Pencil icon per active row) -> PUT /society/residents/:id. Testids edit-resident-*, save-edit-resident-btn.
- Reports: DateRangeFilter (All/This Week/This Month/This Year/Custom) -> /society/reports?start&end. Backend filters tickets by created_at range; daily series + vendor performance now range-aware.
- Audit Log: DateRangeFilter -> /society/audit?start&end (created_at range filter).
- AI Activity: log panel restyled to dark grey (bg-zinc-900 / light text) for readability + DateRangeFilter -> /society/ai/activity?start&end (logs+stats range-aware). Removed obsolete color.
- Suggestions:
  - Categories expanded (Electricity, Water Supply, Plumbing, Lift/Elevator, Cleaning, Waste Management, Gardening/Landscaping, Safety, etc).
  - Admin vote is now a single toggle (voters key "admin_panel"): click Yes -> select (+1); click again -> deselect (-1); click No -> switch. Endpoint returns admin_vote; list returns admin_vote per suggestion; buttons highlight selection. Verified via curl (yes->16, yes again->15/null, no->switch).
  - Group polls captured: a poll created BY a resident inside the WhatsApp group now auto-creates a suggestion (source="group_poll") on the reader webhook, with generic option bars + counts synced. Verified by posting fake Whapi poll payloads to /api/whapi/webhook/read (multi-option + yes/no both captured).
- Notifications: new tab (Bell icon) + sidebar unread badge. Backend routers/notifications_router.py derives from overdue tickets, escalated tickets, assets due-soon/overdue, new suggestions (14d), pending resident approvals. Endpoints GET /society/notifications, GET /society/notifications/unread-count, POST /society/notifications/read {ids|all}; read state persisted in notification_reads collection.
- Removed Review Queue nav item + route (ReviewQueue.jsx and backend review-queue endpoints left intact, just unlinked).
- ENV NOTE: preview frontend REACT_APP_BACKEND_URL=api.propto.app is the DEPLOYED prod (old code); new endpoints verified against local backend only. Redeploy required to sync frontend+backend and run full UI e2e.

## Fixes: vendor dup-priority, resident/committee country codes, admin vote delta (2026-06)
- Vendor priority: added _cascade_priorities() in society_router.py; update_vendor now cascades (insert-at-N, exclude self) so inline priority edits can no longer create duplicate priorities within a society/category. create_vendor refactored to reuse helper. Verified: editing A(1) -> 2 shifts B(2)->3, C(3)->4, all unique.
- Residents: phone now uses a country-code dropdown (default India +91) on both Add and Edit dialogs; stored as dial+digits; edit splits existing phone via lib/countryCodes.splitPhone.
- Committee: phone now uses the same country-code dropdown on Add dialog.
- Shared lib/countryCodes.js (COUNTRY_CODES + splitPhone).
- Suggestion admin vote: no longer recomputes from voters (which reset WhatsApp-synced counts to 1). Now applies a +1/-1 DELTA on top of existing yes/no counts, tracked in doc.admin_vote; toggle select/deselect/switch. _apply_poll_results re-adds the admin delta on WhatsApp sync so the dashboard vote persists. Verified: base yes=50 -> vote yes=51 -> deselect=50 -> vote no=11 (no reset).

## Perf: instant vendor assign (2026-06)
- pipeline.assign_vendor() was blocking on await wa.send_buttons() (Whapi HTTP, 4-5s, worse on token timeout). DB update/timeline/audit are instant; the WhatsApp send now runs fire-and-forget via _fire() helper (asyncio.create_task with error logging; inline fallback when no loop). POST /society/tickets/:id/assign now returns in ~0.1s. Affects both Tickets and Escalated assignment sidebars (shared endpoint).

## Assets overhaul + sidebar/dashboard/escalated/vendor edits (2026-06)
SIDEBAR (Layout.jsx): re-styled to match HTML reference — order Dashboard, Tickets, Escalated Queue, Assignment Logic, Assets, Vendors, Residents, Society Committee, Analytics, Resident Suggestions, AI Activity, Notifications, Audit Log; icons updated (HardHat vendors, Lightbulb suggestions). Announcements intentionally skipped.
VENDORS: added Edit dialog (name, phone+country code, categories, priorities, avail/active) -> PUT /society/vendors/:id.
ESCALATED: added Status filter (All/Escalated/Open/Pending) alongside category/priority.
DASHBOARD: wired real data — Assets summary count, Upcoming Maintenance table (from assets by next_service), Alerts (escalated tickets + asset due/overdue). Escalated stat + list now use broad query (status Escalated OR past-SLA Open/Pending) so they populate. Backend /society/dashboard returns stats.assets + maintenance[].
ASSETS (full rebuild): 
  - Tabs: All Assets | Asset Tickets (tickets with asset_id).
  - Row actions dropdown: View Details, Edit, Mark Service Done, Schedule Service, Raise Ticket, Delete.
  - Service frequency: Monthly/Two Months/Three Months/Six Months/Yearly. Mark-service-done auto-computes next_service = date + frequency (backend _add_months).
  - Dynamic COMPUTED status (backend _asset_status): Overdue (past), Due Soon (<=7d), Scheduled (future), Unscheduled/"Not Scheduled" (no date). Not stored.
  - Raise Ticket -> creates Open asset-ticket (manual assign), source="asset".
  - Escalation Matrix (society-level, GET/PUT /society/escalation-matrix): ordered committee contacts + wait_minutes. Used by asset service alerts.
AUTOMATED ALERTS: backend asset_alerts.run_asset_alerts() + POST /api/cron/asset-alerts (Bearer WEBHOOK_CRON_SECRET). Cron .emergent/crons.yml daily 09:00 Asia/Kolkata. Recipients = asset vendor + escalation matrix; if matrix empty -> vendor + Society Manager (committee Secretary/Manager/Chairman). Deduped via asset.last_alert_date == next_service. Verified: cron ran "1 message". Real WhatsApp delivery only on live VPS with valid Whapi tokens.
NEW ENV: WEBHOOK_CRON_SECRET in backend/.env.
ENV NOTE: preview frontend REACT_APP_BACKEND_URL=api.propto.app is the deployed prod (OLD code, 404s new endpoints). All new code verified on local backend via curl; frontend compiles. Redeploy required for full UI e2e + live cron.

## WhatsApp ticket cancellation via reply "CANCEL" (2026-06)
- Residents/manager can cancel a ticket by REPLYING (swipe/hold-reply, quoting) to either the original complaint OR PROPTO's acknowledgement, sending exactly "CANCEL" (uppercase).
- Parsing: whatsapp_client.parse_whapi_inbound now captures context.quoted_id per message.
- Ticket now stores reporter_phone, source_message_id (original group msg id), ack_message_id (id of PROPTO's ack, extracted via _extract_msg_id from send_text response).
- Handler routers/whatsapp_router._handle_cancel: matches ticket by quoted_id (source_message_id OR ack_message_id); AUTH = creator (reporter_phone last-10 match) OR society manager (committee role Secretary/Manager/Chairman, phone match); others get "Only the resident who raised this ticket or the society manager can cancel it." Sets status=Cancelled + cancelled_by, timeline, audit; replies "❌ Ticket X has been *cancelled* as requested.". Already-cancelled/resolved handled.
- Cancel/rejection phrases added to _BOT_MARKERS so they aren't re-ingested (no loop).
- Verified via reader webhook: unauthorized rejected (stayed Open); creator via ack msg -> Cancelled(resident); manager via original msg -> Cancelled(Society Manager); audit+timeline written.
- NOTE: requires a real WhatsApp *reply* (quote); a plain "CANCEL" without quoting does nothing. Live delivery needs Whapi tokens on VPS.

## CANCEL robustness fix (2026-06)
- Confirmed Whapi uses context.quoted_id (correct). Root cause of "no effect": old tickets had no source_message_id/ack_message_id, so id-match failed silently.
- Added fallback: capture context.quoted_content.body (quoted_body); if id match fails, extract TKT-YYMMDD-XXXXX from the quoted ack text and match by ticket_number -> works for ANY ticket when replying to the acknowledgement.
- Added logging: parsed msgs now log quoted_id + text preview; _handle_cancel logs "CANCEL from=.. quoted_id=.. -> ticket=..".
- Verified: reply-to-ack with unmatched id but ticket number in body -> ticket Cancelled.
- Reminder: replying to the ORIGINAL complaint only matches NEW tickets (source_message_id); replying to the ACK works for all. Requires production redeploy.

## Dashboard escalated redirect + manager-only routing toggle (2026-06)
- Dashboard: escalated panel "View all" and per-row "Assign Now" now navigate to /escalated (was /tickets).
- Society-level flag manager_only_routing (default TRUE). New societies created with it True (super_router). pipeline.create_ticket: if flag on, forces in-house branch -> assigned_to "Society Manager", no vendor pick, ack says handled in-house. When off, normal vendor auto-routing by category/priority.
- Endpoints: GET/PUT /api/society/routing-mode {manager_only_routing}. Audited as routing_mode_changed.
- Vendors tab: highlighted pill toggle in header ("All → Society Manager: ON" amber / "Vendor Routing: ON" green) + amber banner when on. Fetches + PUTs routing-mode. Enabled by default.
- Missing flag on existing societies defaults to True (enabled).
- Verified: endpoints GET/PUT; pipeline branch routes to manager when on. Requires redeploy for prod.

## Super/society batch + login cleanup + Reports PDF (2026-06)
- Login: removed demo-credential buttons + cross-portal redirect links from SocietyLogin.jsx & SuperAdminLogin.jsx.
- Super WhatsApp (SuperWhatsApp.jsx): replaced society dropdown with search + city filter (card picker). Monitoring OFF now blocks ticket creation — pipeline.process_message early-returns "ignored (monitoring disabled)" but still logs ai_activity. Verified.
- Super Societies: search bar + city filter; Edit Society dialog (name/city/address/towers + update admin email & password); removed Power activate/deactivate button. Backend super_router.update_society handles admin_email/admin_password (SocietyUpdate model extended; hashes pw, updates/creates linked society_admin user).
- Resident public form (Join.jsx): country-code dropdown (India default) + combined phone; public_router rejects duplicate phone within the SAME society (HTTP 409 -> toast).
- Reports: "Share to WhatsApp" -> POST /api/society/reports/share-pdf {sections,start,end}. reportlab builds a branded (PROPTO blue) PDF of selected sections (summary/daily/categories/resolution/vendors) respecting date range; sent to society group via wa.send_document (sender token). Verified PDF build; group send works with live Whapi on VPS (simulated in preview). reportlab==5.0.1 added to requirements.txt.
- UI: darkened --secondary token (210 40% 96% -> 210 24% 90%) so tab hovers / faint grey surfaces are more visible.
- NOTE: redeploy required; group PDF delivery needs valid Whapi sender token.

## Complaint detection + keyword category routing (2026-10-13)
- Fixed over-ticketing: removed the taxonomy/keyword override that forced tickets for "working on it rn"-style messages.
- `ai_engine.decide_intent`: AI decides. Resolved updates and status replies are always ignored. Keywords only rescue a ticket when the AI fails or is unsure (certainty < 0.75), and then only if the message has BOTH a topic word and a problem word.
- Category/vendor: word-boundary topic keywords decide the app category (power/electricity/light/fan → Electrical, water/leak/tap → Plumbing, etc.). The taxonomy only enriches sub-category/priority/handled_by when its app_category agrees with that category; otherwise CATEGORY_VENDOR sets the vendor role.
- Prompt now includes status-reply and complaint examples, and returns `certainty`.
- `tests/issue_keyword_probe.py` (25 phrases, simulated + `--live`): 0 failures locally.
- PENDING: deploy to VPS + restart API and worker, then verify with live WhatsApp.


## Taxonomy v3.2 (object + problem) replaces old taxonomy (2026-10-13)
- Source: `backend/data/Propto_Issue_Taxonomy_v3_2.xlsx` → `data/taxonomy_v3.json` (rebuild: `python3 tests/build_taxonomy_v3.py`).
- `backend/taxonomy_v3.py`: safety override → shortcut phrase → object+problem (Line Map; Subject > Equipment > Place, then category priority, then distance) → problem only → object only. Location is recorded only.
- Tickets now store the v3 category, short label (sub_category), issue_id, severity, SLA target, propto_action and location. `routing_category` maps v3 → old 11 vendor categories (user choice). Water Supply falls back to a Plumbing vendor. "Manager Alert" lines WhatsApp the top committee member when a vendor is assigned.
- AI still decides complaint-or-not. Safety words force a complaint. "still not resolved"/"again" follow-ups with a taxonomy signal are complaints.
- Tickets filter matches category OR routing_category. The detail sheet shows the Issue and Location rows.
- Tests: taxonomy sheet 171/172 (same as the sheet's own result), issue_keyword_probe 0 failures (live), testing agent iteration_10: 100%.
- PENDING: deploy to VPS and restart API + worker. `situations_kb.py`/the old taxonomy.json are no longer used for classification.

## Duplicate detection scoped to same flat / same reporter (2026-10-13)
- `pipeline.find_duplicate(..., phone)`: a duplicate needs an Open/Pending ticket (last 7 days) from the SAME flat (AI flat, else resident flat) or the SAME reporter (reporter_phone / linked_reporters), plus the same category or similar wording.
- Same or similar complaints from a different flat or resident now always create a new ticket. Same flat with a different resident is linked (user choice).
- `tests/dedupe_probe.py`: 7 cases, 0 failures. PENDING: deploy `pipeline.py` and restart API + worker.

## Pool AMC Vendor routing + no-vendor fallback (2026-10-13)
- Swimming Pool (taxonomy v3) and pool keywords now route to the "Pool AMC Vendor" vendor category (already in the Vendors form; added to db.COMPLAINT_CATEGORIES and the Tickets/Escalated/ReviewQueue filters).
- Any category with no matching vendor now goes to the committee escalation chain (Society Manager first if it has top priority), instead of waiting unassigned.
- Vendor rejection reassignment now uses the ticket's routing_category.
- `tests/pool_routing_probe.py`: 0 failures. PENDING: deploy + restart API/worker.



