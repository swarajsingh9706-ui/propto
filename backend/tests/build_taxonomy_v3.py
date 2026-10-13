"""Compile data/Propto_Issue_Taxonomy_v3_2.xlsx -> data/taxonomy_v3.json (runtime cache)."""
import os, json, warnings
import pandas as pd

warnings.filterwarnings("ignore")
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
X = pd.ExcelFile(os.path.join(D, "Propto_Issue_Taxonomy_v3_2.xlsx"))


def words(s):
    return [w.strip().lower() for w in str(s or "").split(",") if w.strip() and str(s) != "nan"]


def val(v):
    return "" if pd.isna(v) else str(v).strip()


lines = {}
for r in X.parse("Issue Lines").to_dict("records"):
    if val(r["Issue ID"]):
        lines[val(r["Issue ID"])] = {
            "line": val(r["Issue Line"]), "category": val(r["Category"]), "severity": val(r["Severity"]),
            "sla": val(r["Target SLA"]), "owner": val(r["Default Vendor / Owner"]),
            "action": val(r["Propto Action"]), "label": val(r["Short Label (1-3 words)"]),
        }

categories = {}
for r in X.parse("Categories").to_dict("records"):
    if val(r["Category"]) and not pd.isna(r["Priority"]):
        categories[val(r["Category"])] = {"priority": int(r["Priority"]), "owner": val(r["Default Vendor / Owner"])}

objects = []
for r in X.parse("Objects").to_dict("records"):
    if not val(r["Object"]):
        continue
    shortcuts = {}
    for part in val(r["Shortcut phrases (phrase -> problem)"]).split(";"):
        if "->" in part:
            ph, pr = part.split("->", 1)
            shortcuts[ph.strip().lower()] = pr.strip()
    objects.append({"name": val(r["Object"]), "category": val(r["Category"]), "type": val(r["Type"]),
                    "words": words(r["Words that mean this object"]), "shortcuts": shortcuts,
                    "default_line": val(r["Issue ID"])})

problems = [{"name": val(r["Problem"]), "words": words(r["Words that mean this problem"]),
             "fallback_line": val(r["Issue ID"])}
            for r in X.parse("Problems").to_dict("records") if val(r["Problem"])]

safety = [{"order": int(r["Order"]), "words": words(r["Trigger words (beat everything else)"]), "line": val(r["Issue ID"])}
          for r in X.parse("Safety Overrides").to_dict("records") if not pd.isna(r["Order"])]

locations = [{"name": val(r["Location"]), "words": words(r["Words"])}
             for r in X.parse("Locations").to_dict("records") if val(r["Location"]) and val(r["Words"])]

line_map = {f"{val(r['Object'])}|{val(r['Problem'])}": val(r["Issue ID"])
            for r in X.parse("Line Map").to_dict("records") if val(r["Object"])}

tests = [{"msg": val(r["Resident message"]), "category": val(r["Expected category"]), "line": val(r["Issue line picked"])}
         for r in X.parse("Test Messages").to_dict("records") if not pd.isna(r["#"]) and val(r["Resident message"])]

out = {"lines": lines, "categories": categories, "objects": objects, "problems": problems,
       "safety": safety, "locations": locations, "line_map": line_map, "tests": tests}
with open(os.path.join(D, "taxonomy_v3.json"), "w") as f:
    json.dump(out, f, indent=1)
print({k: len(v) for k, v in out.items()})
