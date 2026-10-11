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


# Phrases that indicate an issue is already fixed/closed (so NOT a new complaint),
# and negations that cancel that resolved sense ("still not resolved", "not fixed yet").
RESOLVED_WORDS = [
    "resolved", "fixed", "sorted", "solved", "rectified", "restored", "repaired",
    "working now", "working fine", "back to normal", "all good now", "issue closed",
    "problem closed", "no longer an issue", "sorted out", "cleared now",
]
NEGATION_WORDS = ["not ", "n't", "pending", "still", "yet", "nahi", "unresolved", "never", "haven't", "isn't", "aren't"]


def is_resolved_context(text: str) -> bool:
    """True when the message reads as an already-resolved/positive update (e.g.
    'swimming pool issue is resolved') and not as a live complaint."""
    t = (text or "").lower()
    if any(w in t for w in NEGATION_WORDS):
        return False
    return any(w in t for w in RESOLVED_WORDS)


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


# Society issue topics — a message is a Complaint ONLY if it clearly reports a
# specific problem/fault/grievance falling under one of these. (De-duplicated.)
ISSUE_TOPICS = list(dict.fromkeys([
    "Power / Electricity", "Voltage / Electrical Damage", "Lift / Elevator",
    "Generator / DG Backup", "Water Supply", "Water Quality / TDS", "Hot Water / Solar",
    "Plumbing / Leakage", "Gas Pipeline", "STP / Sewage / Drainage",
    "Garbage / Housekeeping", "Parking", "Security / CCTV / Theft",
    "Gate Access / Deliveries", "Amenities / Clubhouse / Pool / Gym",
    "Noise / Construction", "Fire Safety / Smoke", "Pest / Insects / Animals",
    "Common Area / Terrace / Structure", "Roads / External Works / Landscaping",
    "Finance / Billing / Collections", "Staff / Vendor / Service Quality",
    "Resident Behavior / Rule Violation", "Communication / Notices / Governance",
    "Health / Safety / Emergency", "Intercom / Communication Devices",
    "Parking Management System", "Gym / Fitness Equipment",
    "Swimming Pool / Water Features", "Children Play Area / Sports",
    "Society Events / Festivals", "Legal / Society Bye-Laws",
    "Staff Attendance / Payroll", "Waste Segregation / Composting",
    "Monsoon Preparedness", "Flat Interior Maintenance", "Domestic Help / Labour",
    "Construction / Renovation Within Flat", "NRI / Absentee Resident",
    "Tenant Onboarding / KYC", "Air Quality / Ventilation",
    "Delivery / E-Commerce Handling", "Smart Metering / Sub-Metering",
    "Horticulture / Gardening", "Noise / Sound Proofing",
    "Society App / Digital Services", "Substation / HT Connection",
    "Painting / Waterproofing AMC", "Plumbing AMC / Annual Maintenance",
    "Electrical AMC / Wiring Maintenance", "Parking Allocation / Disputes",
    "Staircase / Common Corridor", "Senior Citizen Amenities",
    "Indoor Games / Recreation", "Library / Study Room", "Pet Policy / Animal Care",
    "Gate Access / Entry Management", "Natural Disaster / Emergency Response",
    "AGM / Committee / Elections", "Rooftop / Terrace Access & Maintenance",
    "Balcony / Window / External Facade", "Society Governance / Transparency",
    "Emergency Evacuation / Safety Drills", "Vandalism / Anti-Social Behaviour",
    "Document / Record Management", "Community Well-Being / Mental Health",
    "Visitor / Guest Policy", "CCTV / Surveillance", "Society Property / Asset Management",
    "Flood / Drainage", "Society Cyber Security", "Infrastructure Defects / Builder Warranty",
    "Seasonal / Weather Specific", "Drinking Water & RO Plant", "Gas Pipeline & PNG Supply",
    "Solar Hot Water System", "STP & Sewage Treatment Plant", "Fire Safety Systems",
    "Electrical Issues Within Flat", "Plumbing Issues Within Flat",
    "Air Conditioning & Cooling In Flat", "Internet & Cable TV Services",
    "Home Security Within Flat", "Housekeeping & Sanitation",
    "Society Office & Administration", "Security System & Guard Operations",
    "Noise from Neighbours", "Waterproofing & Seepage Issues",
    "Resident Disputes & Mediation", "Structural & Civil Works",
    "Building Maintenance & Annual Works", "Water Pump & Motor",
    "Pest & Insect Control", "Staff Welfare & HR", "Vendor & Contract Management",
    "Flat Access & Key Management", "Adjacent Construction Impact",
    "Society Road & Internal Traffic", "New Amenity Requests",
    "Smart Society Technology", "Garbage Room & Chute", "Painting & Surface Maintenance",
    "AC & HVAC Common Area", "Swimming Pool Operations", "Internet & Communication Infrastructure",
    "Domestic Help Management", "Society Vehicle & Equipment", "Building Envelope & Exterior",
    "Resident Onboarding & Offboarding", "Neighbour Relations & Etiquette",
    "Sustainability & Green Initiatives", "Digital Payments & Billing Systems",
    "Amenity Booking & Usage", "Special Needs & Accessibility",
    "Utilities Coordination & Municipal", "Construction & Renovation Governance",
    "Emergency Medical & Health Response", "Society Records Digitisation",
    "Society Communication Channels", "Common Area Furniture & Fittings",
    "Common Area Usage Conflicts", "Lift Entrapment & Rescue", "Fire Incident Response",
    "Water Emergency & Contamination", "Power Outage & Backup Failure",
    "Structural Safety Alerts", "Security Breach & Incidents", "Sewage & Drainage Emergency",
    "Gas Leak & Safety Emergency", "Pest Infestation Escalation", "Weather Emergency Response",
    "Committee Transition & Handover", "Resident Safety Awareness",
    "Society Financial Planning", "Resident Data & Privacy", "Amenity Safety Compliance",
    "Utility Bill Disputes", "Society Notice Compliance", "Multi-Tower Coordination",
    "Society Website & Online Presence", "Insurance & Claims Management",
    "Society Store & Inventory", "Building Occupancy & Density",
    "Post-Occupancy Building Performance", "Society Redevelopment",
]))

SYSTEM_PROMPT = f"""You are a strict classifier for a residential society WhatsApp group. Your job is to decide whether a message is a genuine COMPLAINT / ISSUE report that a society management team must act on.

Mark "intent":"Complaint" ONLY IF ALL of these hold:
1. The message clearly describes a SPECIFIC problem, fault, breakdown, shortage, damage, malfunction, outage, hazard or grievance about something concrete in the society or a flat.
2. That problem clearly belongs to one of these society issue topics:
{", ".join(ISSUE_TOPICS)}.
3. It reads like the sender is reporting/complaining about that issue (not merely chatting, asking, or mentioning the topic in passing).

Mark "intent":"NotComplaint" for everything else. Be STRICT — the following are NOT complaints:
- greetings, thanks, congratulations, festival/birthday wishes, small talk, jokes, forwards, memes
- general questions or requests for information ("what time is the meeting?", "who is the plumber?")
- opinions, discussions, suggestions, feedback, poll messages, announcements, invitations, notices
- buy/sell/rent ads, promotions, service offers
- acknowledgements/replies like "ok", "done", "noted", "thanks", "sure"
- vague or generic statements that do not name a specific problem (e.g. "society is nice", "good work team")
If the message only mentions a topic without a clear, specific problem, choose NotComplaint. If unsure, choose NotComplaint with low confidence.

Respond ONLY with a strict minified JSON object, no markdown, no explanation, with keys:
"intent": "Complaint" or "NotComplaint",
"category": the single best-matching topic from the list above, or "",
"flat": flat/unit number mentioned or "",
"tower": tower/block/wing mentioned or "",
"priority": "High", "Medium" or "Low",
"preferred_time": any preferred visit time mentioned or "",
"description": a concise one-line description of the complaint,
"confidence": a float 0 to 1 for how sure you are this is a REAL, specific complaint. Use >=0.8 only when it clearly reports a concrete problem; use <0.5 when it is chit-chat/ambiguous.
High priority = safety/urgent (no water, no power, lift stuck/entrapment, fire/smoke/gas leak, security/theft, medical). Medium = normal repairs. Low = minor/cosmetic."""


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

    # 3) Safety net — if the deterministic signals say this is a genuine society issue
    #    (domain keyword / generic indicator like "issue"/"problem", or a taxonomy match)
    #    and the message is NOT a resolved/positive update, force a Complaint. This
    #    overrides the LLM even when it answered successfully, because the LLM is
    #    inconsistent on short phrasings like "water issue in my flat".
    resolved_ctx = is_resolved_context(text)
    if ai.get("intent") != "Complaint" and (kb or kw_hit) and not resolved_ctx:
        reason = "taxonomy_match" if kb else "keyword_match"
        logger.info("Complaint override (%s); llm_ok=%s resolved_ctx=%s", reason, ai.get("_llm_ok"), resolved_ctx)
        ai["intent"] = "Complaint"
        ai["override_reason"] = reason
        # Ensure sane defaults for ticket creation (esp. when OpenAI failed/was empty).
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
