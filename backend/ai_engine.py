import os
import json
import re
import asyncio
import logging
from db import COMPLAINT_CATEGORIES

logger = logging.getLogger("propto.ai")

GREETING_WORDS = [
    "good morning", "good evening", "good night", "gm", "gn", "hi", "hello", "hey",
    "thanks", "thank you", "welcome", "congrats", "congratulations",
]
FESTIVAL_WORDS = [
    "happy diwali", "happy new year", "happy holi", "eid mubarak", "merry christmas",
    "happy birthday", "festival", "wishes", "blessed",
]
AD_WORDS = ["sale", "offer", "discount", "buy now", "for sale", "selling", "brand new", "%off", "% off", "contact for booking"]

COMPLAINT_KEYWORDS = [
    "water", "leak", "leakage", "leaking", "plumb", "tap", "pipe", "drain", "seepage", "flush",
    "electric", "power", "current", "light", "fan", "switch", "wiring", "socket", "mcb", "short circuit",
    "lift", "elevator", "stuck",
    "security", "guard", "gate", "intercom", "cctv",
    "clean", "garbage", "trash", "housekeep", "dust", "sweep",
    "wall", "crack", "paint", "civil", "ceiling", "tile", "plaster",
    "parking", "vehicle",
    "garden", "plant", "tree", "lawn",
    "generator", "dg set", "dg ",
    "pest", "cockroach", "mosquito", "rat", "termite", "insect",
    "broken", "not working", "repair", "fix", "issue", "problem", "complaint",
    "blocked", "choked", "damaged", "overflow", "no water", "no power",
]


def rule_filter(text: str) -> dict:
    """Return {'forward': bool, 'reason': str}. Only potential complaints forwarded to AI."""
    t = (text or "").lower().strip()
    if not t or len(t) < 4:
        return {"forward": False, "reason": "Empty/too short"}

    has_complaint = any(k in t for k in COMPLAINT_KEYWORDS)
    if has_complaint:
        return {"forward": True, "reason": "Complaint keyword matched"}

    for w in AD_WORDS:
        if w in t:
            return {"forward": False, "reason": "Advertisement/Spam"}
    for w in FESTIVAL_WORDS:
        if w in t:
            return {"forward": False, "reason": "Festival wish"}
    stripped = re.sub(r"[^a-z ]", "", t)
    if stripped.strip() in GREETING_WORDS or all(word in GREETING_WORDS for word in stripped.split() if word):
        return {"forward": False, "reason": "Greeting"}
    return {"forward": False, "reason": "General discussion"}


SYSTEM_PROMPT = f"""You are an AI that analyzes WhatsApp messages from a residential society group to detect maintenance complaints.
Valid complaint categories: {", ".join(COMPLAINT_CATEGORIES)}.
Analyze the message and respond ONLY with a strict minified JSON object, no markdown, no explanation, with keys:
"intent": "Complaint" or "NotComplaint",
"category": one of the valid categories or "",
"flat": flat/unit number mentioned or "",
"tower": tower/block/wing mentioned or "",
"priority": "High", "Medium" or "Low",
"preferred_time": any preferred visit time mentioned or "",
"description": a concise one-line description of the complaint,
"confidence": a float 0 to 1 indicating how confident you are this is a real maintenance complaint.
High priority = safety/urgent (no water, no power, lift stuck, security, gas). Medium = normal repairs. Low = minor/cosmetic."""


def _extract_unit(text: str):
    """Lightweight flat/tower extraction used when the Excel taxonomy matches (no AI needed)."""
    t = text or ""
    flat, tower = "", ""
    m = re.search(r"\b([A-Za-z])[-\s]?(\d{2,4})\b", t)
    if m:
        tower = m.group(1).upper()
        flat = (m.group(1) + m.group(2)).upper()
    else:
        m2 = re.search(r"(?:flat|unit|apartment|apt|house)\s*(?:no\.?)?\s*([A-Za-z]?-?\d{1,4})", t, re.I)
        if m2:
            flat = m2.group(1).upper().replace("-", "")
    mt = re.search(r"(?:tower|block|wing)\s*([A-Za-z0-9]{1,3})", t, re.I)
    if mt:
        tower = mt.group(1).upper()
    return flat, tower


async def _call_llm(text: str) -> str:
    """Use the user's own Gemini key when self-hosting; else the Emergent LLM key.
    Degrades gracefully (returns "") if no LLM is configured or a call fails."""
    gkey = os.environ.get("GEMINI_API_KEY")
    if gkey:
        try:
            return await asyncio.wait_for(asyncio.to_thread(_gemini_native, text, gkey), timeout=15)
        except Exception as e:
            logger.warning("Gemini call failed/timed out: %s", e)
            return ""
    if os.environ.get("EMERGENT_LLM_KEY"):
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=os.environ["EMERGENT_LLM_KEY"],
                session_id="propto-ai",
                system_message=SYSTEM_PROMPT,
            ).with_model("gemini", "gemini-2.5-flash")
            resp = await asyncio.wait_for(chat.send_message(UserMessage(text=f"Message: {text}")), timeout=15)
            return resp if isinstance(resp, str) else str(resp)
        except Exception as e:
            logger.warning("Emergent LLM call failed: %s", e)
            return ""
    logger.warning("No LLM configured (set GEMINI_API_KEY) — skipping AI classification")
    return ""


def _gemini_native(text: str, key: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=SYSTEM_PROMPT)
    resp = model.generate_content(f"Message: {text}", request_options={"timeout": 12})
    return getattr(resp, "text", "") or ""


async def _ai_classify(text: str) -> dict:
    raw = await _call_llm(text)
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if m:
        cleaned = m.group(0)
    try:
        data = json.loads(cleaned)
    except Exception:
        data = {"intent": "NotComplaint", "category": "", "flat": "", "tower": "",
                "priority": "Low", "preferred_time": "", "description": text[:120], "confidence": 0.0}
    data.setdefault("intent", "NotComplaint")
    data.setdefault("category", "")
    data.setdefault("flat", "")
    data.setdefault("tower", "")
    data.setdefault("priority", "Medium")
    data.setdefault("preferred_time", "")
    data.setdefault("description", text[:120])
    try:
        data["confidence"] = float(data.get("confidence", 0))
    except Exception:
        data["confidence"] = 0.0
    if data.get("category") not in COMPLAINT_CATEGORIES:
        data["category"] = data.get("category") or ""
    data["source_of_truth"] = "ai"
    return data


async def analyze_message(text: str) -> dict:
    # 1) Check the 1,000-row taxonomy Excel FIRST. If the issue is present, use its
    #    category / sub-category / severity / handled-by / vendor directly.
    import situations_kb
    kb = situations_kb.match(text)
    if kb:
        flat, tower = _extract_unit(text)
        return {
            "intent": "Complaint",
            "category": kb["category"],
            "sub_category": kb.get("sub_category", ""),
            "flat": flat,
            "tower": tower,
            "priority": kb["priority"],
            "preferred_time": "",
            "description": text[:150],
            "confidence": 0.9,
            "routing_category": kb.get("app_category", ""),
            "kb_category": kb["category"],
            "matched_situation": kb.get("subcategory"),
            "kb_score": kb.get("score"),
            "handled_by": kb.get("handled_by", ""),
            "vendor_required": kb.get("vendor_required", ""),
            "source_of_truth": "excel",
        }
    # 2) Not in the taxonomy -> fall back to AI.
    return await _ai_classify(text)
