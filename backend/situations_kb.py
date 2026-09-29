import os, json, re, logging
from difflib import SequenceMatcher

logger = logging.getLogger("propto.kb")
_CACHE = os.path.join(os.path.dirname(__file__), "data", "taxonomy.json")
_XLSX = "https://customer-assets-lxgj4vgw.emergentagent.net/job_complaint-whatsapp/artifacts/jvybzgi9_Propto_Taxonomy.xlsx"
_SHEET = "Issue Taxonomy"
_ITEMS = None
_STOP = {"the", "a", "an", "is", "in", "my", "of", "to", "and", "for", "on", "at",
         "there", "no", "not", "flat", "our", "we", "it", "this", "that", "are", "with"}

# "Default Owner / Vendor" keywords that mean an EXTERNAL vendor handles it (route to vendor).
# Anything else (Admin, Committee, Manager, Accounts, Legal, Security desk, Supervisor)
# is handled in-house -> "Society Manager".
_VENDOR_KW = ("vendor", "contractor", "amc", "electrician", "plumber", "technician",
              "mseb", "wtp", "pool", "telecom", "equipment", "landscape", "pest control",
              "lift amc", "civil vendor", "utility vendor", "tech vendor", "carpenter",
              "mason", "painter", "stp vendor", "agency", "fabricator", "mechanic")


def _prio(p):
    p = (p or "").lower()
    if "critical" in p:
        return "Critical"
    if "high" in p:
        return "High"
    if "medium" in p:
        return "Medium"
    return "Low"


def _tokens(s):
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split() if len(w) > 2 and w not in _STOP}


def _app_cat(category, issue, owner):
    """Map a taxonomy row -> the app's vendor-routing enum (matches demo vendor categories)."""
    s = f"{category} {issue} {owner}".lower()
    if any(k in s for k in ("lift", "elevator")):
        return "Lift"
    if any(k in s for k in ("dg set", "dg ", "generator", "diesel")):
        return "DG Set"
    if any(k in s for k in ("pest", "cockroach", "mosquito", "termite", "rodent", "rat ", "insect")):
        return "Pest Control"
    if any(k in s for k in ("garden", "landscape", "lawn", "horticulture", "plant")):
        return "Gardening"
    if any(k in s for k in ("parking", "vehicle", "car park")):
        return "Parking"
    if any(k in s for k in ("security", "cctv", "surveillance", "access", "visitor", "gate",
                            "intercom", "fire", "gas leak", "guard", "theft")):
        return "Security"
    if any(k in s for k in ("housekeep", "garbage", "waste", "cleaning", "sweep", "chute", "trash", "litter")):
        return "Housekeeping"
    if any(k in s for k in ("electric", "power", "wiring", "mcb", "switch", "socket", "light",
                            "fuse", "transformer", "meter", "hvac", "air condition", "ac ")):
        return "Electrical"
    if any(k in s for k in ("plumb", "water", "leak", "seepage", "drain", "sewage", "stp", "tap",
                            "pipe", "ro plant", "flush", "toilet", "overflow", "tank", "sanitation")):
        return "Plumbing"
    if any(k in s for k in ("civil", "crack", "wall", "paint", "tile", "plaster", "ceiling",
                            "carpentry", "structure", "facade", "balcony", "waterproof", "seepage")):
        return "Civil"
    return "Civil"


def _owner_split(owner):
    """Return (handled_by, vendor_required). Vendor-owned -> route to vendor; else in-house."""
    o = (owner or "").strip()
    if o and any(k in o.lower() for k in _VENDOR_KW):
        return o, o
    return "Society Manager", ""


def _parse_df(df):
    df.columns = [str(c).strip() for c in df.columns]
    items = []
    for _, r in df.iterrows():
        issue = str(r.get("Issue / Problem", "")).strip()
        if not issue or issue.lower() == "nan":
            continue
        cat = str(r.get("Category", "")).strip()
        sub = str(r.get("Subcategory", "")).strip()
        if sub.lower() == "nan":
            sub = ""
        owner = str(r.get("Default Owner / Vendor", "")).strip()
        if owner.lower() == "nan":
            owner = ""
        handled_by, vendor_required = _owner_split(owner)
        items.append({
            "issue": issue,
            "subcategory": sub,
            "category": cat,
            "priority": _prio(str(r.get("Severity"))),
            "owner": owner,
            "vendor_required": vendor_required,
            "handled_by": handled_by,
            "app_category": _app_cat(cat, issue, owner),
            "_tok": list(_tokens(issue + " " + sub)),
        })
    return items


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
            _ITEMS = _parse_df(df)
            os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
            with open(_CACHE, "w") as f:
                json.dump(_ITEMS, f)
        for it in _ITEMS:
            it["_tok_set"] = set(it.get("_tok") or _tokens(it["issue"] + " " + it.get("subcategory", "")))
    except Exception as e:
        logger.warning("Taxonomy load failed: %s", e)
        _ITEMS = []
    return _ITEMS


def match(text: str, threshold: float = 0.6):
    """Match a message against the 10,000-row taxonomy (by Issue/Problem). Returns dict or None.
    Token overlap is computed for all rows (fast set intersection); the fuzzy ratio is only
    computed for rows that share at least one token, keeping matching quick at 10k rows."""
    items = _load()
    if not items or not text:
        return None
    tw = _tokens(text)
    if not tw:
        return None
    tl = text.lower()
    best, best_score = None, 0.0
    for it in items:
        it_tok = it.get("_tok_set")
        if not it_tok:
            continue
        inter = len(tw & it_tok)
        if not inter:
            continue
        overlap = inter / len(it_tok)
        ratio = SequenceMatcher(None, tl, it["issue"].lower()).ratio()
        score = overlap if overlap > ratio else ratio
        if score > best_score:
            best, best_score = it, score
    if best and best_score >= threshold:
        return {
            "subcategory": best["subcategory"],
            "sub_category": best["subcategory"],
            "situation": best["issue"],
            "issue": best["issue"],
            "category": best["category"],
            "priority": best["priority"],
            "vendor_required": best["vendor_required"],
            "handled_by": best["handled_by"],
            "owner": best["owner"],
            "app_category": best["app_category"],
            "kb_category": best["category"],
            "score": round(best_score, 2),
        }
    return None
