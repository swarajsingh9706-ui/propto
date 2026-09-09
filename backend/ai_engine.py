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


# Keyword -> app category groups. Used for the deterministic safety net so genuine
# complaints are never dropped when OpenAI fails or misclassifies (e.g. Hinglish).
KEYWORD_CATEGORIES = [
    ("Lift", ["lift", "elevator"]),
    ("Plumbing", ["water", "leak", "leakage", "leaking", "seepage", "drain", "pipe", "tap",
                  "flush", "overflow", "sewage", "toilet", "no water", "plumb", "choked", "blocked"]),
    ("Electrical", ["power", "electric", "current", "light", "fan", "switch", "wiring",
                    "socket", "mcb", "short circuit", "no power", "fuse"]),
    ("Security", ["security", "guard", "gate", "intercom", "cctv", "theft"]),
    ("Housekeeping", ["clean", "garbage", "trash", "dust", "sweep", "housekeep"]),
    ("Pest Control", ["pest", "cockroach", "mosquito", "rat", "termite", "insect"]),
    ("Gardening", ["garden", "plant", "tree", "lawn"]),
    ("Parking", ["parking", "vehicle"]),
    ("DG Set", ["generator", "dg set", "dg "]),
    ("Civil", ["wall", "crack", "paint", "ceiling", "tile", "plaster", "civil"]),
]

# Generic complaint indicators that, on their own, still mean "this is a complaint".
GENERIC_COMPLAINT_WORDS = ["broken", "not working", "repair", "fix ", "issue", "problem",
                           "complaint", "damaged", "stuck", "down hai", "kharab", "band hai"]


def strong_keyword_hit(text: str):
    """Deterministic complaint signal. Returns (True, category) if the message contains a
    domain keyword or a generic complaint indicator; else (False, '')."""
    t = (text or "").lower()
    for cat, words in KEYWORD_CATEGORIES:
        for w in words:
            if w in t:
                return True, cat
    for w in GENERIC_COMPLAINT_WORDS:
        if w in t:
            return True, ""
    return False, ""


def prefilter(text: str) -> dict:
    """Cheap gate BEFORE the LLM. Drops ONLY greeting messages (and empty text);
    every other message is sent to OpenAI, which makes the complaint-or-not decision."""
    t = (text or "").lower().strip()
    if not t:
        return {"forward": False, "reason": "Empty"}
    stripped = re.sub(r"[^a-z ]", "", t)
    words = [w for w in stripped.split() if w]
    if words and all(w in GREETING_WORDS for w in words):
        return {"forward": False, "reason": "Greeting"}
    return {"forward": True, "reason": "Forwarded to OpenAI"}


def rule_filter(text: str) -> dict:
    """Deprecated keyword gate (kept for compatibility). Use prefilter()."""
    return prefilter(text)


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


OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")


async def _call_llm(text: str) -> str:
    """Use the user's own OpenAI key when self-hosting (OPENAI_API_KEY); else the
    Emergent universal LLM key (preview/Emergent env only). Returns "" and logs on
    failure so the deterministic safety net can still catch genuine complaints."""
    okey = os.environ.get("OPENAI_API_KEY")
    if okey:
        try:
            out = await asyncio.wait_for(asyncio.to_thread(_openai_native, text, okey), timeout=20)
            if out and out.strip():
                logger.info("OpenAI OK (%d chars)", len(out))
            else:
                logger.warning("OpenAI returned empty response")
            return out
        except Exception as e:
            logger.warning("OpenAI call failed/timed out: %s", e)
            return ""
    if os.environ.get("EMERGENT_LLM_KEY"):
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=os.environ["EMERGENT_LLM_KEY"],
                session_id="propto-ai",
                system_message=SYSTEM_PROMPT,
            ).with_model("openai", OPENAI_MODEL)
            resp = await asyncio.wait_for(chat.send_message(UserMessage(text=f"Message: {text}")), timeout=20)
            out = resp if isinstance(resp, str) else str(resp)
            if out and out.strip():
                logger.info("OpenAI (Emergent) OK (%d chars)", len(out))
            else:
                logger.warning("OpenAI (Emergent) returned empty response")
            return out
        except Exception as e:
            logger.warning("Emergent LLM call failed: %s", e)
            return ""
    logger.warning("No LLM configured (set OPENAI_API_KEY) — skipping AI classification")
    return ""


def _openai_native(text: str, key: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Message: {text}"},
        ],
        response_format={"type": "json_object"},
        timeout=18,
    )
    return resp.choices[0].message.content or ""


async def _ai_classify(text: str) -> dict:
    raw = await _call_llm(text)
    llm_ok = bool(raw and raw.strip())
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
    data["_llm_ok"] = llm_ok
    return data


async def analyze_message(text: str) -> dict:
    """Flow: OpenAI decides complaint-or-not (+ extracts flat/priority/description),
    THEN the 10,000-row taxonomy enriches category/severity/routing if present,
    ELSE the OpenAI-generated content is used to build the ticket.

    Safety net: if OpenAI says NotComplaint OR the OpenAI call failed/returned empty,
    but the message strongly matches the 10,000-row taxonomy or a complaint keyword,
    we override to a valid Complaint so genuine issues are never silently dropped."""
    # 1) OpenAI: is this an actual complaint? (also extracts flat/tower/priority/description)
    ai = await _ai_classify(text)

    # 2) Deterministic signals (independent of OpenAI).
    import situations_kb
    kb = situations_kb.match(text)
    kw_hit, kw_cat = strong_keyword_hit(text)

    # 3) Override NotComplaint / OpenAI-failure when there's a real complaint signal.
    if ai.get("intent") != "Complaint" and (kb or kw_hit):
        reason = "taxonomy_match" if kb else "keyword_match"
        logger.info("Complaint override applied (%s); LLM intent=%s llm_ok=%s",
                    reason, ai.get("intent"), ai.get("_llm_ok"))
        ai["intent"] = "Complaint"
        ai["override_reason"] = reason
        # When OpenAI failed, ensure sane defaults for ticket creation.
        if not ai.get("description"):
            ai["description"] = text[:150]
        if kw_cat and not ai.get("category"):
            ai["category"] = kw_cat
        ai["priority"] = ai.get("priority") or "Medium"
        # Bump confidence past the ticket threshold so a ticket is actually created.
        ai["confidence"] = max(float(ai.get("confidence", 0) or 0), 0.85)

    if ai.get("intent") != "Complaint":
        return ai

    # 4) Complaint -> enrich from the 10,000-issue taxonomy for authoritative routing.
    if kb:
        ai["category"] = kb["category"]
        ai["sub_category"] = kb.get("sub_category", "")
        ai["priority"] = kb["priority"]
        ai["routing_category"] = kb.get("app_category", "")
        ai["kb_category"] = kb["category"]
        ai["matched_situation"] = kb.get("issue") or kb.get("subcategory")
        ai["kb_score"] = kb.get("score")
        ai["handled_by"] = kb.get("handled_by", "")
        ai["vendor_required"] = kb.get("vendor_required", "")
        ai["confidence"] = max(float(ai.get("confidence", 0) or 0), 0.9)
        ai["source_of_truth"] = "excel"
    else:
        # 5) No taxonomy match -> rely on the OpenAI-generated (or keyword-derived) content.
        if kw_cat:
            ai["routing_category"] = ai.get("routing_category") or kw_cat
        ai["source_of_truth"] = "ai"
    return ai
