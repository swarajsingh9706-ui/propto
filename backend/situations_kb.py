import os, json, re, logging
from difflib import SequenceMatcher

logger = logging.getLogger("propto.kb")
_CACHE = os.path.join(os.path.dirname(__file__), "data", "taxonomy.json")
_XLSX = "https://customer-assets-lxgj4vgw.emergentagent.net/job_complaint-whatsapp/artifacts/52wrowf2_Propto_Taxonomy_1000.xlsx"
_SHEET = "Taxonomy (All)"
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


# Map the 41 taxonomy categories (number prefix stripped) -> app's vendor-routing enum
_CAT_MAP = {
    "Water Supply": "Water Supply",
    "Water Quality / Sanitation": "Water Supply",
    "Plumbing / Leakage": "Plumbing",
    "Electrical / Power": "Electrical",
    "Generator / DG Set": "DG Set",
    "Lift / Elevator": "Lift",
    "Hot Water / Solar": "Plumbing",
    "HVAC / Ventilation": "Electrical",
    "Gas Pipeline": "Security",
    "Fire & Safety": "Security",
    "Lighting": "Electrical",
    "Housekeeping / Cleaning": "Housekeeping",
    "Garbage / Waste": "Housekeeping",
    "Pest Control": "Pest Control",
    "Security / Access": "Security",
    "CCTV / Surveillance": "Security",
    "Parking / Vehicles": "Parking",
    "Structural / Civil": "Civil",
    "Carpentry / Fittings": "Civil",
    "Amenities / Clubhouse": "Civil",
    "Sewage / STP / Drainage": "Plumbing",
    "Deliveries / Visitor": "Security",
    "Noise / Nuisance": "Civil",
    "Community / Governance": "Civil",
    "Appliances / Misc Assets": "Electrical",
    "Occupancy & Move Management": "Civil",
    "Amenity Administration": "Civil",
    "Communication & Information": "Civil",
    "Bills & Payments": "Civil",
    "Legal & Regulatory Compliance": "Civil",
    "Finance, Budget & Audit": "Civil",
    "Society Staff & HR": "Civil",
    "Events & Community Engagement": "Civil",
    "Sustainability, Energy & Water": "Civil",
    "Insurance & Risk": "Civil",
    "Technology & Smart Systems": "Electrical",
    "Health & Medical Emergency": "Security",
    "Redevelopment & Major Works": "Civil",
    "Accessibility & Vulnerable Residents": "Civil",
    "Monsoon & Seasonal": "Civil",
    "Records & Documentation": "Civil",
}


def _app_cat(c):
    return _CAT_MAP.get((c or "").strip(), "Civil")


def _strip_cat(c):
    return re.sub(r"^\s*\d+\.\s*", "", str(c or "").strip())


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
            df = pd.read_excel(_XLSX, sheet_name=_SHEET, header=0)
            df.columns = [str(c).strip() for c in df.columns]
            items = []
            for _, r in df.iterrows():
                sub = str(r.get("Subcategory", "")).strip()
                if not sub or sub.lower() in ("nan", "subcategory"):
                    continue
                cat = _strip_cat(r.get("Category"))
                items.append({
                    "subcategory": sub,
                    "category": cat,
                    "priority": _prio(str(r.get("Severity"))),
                    "vendor_required": str(r.get("Vendor Required", "")).strip(),
                    "handled_by": str(r.get("Handled By", "")).strip(),
                    "app_category": _app_cat(cat),
                })
            os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
            with open(_CACHE, "w") as f:
                json.dump(items, f)
            _ITEMS = items
        for it in _ITEMS:
            it.setdefault("_tok", list(_tokens(it["subcategory"])))
    except Exception as e:
        logger.warning("Taxonomy load failed: %s", e)
        _ITEMS = []
    return _ITEMS


def match(text: str, threshold: float = 0.6):
    """Match a message against the 1,000-row taxonomy (by Subcategory). Returns dict or None."""
    items = _load()
    if not items or not text:
        return None
    tw = _tokens(text)
    tl = text.lower()
    best, best_score = None, 0.0
    for it in items:
        sub = it["subcategory"].lower()
        it_tok = set(it.get("_tok") or _tokens(it["subcategory"]))
        overlap = (len(tw & it_tok) / len(it_tok)) if it_tok else 0.0
        ratio = SequenceMatcher(None, tl, sub).ratio()
        score = max(overlap, ratio)
        if score > best_score:
            best, best_score = it, score
    if best and best_score >= threshold:
        return {
            "subcategory": best["subcategory"],
            "sub_category": best["subcategory"],
            "situation": best["subcategory"],
            "category": best["category"],
            "priority": best["priority"],
            "vendor_required": best["vendor_required"],
            "handled_by": best["handled_by"],
            "app_category": best["app_category"],
            "kb_category": best["category"],
            "score": round(best_score, 2),
        }
    return None
