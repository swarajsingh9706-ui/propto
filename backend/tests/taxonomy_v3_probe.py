"""Runs the 'Test Messages' sheet of taxonomy v3 against taxonomy_v3.match()."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import taxonomy_v3 as tx

tests = tx._load()["tests"]
ok = 0
for t in tests:
    m = tx.match(t["msg"])
    got = m["category"] if m else "-"
    if got == t["category"]:
        ok += 1
    else:
        print(f"MISS {t['msg']!r:55} expected={t['category']!r} got={got!r} line={m and m['issue_line']!r} by={m and m['decided_by']}")
print(f"PASS {ok}/{len(tests)}")
