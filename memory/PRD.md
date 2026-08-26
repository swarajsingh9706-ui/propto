# PROPTO — Society Complaint & Ticket Management (PRD)

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
