import os
import hmac
import hashlib
import logging
import httpx

logger = logging.getLogger("propto.whatsapp")

GRAPH_URL = "https://graph.facebook.com/v19.0"


def is_configured() -> bool:
    return bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_ID"))


def verify_signature(body: bytes, signature: str) -> bool:
    secret = os.environ.get("WHATSAPP_APP_SECRET", "")
    if not secret:
        return True  # skip validation when not configured (dev/simulator)
    if not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


async def _post(payload: dict) -> dict:
    if not is_configured():
        logger.info("[WA-SIMULATED-OUTBOUND] %s", payload)
        return {"simulated": True, "payload": payload}
    url = f"{GRAPH_URL}/{os.environ['WHATSAPP_PHONE_ID']}/messages"
    headers = {
        "Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def send_text(phone: str, text: str) -> dict:
    return await _post({
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    })


async def send_buttons(phone: str, body: str, buttons: list) -> dict:
    """buttons: list of {'id': str, 'title': str} (max 3)"""
    return await _post({
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                    for b in buttons[:3]
                ]
            },
        },
    })


def parse_inbound(payload: dict):
    """Return list of dicts: {from, text, type, button_id, group_id}"""
    out = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                for msg in value.get("messages", []):
                    item = {
                        "from": msg.get("from"),
                        "type": msg.get("type"),
                        "text": "",
                        "button_id": None,
                        "phone_number_id": metadata.get("phone_number_id"),
                    }
                    if msg.get("type") == "text":
                        item["text"] = msg.get("text", {}).get("body", "")
                    elif msg.get("type") == "interactive":
                        inter = msg.get("interactive", {})
                        if inter.get("type") == "button_reply":
                            item["button_id"] = inter["button_reply"]["id"]
                            item["text"] = inter["button_reply"].get("title", "")
                    out.append(item)
    except Exception as e:
        logger.warning("parse_inbound error: %s", e)
    return out
