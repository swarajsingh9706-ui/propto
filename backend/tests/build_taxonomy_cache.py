"""Regenerate backend/data/taxonomy.json from the local xlsx (no network needed)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import situations_kb as kb

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/new_taxonomy.xlsx"
df = pd.read_excel(SRC, sheet_name=kb._SHEET, header=0)
items = kb._parse_df(df)
os.makedirs(os.path.dirname(kb._CACHE), exist_ok=True)
with open(kb._CACHE, "w") as f:
    json.dump(items, f)
print("cached", len(items), "items ->", kb._CACHE)
# quick stats
vend = sum(1 for i in items if i["handled_by"] != "Society Manager")
print("vendor-routed:", vend, "| in-house (Society Manager):", len(items) - vend)
