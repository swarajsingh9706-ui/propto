"""Propto Issue Taxonomy v3 matcher: safety override -> object+problem -> problem only -> object only."""
import os, re, json

_PATH = os.path.join(os.path.dirname(__file__), "data", "taxonomy_v3.json")
_T = None
_TYPE_RANK = {"Subject": 0, "Equipment / structure": 1, "Place / person": 2}
_IN_HOUSE = ("society", "treasurer", "committee", "facility manager", "admin")

# New v3 category -> one of the existing 11 vendor categories (vendors keep old tags).
VENDOR_CATEGORY = {
    "Medical & Emergency": "Security", "Fire Safety": "Security", "Gas Supply": "Plumbing",
    "Lift": "Lift", "Swimming Pool": "Pool AMC Vendor", "DG, Inverter & Solar": "DG Set",
    "AC & Ventilation": "Electrical", "Electrical": "Electrical", "Water Supply": "Water Supply",
    "Plumbing & Leakage": "Plumbing", "Drainage & Sewage": "Plumbing", "Seepage & Waterproofing": "Civil",
    "Civil & Structural": "Civil", "Renovation & Construction": "Civil", "Pest Control": "Pest Control",
    "Stray Animals & Pets": "Security", "Security & Gate": "Security", "Parking": "Parking",
    "Garbage & Waste": "Housekeeping", "Housekeeping & Cleaning": "Housekeeping",
    "Internet, TV & Intercom": "Electrical", "Amenities & Clubhouse": "Civil",
    "Garden & Landscaping": "Gardening", "Noise, Nuisance & Disputes": "Security",
    "Staff & Domestic Help": "Housekeeping", "Billing & Accounts": "Civil",
    "Society Admin & Documents": "Civil", "General / Unclassified": "Civil",
}


def _load():
    global _T
    if _T is None:
        with open(_PATH) as f:
            _T = json.load(f)
        vocab = []  # (phrase, kind, ref)
        for s in _T["safety"]:
            vocab += [(w, "safety", s) for w in s["words"]]
        for o in _T["objects"]:
            vocab += [(w, "object", o) for w in o["words"]]
            vocab += [(ph, "shortcut", (o, pr)) for ph, pr in o["shortcuts"].items()]
        for p in _T["problems"]:
            vocab += [(w, "problem", p) for w in p["words"]]
        for loc in _T["locations"]:
            vocab += [(w, "location", loc) for w in loc["words"]]
        vocab.sort(key=lambda v: -len(v[0]))
        _T["_vocab"] = [(re.compile(r"(?<![a-z0-9])" + re.escape(ph) + r"(?:s|es)?(?![a-z0-9])"), kind, ref)
                        for ph, kind, ref in vocab]
    return _T


def _hits(text):
    t = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    taken, hits = [False] * (len(t) + 1), []
    for rx, kind, ref in _load()["_vocab"]:
        for m in rx.finditer(t):
            if any(taken[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                taken[i] = True
            hits.append((kind, ref, m.start()))
    return hits


def _result(line_id, decided_by, location):
    T = _load()
    ln = T["lines"].get(line_id)
    if not ln:
        return None
    owner = ln["owner"] or T["categories"].get(ln["category"], {}).get("owner", "")
    in_house = any(k in owner.lower() for k in _IN_HOUSE)
    return {"issue_id": line_id, "issue_line": ln["line"], "label": ln["label"], "category": ln["category"],
            "severity": ln["severity"], "sla": ln["sla"], "owner": owner, "action": ln["action"],
            "manager_alert": "Manager Alert" in ln["action"], "decided_by": decided_by, "location": location,
            "handled_by": "Society Manager" if in_house else owner, "vendor_required": "" if in_house else owner,
            "vendor_category": VENDOR_CATEGORY.get(ln["category"], "Civil")}


def match(text: str):
    """Returns the matched issue line dict, or None when nothing is recognised."""
    T = _load()
    hits = _hits(text)
    location = next((r["name"] for k, r, _ in hits if k == "location"), "")
    safety = sorted((r for k, r, _ in hits if k == "safety"), key=lambda s: s["order"])
    if safety:
        return _result(safety[0]["line"], "Safety override", location)

    objs = [(r, pos) for k, r, pos in hits if k == "object"]
    probs = [(r["name"], pos, r) for k, r, pos in hits if k == "problem"]
    def cat_prio(o):
        return T["categories"].get(o["category"], {}).get("priority", 99)

    # Shortcut phrases ("pipe burst", "load shedding") name object+problem explicitly and win.
    for k, r, pos in hits:
        if k == "shortcut":
            lid = T["line_map"].get(f"{r[0]['name']}|{r[1]}")
            if lid:
                return _result(lid, "Object + problem", location)
            objs.append((r[0], pos))

    pairs = []
    for o, opos in objs:
        for pname, ppos, _ in probs:
            lid = T["line_map"].get(f"{o['name']}|{pname}")
            if lid:
                pairs.append((_TYPE_RANK.get(o["type"], 3), cat_prio(o), abs(opos - ppos), lid))
    if pairs:
        return _result(sorted(pairs)[0][3], "Object + problem", location)

    for _, _, p in sorted(probs, key=lambda x: x[1]):
        if p and p.get("fallback_line"):
            return _result(p["fallback_line"], "Problem only", location)

    if objs:
        o = sorted(objs, key=lambda x: (_TYPE_RANK.get(x[0]["type"], 3), cat_prio(x[0])))[0][0]
        return _result(o["default_line"], "Object only", location)
    return None


def has_complaint_signal(text: str) -> bool:
    """Taxonomy-level complaint evidence: a safety word, an object+problem pair or a problem with its own line."""
    m = match(text)
    return bool(m and m["decided_by"] != "Object only")
