import os
import json
import re
from emergentintegrations.llm.chat import LlmChat, UserMessage
from db import COMPLAINT_CATEGORIES

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


async def analyze_message(text: str) -> dict:
    api_key = os.environ["EMERGENT_LLM_KEY"]
    chat = LlmChat(
        api_key=api_key,
        session_id="propto-ai",
        system_message=SYSTEM_PROMPT,
    ).with_model("gemini", "gemini-2.5-flash")
    resp = await chat.send_message(UserMessage(text=f"Message: {text}"))
    raw = resp if isinstance(resp, str) else str(resp)
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
    # Match against the 500-situation knowledge base. On a confident match the
    # Excel category/sub-category/priority take precedence over the AI guess.
    try:
        import situations_kb
        kb = situations_kb.match(text)
        if kb:
            if kb.get("app_category"):
                data["category"] = kb["app_category"]
            if kb.get("priority"):
                data["priority"] = kb["priority"]
            data["sub_category"] = kb.get("sub_category") or ""
            data["kb_category"] = kb.get("kb_category") or ""
            data["matched_situation"] = kb.get("situation")
            data["kb_score"] = kb.get("score")
            # A KB hit means it is a genuine maintenance situation.
            if data.get("intent") != "Complaint":
                data["intent"] = "Complaint"
            if float(data.get("confidence", 0)) < 0.7:
                data["confidence"] = 0.75
    except Exception:
        pass
    return data
