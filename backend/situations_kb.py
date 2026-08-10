import os, json, re, logging
from difflib import SequenceMatcher

logger = logging.getLogger("propto.kb")
_CACHE = os.path.join(os.path.dirname(__file__), "data", "situations.json")
_XLSX = "https://customer-assets-lxgj4vgw.emergentagent.net/job_complaint-whatsapp/artifacts/bwsivtl5_Issues.xlsx"
_ITEMS = None
_STOP = {"the", "a", "an", "is", "in", "my", "of", "to", "and", "for", "on", "at",
         "there", "no", "not", "flat", "our", "we", "it", "this", "that", "are", "with"}


def _prio(p):
    p = (p or "").lower()
    if "critical" in p:
        return "Critical"
    if "high" in p:
        return "High"
    if "medium" in p:
        return "Medium"
    return "Low"


# Map granular Excel categories -> the app's 11-category enum (for vendor routing/analytics)
_CAT_MAP = {
    "Power / Electricity": "Electrical",
    "Voltage / Electrical Damage": "Electrical",
    "Generator / DG Backup": "DG Set",
    "Plumbing / Leakage": "Plumbing",
    "STP / Sewage / Drainage": "Plumbing",
    "Hot Water / Solar": "Plumbing",
    "Water Supply": "Water Supply",
    "Water Quality / TDS": "Water Supply",
    "Lift / Elevator": "Lift",
    "Security / CCTV / Theft": "Security",
    "Gate Access / Deliveries": "Security",
    "Fire Safety / Smoke": "Security",
    "Health / Safety / Emergency": "Security",
    "Gas Pipeline": "Security",
    "Garbage / Housekeeping": "Housekeeping",
    "Staff / Vendor / Service Quality": "Housekeeping",
    "Common Area / Terrace / Structure": "Civil",
    "Roads / External Works / Landscaping": "Civil",
    "Noise / Construction": "Civil",
    "Amenities / Clubhouse / Pool / Gym": "Civil",
    "Parking": "Parking",
    "Pest / Insects / Animals": "Pest Control",
    "Communication / Notices / Governance": "Civil",
    "Finance / Billing / Collections": "Civil",
    "Resident Behavior / Rule Violation": "Security",
}


def _app_cat(c):
    return _CAT_MAP.get((c or "").strip(), "Civil")


def _tokens(s):
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split() if len(w) > 2 and w not in _STOP}


def _load():
    global _ITEMS
    if _ITEMS is not None:
        return _ITEMS
    try:
        if os.path.exists(_CACHE):
            with open(_CACHE) as f:
                _ITEMS = json.load(f)
        else:
            import pandas as pd
            # Excel has NO header row: [row#, Category, Sub-category, Situation, Priority, Time-window]
            df = pd.read_excel(_XLSX, header=None)
            items = []
            for _, r in df.iterrows():
                situation = str(r[3]).strip()
                if not situation or situation.lower() == "nan":
                    continue
                # skip the accidental header-like first row if present
                if situation.lower() == "situation":
                    continue
                items.append({
                    "situation": situation,
                    "category": str(r[1]).strip(),
                    "sub_category": str(r[2]).strip(),
                    "priority": _prio(str(r[4])),
                })
            os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
            with open(_CACHE, "w") as f:
                json.dump(items, f)
            _ITEMS = items
        # precompute tokens
        for it in _ITEMS:
            it.setdefault("_tok", list(_tokens(it["situation"])))
    except Exception as e:
        logger.warning("KB load failed: %s", e)
        _ITEMS = []
    return _ITEMS


def match(text: str, threshold: float = 0.6):
    """Return best-matching KB situation dict (with 'score' and 'app_category') or None."""
    items = _load()
    if not items or not text:
        return None
    tw = _tokens(text)
    tl = text.lower()
    best, best_score = None, 0.0
    for it in items:
        sit = it["situation"].lower()
        it_tok = set(it.get("_tok") or _tokens(it["situation"]))
        # containment: fraction of situation keywords present in the message
        overlap = (len(tw & it_tok) / len(it_tok)) if it_tok else 0.0
        ratio = SequenceMatcher(None, tl, sit).ratio()
        score = max(overlap, ratio)
        if score > best_score:
            best, best_score = it, score
    if best and best_score >= threshold:
        out = {k: v for k, v in best.items() if k != "_tok"}
        out["app_category"] = _app_cat(best["category"])
        out["kb_category"] = best["category"]
        out["score"] = round(best_score, 2)
        return out
    return None
