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

## Excel Situation KB (2026-06 update)
- `Issues.xlsx` (500 situations, no header row: [#, Category, Sub-category, Situation, Priority, Time-window]) loaded into `backend/situations_kb.py`, cached at `backend/data/situations.json`.
- On a confident fuzzy match (threshold 0.6), the Excel category/sub-category/priority OVERRIDE the AI guess. Granular Excel category is mapped to the app's 11-category enum (`_CAT_MAP`) for vendor routing/analytics; raw Excel category kept in `kb_category`, sub-category in `sub_category`, matched text in `matched_situation`.
- Ticket schema now persists `sub_category`, `kb_category`, `matched_situation` (stored only; not shown in UI per user choice).
- Verified e2e via simulator: correct category/priority/sub_category + correct vendor auto-assignment. Backend-tested (agent).
