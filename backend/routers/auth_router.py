from fastapi import APIRouter, HTTPException, Response, Depends
from bson import ObjectId
from datetime import datetime, timezone

from db import db
from models import LoginRequest
from auth_utils import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _public(user: dict) -> dict:
    society_name = None
    sid = user.get("society_id")
    if sid:
        try:
            s = await db.societies.find_one({"_id": ObjectId(sid)}, {"name": 1})
            society_name = (s or {}).get("name")
        except Exception:
            society_name = None
    return {
        "id": str(user["_id"]) if user.get("_id") else user.get("id"),
        "email": user["email"],
        "name": user.get("name", ""),
        "role": user["role"],
        "society_id": sid,
        "society_name": society_name,
    }


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(str(user["_id"]), email, user["role"])
    response.set_cookie("access_token", token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    return {"token": token, "user": await _public(user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"status": "ok"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return await _public(user)
