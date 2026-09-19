from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / '.env')

import os
import asyncio
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from db import db, COMPLAINT_CATEGORIES
from auth_utils import hash_password, verify_password
from models import now_iso

from routers.auth_router import router as auth_router
from routers.super_router import router as super_router
from routers.society_router import router as society_router
from routers.ai_router import router as ai_router
from routers.whatsapp_router import router as whatsapp_router
from routers.reports_router import router as reports_router
from routers.suggestions_router import router as suggestions_router
from routers.public_router import router as public_router
from routers.notifications_router import router as notifications_router
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("propto")

app = FastAPI(title="PROPTO API")


@app.get("/api/")
async def root():
    return {"message": "PROPTO API", "status": "ok"}


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


app.include_router(auth_router)
app.include_router(super_router)
app.include_router(society_router)
app.include_router(ai_router)
app.include_router(whatsapp_router)
app.include_router(reports_router)
app.include_router(suggestions_router)
app.include_router(public_router)
app.include_router(notifications_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


async def seed_super_admin():
    email = os.environ.get("ADMIN_EMAIL", "superadmin@propto.com").lower()
    password = os.environ.get("ADMIN_PASSWORD", "Propto@123")
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({
            "email": email, "password_hash": hash_password(password),
            "name": "Super Admin", "role": "super_admin", "created_at": now_iso(),
        })
        logger.info("Seeded super admin %s", email)
    elif not verify_password(password, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})


async def seed_demo():
    if await db.societies.find_one({"code": "GRNVLY"}):
        return
    # Society
    res = await db.societies.insert_one({
        "name": "Green Valley Residency", "code": "GRNVLY",
        "address": "Sector 21, Whitefield", "city": "Bangalore",
        "towers": ["A", "B", "C"], "active": True,
        "whatsapp_group": {"group_name": "Green Valley Residents", "group_id": "GV-GROUP-001", "phone_number_id": os.environ.get("WHATSAPP_PHONE_ID", "")},
        "monitoring": True, "created_at": now_iso(),
    })
    sid = str(res.inserted_id)
    # Society admin
    if not await db.users.find_one({"email": "admin@greenvalley.com"}):
        await db.users.insert_one({
            "email": "admin@greenvalley.com", "password_hash": hash_password("Admin@123"),
            "name": "Rahul Mehta", "role": "society_admin", "society_id": sid, "created_at": now_iso(),
        })
    # Vendors
    vendors = [
        {"name": "AquaFix Plumbing", "phone": "919000000001", "categories": ["Plumbing", "Water Supply"]},
        {"name": "PowerLine Electricals", "phone": "919000000002", "categories": ["Electrical", "DG Set"]},
        {"name": "LiftCare Services", "phone": "919000000003", "categories": ["Lift"]},
        {"name": "CleanPro Housekeeping", "phone": "919000000004", "categories": ["Housekeeping", "Gardening", "Pest Control"]},
        {"name": "BuildRight Civil", "phone": "919000000005", "categories": ["Civil", "Parking", "Security"]},
    ]
    for v in vendors:
        await db.vendors.insert_one({**v, "availability": True, "active": True, "society_id": sid, "created_at": now_iso()})
    # Residents
    residents = [
        {"name": "Anita Sharma", "phone": "918111111101", "flat": "A101", "tower": "A"},
        {"name": "Vikram Rao", "phone": "918111111102", "flat": "B302", "tower": "B"},
        {"name": "Priya Nair", "phone": "918111111103", "flat": "C204", "tower": "C"},
        {"name": "Sunil Kumar", "phone": "918111111104", "flat": "A305", "tower": "A"},
    ]
    for r in residents:
        await db.residents.insert_one({**r, "society_id": sid, "created_at": now_iso()})
    logger.info("Seeded demo society %s", sid)


async def seed_suggestions():
    soc = await db.societies.find_one({"code": "GRNVLY"})
    if not soc:
        return
    sid = str(soc["_id"])
    if await db.suggestions.count_documents({"society_id": sid}) > 0:
        return
    samples = [
        ("We should install a borewell of our own", "Infrastructure", "Mrs. Sharma", "B-1204", "Under Review", 58, 12),
        ("Add CCTV cameras in the parking area", "Security", "Mr. Patil", "A-0802", "Approved", 41, 6),
        ("Start a weekly cleaning drive for common areas", "Maintenance", "Mrs. Iyer", "C-1105", "Under Review", 29, 18),
        ("Set up a children's play area in the garden", "Amenities", "Mr. Rao", "A-0305", "Pending", 22, 9),
        ("Ban loud music after 10 PM", "Community", "Mrs. Nair", "C-0204", "Declined", 15, 33),
    ]
    for title, cat, who, flat, status, yes, no in samples:
        voters = {f"y{i}": "yes" for i in range(yes)}
        voters.update({f"n{i}": "no" for i in range(no)})
        await db.suggestions.insert_one({
            "society_id": sid, "title": title, "category": cat, "author_name": who, "flat": flat,
            "status": status, "voters": voters, "yes_votes": yes, "no_votes": no,
            "poll_posted": True, "created_at": now_iso(), "updated_at": now_iso(),
        })
    logger.info("Seeded demo suggestions")


async def write_credentials():
    # Dev-only helper (used inside the Emergent workspace). Skip silently off-platform.
    memory_dir = Path("/app/memory")
    if not memory_dir.is_dir():
        return
    path = memory_dir / "test_credentials.md"
    content = f"""# Test Credentials

## Super Admin
- Email: {os.environ.get('ADMIN_EMAIL', 'superadmin@propto.com')}
- Password: {os.environ.get('ADMIN_PASSWORD', 'Propto@123')}
- Role: super_admin

## Society Admin (demo: Green Valley Residency)
- Email: admin@greenvalley.com
- Password: Admin@123
- Role: society_admin

## Auth endpoints
- POST /api/auth/login  {{email, password}} -> {{token, user}}
- GET  /api/auth/me  (Authorization: Bearer <token>)
- POST /api/auth/logout

## Notes
- Frontend sends JWT as `Authorization: Bearer <token>` (stored in localStorage).
- WhatsApp simulator: POST /api/society/whatsapp/simulate {{phone, text}} runs full AI pipeline.
- Demo resident phones: 918111111101 (A101), 918111111102 (B302), 918111111103 (C204).
"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    except Exception as e:
        logger.warning("could not write credentials: %s", e)


async def _seed_all():
    try:
        await db.users.create_index("email", unique=True)
        await db.tickets.create_index("society_id")
        await db.vendors.create_index("society_id")
        await db.residents.create_index("society_id")
        await db.audit_logs.create_index("society_id")
        await seed_super_admin()
        await seed_demo()
        await seed_suggestions()
        await write_credentials()
    except Exception as e:
        logger.exception("startup seeding failed (app will still serve): %s", e)


@app.on_event("startup")
async def startup():
    # Fire-and-forget: serving must NEVER block on DB/seeding. Under a2wsgi/Passenger
    # a blocking startup (e.g. slow Atlas) would hang every request (ESOCKETTIMEDOUT).
    # Keep a reference so the task can't be garbage-collected mid-run.
    app.state._seed_task = asyncio.create_task(_seed_all())


@app.on_event("shutdown")
async def shutdown():
    pass
