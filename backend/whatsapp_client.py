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
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.post(f"{whapi_base()}{path}", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def _meta_post(payload: dict) -> dict:
    url = f"{GRAPH_URL}/{os.environ['WHATSAPP_PHONE_ID']}/messages"
    headers = {"Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()


async def send_poll(to: str, title: str, options: list, count: int = 1) -> dict:
    """Send a native WhatsApp poll. Best-effort; never raises."""
    try:
        if whapi_configured():
            return await _whapi_post("/messages/poll", {"to": to, "title": title, "options": options, "count": count})
        if meta_configured():
            return await send_buttons(to, title, [{"id": "poll_" + o.lower(), "title": o} for o in options[:3]])
    except Exception as e:
        logger.error("send_poll failed to=%s: %s", to, e)
        return {"error": str(e), "delivered": False}
    logger.info("[WA-SIMULATED-POLL] to=%s title=%s options=%s", to, title, options)
    return {"simulated": True}


def poll_message_id_from(resp) -> str:
    if not isinstance(resp, dict) or resp.get("error") or resp.get("simulated"):
        return None
    m = resp.get("message") or {}
    if m.get("id"):
        return m["id"]
    if resp.get("id"):
        return resp["id"]
    msgs = resp.get("messages") or []
    if isinstance(msgs, list) and msgs:
        return msgs[0].get("id")
    return None


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


async def list_groups() -> list:
    """List the linked Whapi number's WhatsApp groups so the admin can pick the
    exact group (guarantees the stored chat_id matches inbound webhooks)."""
    if not whapi_configured():
        return []
    headers = {"Authorization": f"Bearer {os.environ['WHAPI_TOKEN']}"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{whapi_base()}/groups", headers=headers, params={"count": 200})
        r.raise_for_status()
        data = r.json()
    raw = data.get("groups") or data.get("data") or (data if isinstance(data, list) else [])
    out = []
    for g in raw:
        if not isinstance(g, dict):
            continue
        gid = g.get("id") or g.get("chat_id") or g.get("group_id")
        if not gid:
            continue
        if "@" not in gid:
            gid = f"{gid}@g.us"
        name = g.get("name") or g.get("subject") or g.get("title") or gid
        out.append({"id": gid, "name": name})
    return out


async def get_poll_results(message_id: str) -> dict:
    """Fetch the authoritative poll state (title + results with counts) for a poll
    message id. Used to tally votes even when only messages.post is enabled."""
    if not whapi_configured() or not message_id:
        return {}
    headers = {"Authorization": f"Bearer {os.environ['WHAPI_TOKEN']}"}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{whapi_base()}/messages/{message_id}", headers=headers)
            r.raise_for_status()
            data = r.json()
        msg = data.get("message") or data
        return msg.get("poll") or {}
    except Exception as e:
        logger.warning("get_poll_results failed for %s: %s", message_id, e)
        return {}


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
    """Return list of message items. Poll results are included even when from_me
    (we own the poll), so vote tallies flow back in."""
    out = []
    try:
        for upd in payload.get("messages_updates", []):
            au = upd.get("after_update") or {}
            poll = au.get("poll")
            if poll:
                cid = au.get("chat_id", "") or ""
                out.append({
                    "from": "", "group_chat_id": cid if cid.endswith("@g.us") else None,
                    "id": au.get("id") or upd.get("id"), "type": "poll",
                    "poll": poll, "poll_update": {}, "from_me": True,
                })
        for msg in payload.get("messages", []):
            chat_id = msg.get("chat_id", "")
            is_group = chat_id.endswith("@g.us")
            sender = msg.get("participant") if is_group else chat_id
            mtype = msg.get("type")
            base = {
                "from": strip_jid(sender or msg.get("from") or ""),
                "group_chat_id": chat_id if is_group else None,
                "id": msg.get("id"),
                "type": mtype,
                "text": "",
                "button_id": None,
                "from_me": bool(msg.get("from_me")),
            }
            act0 = msg.get("action") or {}
            is_vote = mtype == "action" and act0.get("type") == "vote"
            if mtype in ("poll", "poll_update") or msg.get("poll") or msg.get("poll_update") or is_vote:
                base["type"] = "poll"
                if is_vote:
                    # messages.post vote: no counts here — fetch authoritative poll state.
                    base["poll"] = {}
                    base["poll_update"] = {}
                    base["poll_fetch_id"] = act0.get("target") or msg.get("id")
                else:
                    base["poll"] = msg.get("poll") or {}
                    base["poll_update"] = msg.get("poll_update") or {}
                out.append(base)
                continue
            if msg.get("from_me"):
                continue
            if mtype == "text":
                base["text"] = (msg.get("text") or {}).get("body", "")
            elif mtype == "reply":
                br = (msg.get("reply") or {}).get("buttons_reply") or {}
                base["button_id"] = br.get("id"); base["text"] = br.get("title", "")
            elif mtype == "interactive":
                br = (msg.get("interactive") or {}).get("button_reply") or {}
                base["button_id"] = br.get("id"); base["text"] = br.get("title", "")
            elif mtype == "action":
                act = msg.get("action") or {}
                base["button_id"] = act.get("id"); base["text"] = act.get("title", "")
            elif mtype == "button":
                b = msg.get("button") or {}
                base["button_id"] = b.get("id") or b.get("payload"); base["text"] = b.get("text", "")
            if base["text"] or base["button_id"]:
                out.append(base)
    except Exception as e:
        logger.warning("parse_whapi_inbound error: %s", e)
    return out
