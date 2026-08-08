import os
import re
import hmac
import hashlib
import logging
import httpx

logger = logging.getLogger("propto.whatsapp")

GRAPH_URL = "https://graph.facebook.com/v19.0"


def whapi_base() -> str:
    return os.environ.get("WHAPI_BASE", "https://gate.whapi.cloud").rstrip("/")


def whapi_configured() -> bool:
    return bool(os.environ.get("WHAPI_TOKEN"))


def is_configured() -> bool:
    """True if any real outbound transport is available (Whapi preferred, else Meta Cloud API)."""
    return whapi_configured() or bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID"))


def meta_configured() -> bool:
    return bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID"))


def verify_signature(body: bytes, signature: str) -> bool:
    secret = os.environ.get("WHATSAPP_APP_SECRET", "")
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def strip_jid(jid: str) -> str:
    """9199...@s.whatsapp.net -> 9199...  ; keep group ids (@g.us) intact."""
    if not jid:
        return jid
    return jid.split("@")[0]


# ---------------- Outbound (Whapi preferred, Meta fallback, else simulated) ----------------
async def _whapi_post(path: str, payload: dict) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['WHAPI_TOKEN']}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{whapi_base()}{path}", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def _meta_post(payload: dict) -> dict:
    url = f"{GRAPH_URL}/{os.environ['WHATSAPP_PHONE_ID']}/messages"
    headers = {"Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def send_text(to: str, text: str, reply_to: str = None) -> dict:
    try:
        if whapi_configured():
            payload = {"to": to, "body": text}
            if reply_to:
                payload["quoted"] = reply_to
            return await _whapi_post("/messages/text", payload)
        if meta_configured():
            payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}}
            if reply_to:
                payload["context"] = {"message_id": reply_to}
            return await _meta_post(payload)
    except Exception as e:
        logger.error("send_text delivery failed to=%s: %s", to, e)
        return {"error": str(e), "delivered": False}
    logger.info("[WA-SIMULATED-OUTBOUND-TEXT] to=%s reply_to=%s body=%s", to, reply_to, text)
    return {"simulated": True, "to": to, "body": text}


async def send_buttons(to: str, body: str, buttons: list) -> dict:
    """buttons: list of {'id': str, 'title': str} (max 3). Best-effort; never raises."""
    try:
        if whapi_configured():
            try:
                return await _whapi_post("/messages/interactive", {
                    "to": to, "type": "button", "body": {"text": body},
                    "action": {"buttons": [{"type": "quick_reply", "title": b["title"][:20], "id": b["id"]} for b in buttons[:3]]},
                })
            except Exception as e:
                logger.warning("Whapi interactive failed (%s), falling back to text", e)
                opts = " / ".join(b["title"] for b in buttons)
                return await send_text(to, f"{body}\n\nReply with: {opts}")
        if meta_configured():
            return await _meta_post({
                "messaging_product": "whatsapp", "to": to, "type": "interactive",
                "interactive": {"type": "button", "body": {"text": body},
                                "action": {"buttons": [{"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}} for b in buttons[:3]]}},
            })
    except Exception as e:
        logger.error("send_buttons delivery failed to=%s: %s", to, e)
        return {"error": str(e), "delivered": False}
    logger.info("[WA-SIMULATED-OUTBOUND-BUTTONS] to=%s body=%s buttons=%s", to, body, buttons)
    return {"simulated": True, "to": to, "body": body, "buttons": buttons}


# ---------------- Connection checks ----------------
async def check_connection() -> dict:
    if whapi_configured():
        headers = {"Authorization": f"Bearer {os.environ['WHAPI_TOKEN']}"}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{whapi_base()}/health", headers=headers)
            if r.status_code == 200:
                data = r.json()
                status = (data.get("status") or {})
                return {"ok": True, "provider": "whapi", "state": status.get("text") or status, "raw": data}
            return {"ok": False, "provider": "whapi", "detail": r.text, "status": r.status_code}
    if meta_configured():
        url = f"{GRAPH_URL}/{os.environ['WHATSAPP_PHONE_ID']}"
        headers = {"Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}"}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(url, headers=headers, params={"fields": "display_phone_number,verified_name,quality_rating"})
            if r.status_code == 200:
                return {"ok": True, "provider": "meta", "phone": r.json()}
            return {"ok": False, "provider": "meta", "detail": r.text, "status": r.status_code}
    return {"ok": False, "detail": "No WhatsApp transport configured"}


# ---------------- Inbound parsers ----------------
def parse_meta_inbound(payload: dict):
    out = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                for msg in value.get("messages", []):
                    item = {"from": msg.get("from"), "type": msg.get("type"), "text": "",
                            "button_id": None, "phone_number_id": metadata.get("phone_number_id"),
                            "group_chat_id": None}
                    if msg.get("type") == "text":
                        item["text"] = msg.get("text", {}).get("body", "")
                    elif msg.get("type") == "interactive":
                        inter = msg.get("interactive", {})
                        if inter.get("type") == "button_reply":
                            item["button_id"] = inter["button_reply"]["id"]
                            item["text"] = inter["button_reply"].get("title", "")
                    out.append(item)
    except Exception as e:
        logger.warning("parse_meta_inbound error: %s", e)
    return out


# backwards-compat alias
parse_inbound = parse_meta_inbound


def parse_whapi_inbound(payload: dict):
    """Return list of {from, text, group_chat_id, button_id, from_me}."""
    out = []
    try:
        for msg in payload.get("messages", []):
            if msg.get("from_me"):
                continue
            chat_id = msg.get("chat_id", "")
            is_group = chat_id.endswith("@g.us")
            sender = msg.get("participant") if is_group else chat_id
            item = {
                "from": strip_jid(sender or msg.get("from") or ""),
                "group_chat_id": chat_id if is_group else None,
                "id": msg.get("id"),
                "type": msg.get("type"),
                "text": "",
                "button_id": None,
                "from_me": False,
            }
            mtype = msg.get("type")
            if mtype == "text":
                item["text"] = (msg.get("text") or {}).get("body", "")
            elif mtype == "reply":
                reply = msg.get("reply") or {}
                br = reply.get("buttons_reply") or {}
                item["button_id"] = br.get("id")
                item["text"] = br.get("title", "")
            elif mtype == "interactive":
                inter = msg.get("interactive") or {}
                br = (inter.get("button_reply") or {})
                item["button_id"] = br.get("id")
                item["text"] = br.get("title", "")
            elif mtype == "action":
                act = msg.get("action") or {}
                item["button_id"] = act.get("id")
                item["text"] = act.get("title", "")
            elif mtype == "button":
                b = msg.get("button") or {}
                item["button_id"] = b.get("id") or b.get("payload")
                item["text"] = b.get("text", "")
            if item["text"] or item["button_id"]:
                out.append(item)
    except Exception as e:
        logger.warning("parse_whapi_inbound error: %s", e)
    return out
