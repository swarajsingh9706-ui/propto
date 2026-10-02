from fastapi import APIRouter, HTTPException

from db import db
from models import ResidentCreate, now_iso

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/join/{token}")
async def join_info(token: str):
    soc = await db.societies.find_one({"form_token": token})
    if not soc:
        raise HTTPException(status_code=404, detail="This link is invalid or has expired.")
    return {"society_name": soc.get("name"), "city": soc.get("city") or "", "towers": soc.get("towers") or []}


@router.post("/join/{token}")
async def join_submit(token: str, body: ResidentCreate):
    soc = await db.societies.find_one({"form_token": token})
    if not soc:
        raise HTTPException(status_code=404, detail="This link is invalid or has expired.")
    if not body.name.strip() or not body.phone.strip():
        raise HTTPException(status_code=400, detail="Name and phone are required.")
    if await db.residents.find_one({"society_id": str(soc["_id"]), "phone": body.phone.strip()}):
        raise HTTPException(status_code=409, detail="This phone number is already registered for this society.")
    doc = body.model_dump()
    doc.update({
        "society_id": str(soc["_id"]), "created_at": now_iso(),
        "approval": "pending", "source": "form",
    })
    await db.residents.insert_one(doc)
    return {"status": "submitted", "society_name": soc.get("name")}
