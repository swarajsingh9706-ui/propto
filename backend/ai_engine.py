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
# Topic keywords (regex, word-boundary matched) -> app category used for vendor routing.
TOPIC_CATEGORIES = [
    ("Lift", [r"lifts?", r"elevators?"]),
    ("DG Set", [r"generators?", r"dg", r"dg set", r"diesel"]),
    ("Electrical", [r"power", r"electric\w*", r"electricity", r"current", r"lights?", r"bulbs?",
                    r"tube ?lights?", r"fans?", r"switch\w*", r"wiring", r"wires?", r"sockets?",
                    r"mcb", r"short circuit", r"fuses?", r"voltage", r"spark\w*", r"geyser",
                    r"inverter", r"meter", r"bijli", r"light ?bill", r"plug", r"shock"]),
    ("Plumbing", [r"water", r"leak\w*", r"seepage", r"drain\w*", r"pipes?", r"pipeline", r"taps?",
                  r"flush\w*", r"overflow\w*", r"sewage", r"toilets?", r"plumb\w*", r"choke?d?",
                  r"basin", r"sink", r"washroom", r"bathroom", r"tank", r"pani", r"motor", r"pump"]),
    ("Security", [r"security", r"guards?", r"gates?", r"intercom", r"cctv", r"camera", r"theft",
                  r"stolen", r"thief", r"watchman", r"stranger"]),
    ("Housekeeping", [r"clean\w*", r"garbage", r"trash", r"dust\w*", r"sweep\w*", r"housekeep\w*",
                      r"dirty", r"waste", r"kachra", r"smell\w*", r"stink\w*", r"mopping"]),
    ("Pest Control", [r"pests?", r"cockroach\w*", r"mosquito\w*", r"rats?", r"termites?", r"insects?",
                      r"rodents?", r"bed ?bugs?", r"lizards?", r"snakes?"]),
    ("Gardening", [r"garden\w*", r"plants?", r"trees?", r"lawn", r"grass"]),
    ("Parking", [r"parking", r"parked", r"vehicles?", r"car", r"bike"]),
    ("Civil", [r"walls?", r"cracks?", r"paint\w*", r"ceiling", r"tiles?", r"plaster\w*", r"civil",
               r"doors?", r"windows?", r"railing", r"stairs?", r"staircase", r"roof", r"terrace"]),
]
_TOPIC_RX = [(cat, re.compile(r"\b(?:" + "|".join(ws) + r")\b")) for cat, ws in TOPIC_CATEGORIES]

# Problem indicators — a topic word alone ("electrician is coming") is NOT a complaint.
_PROBLEM_RX = re.compile(r"\b(?:" + "|".join([
    r"issues?", r"problems?", r"complain\w*", r"not working", r"isn'?t working", r"doesn'?t work\w*",
    r"not work\w*", r"stopped", r"broken", r"broke", r"leak\w*", r"damage\w*", r"stuck", r"faulty",
    r"fault", r"no (?:water|power|electricity|lights?|current|supply|gas|lift|bijli|pani)",
    r"not coming", r"not available", r"not (?:collected|cleaned|picked|done|repaired|fixed|attended|resolved)", r"cut", r"outage", r"tripp\w*", r"kharab", r"band hai",
    r"nahi aa\w*", r"nahi hai", r"choke?d", r"block\w*", r"overflow\w*", r"smell\w*", r"stink\w*",
    r"dirty", r"repair\w*", r"fix", r"blown", r"spark\w*", r"short circuit", r"low pressure",
    r"drip\w*", r"seep\w*", r"crack\w*", r"flicker\w*", r"dead", r"burnt", r"burning", r"fell",
    r"falling", r"missing", r"stolen", r"theft", r"infest\w*", r"malfunction\w*", r"fail\w*",
    r"went off", r"gone", r"down", r"jammed", r"noisy", r"shock", r"fluctuat\w*", r"contaminat\w*",
    r"muddy", r"dirty water", r"please check", r"pls check", r"urgent\w*", r"help",
]) + r")\b")

# Status / acknowledgement replies (staff or residents chatting), never new complaints.
_STATUS_RX = re.compile(r"\b(?:" + "|".join([
    r"w(?:or|ro)king on it", r"on it", r"on my way", r"on the way", r"will (?:check|fix|do|look|send|update|come|see|inform|call)",
    r"looking into", r"checking", r"coming", r"reached", r"done", r"noted", r"ok(?:ay)?", r"sure",
    r"in progress", r"wip", r"rn", r"right now", r"thanks?", r"thank you", r"got it", r"received",
]) + r")\b")

# Default vendor role per app category (used when the taxonomy does not agree with keywords).
CATEGORY_VENDOR = {
    "Electrical": "Electrician", "Plumbing": "Plumber", "Lift": "Lift Technician",
    "DG Set": "DG Technician", "Security": "Security Agency", "Housekeeping": "Housekeeping Vendor",
    "Pest Control": "Pest Control Vendor", "Gardening": "Landscape Vendor", "Parking": "Society Manager",
    "Civil": "Civil Vendor", "Water Supply": "Plumber",
}


def keyword_category(text: str) -> str:
    """Best app category from topic keywords (most hits wins, list order breaks ties)."""
    t = (text or "").lower()
    best, best_n = "", 0
    for cat, rx in _TOPIC_RX:
        n = len(rx.findall(t))
        if n > best_n:
            best, best_n = cat, n
    return best


def has_problem_word(text: str) -> bool:
    return bool(_PROBLEM_RX.search((text or "").lower()))


def is_status_reply(text: str) -> bool:
    return bool(_STATUS_RX.search((text or "").lower())) and not has_problem_word(text)


def strong_keyword_hit(text: str):
    """(True, category) only when the message has BOTH a topic word and a problem word."""
    import taxonomy_v3
    cat = keyword_category(text)
    if (cat and has_problem_word(text)) or taxonomy_v3.has_complaint_signal(text):
        return True, cat
    return False, cat


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
- STATUS UPDATES / REPLIES from staff, vendors or residents about work in progress: "working on it rn", "on my way", "will check", "electrician is coming", "done", "plumber reached", "checking now"
- updates that a problem is already resolved/fixed: "lift is working now", "pool issue is resolved"
Examples that ARE complaints: "water issue in my flat", "no power in B-302", "lift stuck at 5th floor", "light not working in corridor", "tap leaking in kitchen", "garbage not collected since 2 days".
If the message only mentions a topic without a clear, specific problem, choose NotComplaint. If unsure, choose NotComplaint with low certainty.

Respond ONLY with a strict minified JSON object, no markdown, no explanation, with keys:
"intent": "Complaint" or "NotComplaint",
"category": the single best-matching topic from the list above, or "",
"flat": flat/unit number mentioned or "",
"tower": tower/block/wing mentioned or "",
"priority": "High", "Medium" or "Low",
"preferred_time": any preferred visit time mentioned or "",
"description": a concise one-line description of the complaint,
"confidence": a float 0 to 1 for how sure you are this is a REAL, specific complaint. Use >=0.8 only when it clearly reports a concrete problem; use <0.5 when it is chit-chat/ambiguous,
"certainty": a float 0 to 1 for how sure you are of your intent decision (either way).
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


# Follow-ups that say a problem persists ("still not resolved") are real complaints.
_UNRESOLVED_RX = re.compile(r"\b(?:still|not (?:yet )?(?:resolved|fixed|solved|repaired|done|attended)|again)\b")


def decide_intent(text: str, ai: dict) -> tuple:
    """Final complaint decision. AI decides; keywords only rescue an unsure/failed AI
    when the message has BOTH a topic word and a problem word. Returns (is_complaint, reason)."""
    if is_resolved_context(text):
        return False, "resolved update"
    if is_status_reply(text):
        return False, "status reply"
    kw_hit, _ = strong_keyword_hit(text)
    if not ai.get("_llm_ok"):
        return (True, "keyword_fallback") if kw_hit else (False, "AI unavailable, no complaint keywords")
    if ai.get("intent") == "Complaint":
        return True, "ai"
    try:
        certainty = float(ai.get("certainty", 0.5))
    except (TypeError, ValueError):
        certainty = 0.5
    if kw_hit and (certainty < 0.75 or _UNRESOLVED_RX.search((text or "").lower())):
        return True, "keyword_override"
    return False, "AI: not a complaint"


async def analyze_message(text: str) -> dict:
    """AI decides complaint-or-not; taxonomy v3 (object + problem) decides issue line,
    category, severity and vendor; keywords/AI topic are the fallback when v3 finds nothing."""
    import situations_kb, taxonomy_v3
    ai = await _ai_classify(text)
    tx = taxonomy_v3.match(text)
    if tx and tx["decided_by"] == "Safety override" and not is_resolved_context(text):
        ai["intent"], ai["_llm_ok"] = "Complaint", True
    is_complaint, reason = decide_intent(text, ai)
    ai["decision_reason"] = reason
    if not is_complaint:
        ai["intent"] = "NotComplaint"
        return ai

    ai["intent"] = "Complaint"
    if reason in ("keyword_fallback", "keyword_override"):
        ai["override_reason"] = reason
        ai["confidence"] = max(float(ai.get("confidence", 0) or 0), 0.85)
    ai["description"] = ai.get("description") or text[:150]
    ai["priority"] = ai.get("priority") or "Medium"

    ai_topic = ai.get("category") or ""
    if tx:
        ai.update({
            "category": tx["category"], "sub_category": tx["label"], "kb_category": tx["category"],
            "matched_situation": tx["issue_line"], "issue_id": tx["issue_id"], "priority": tx["severity"] or ai["priority"],
            "sla_target": tx["sla"], "propto_action": tx["action"], "manager_alert": tx["manager_alert"],
            "location": tx["location"], "decided_by": tx["decided_by"], "routing_category": tx["vendor_category"],
            "handled_by": tx["handled_by"], "vendor_required": tx["vendor_required"], "source_of_truth": "taxonomy_v3",
        })
        return ai

    cat = keyword_category(text) or (situations_kb._app_cat(ai_topic, "", "") if ai_topic else "") or "Civil"
    ai["category"] = cat
    ai["routing_category"] = cat
    ai["sub_category"] = ai_topic if ai_topic != cat else ""
    vendor_role = CATEGORY_VENDOR.get(cat, "Society Manager")
    ai["handled_by"] = vendor_role
    ai["vendor_required"] = "" if vendor_role == "Society Manager" else vendor_role
    ai["source_of_truth"] = "ai"
    return ai
