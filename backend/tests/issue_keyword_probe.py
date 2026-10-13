import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
import ai_engine as a

# (text, expected_complaint, expected_category)
CASES = [
    ("wokring on it rn", False, ""),
    ("working on it rn", False, ""),
    ("on my way", False, ""),
    ("will check and update", False, ""),
    ("electrician is coming in 10 mins", False, ""),
    ("ok done", False, ""),
    ("plumber reached", False, ""),
    ("good morning everyone", False, ""),
    ("swimming pool issue is resolved", False, ""),
    ("thanks, the water problem is fixed now", False, ""),
    ("lift is working now", False, ""),
    ("meeting at 6pm in clubhouse", False, ""),
    ("water issue in my flat", True, "Plumbing"),
    ("water issue still not resolved", True, "Plumbing"),
    ("no power in B-302", True, "Electrical"),
    ("electricity gone in tower A since morning", True, "Electrical"),
    ("corridor light not working on 4th floor", True, "Electrical"),
    ("fan stopped working in my flat", True, "Electrical"),
    ("power cut again", True, "Electrical"),
    ("lift stuck at 5th floor", True, "Lift"),
    ("tap leaking in kitchen", True, "Plumbing"),
    ("garbage not collected since 2 days", True, "Housekeeping"),
    ("cockroach infestation in basement", True, "Pest Control"),
    ("crack in my bedroom wall", True, "Civil"),
    ("someone parked in my parking slot again, problem every day", True, "Parking"),
]


def fake_ai(expected, llm_ok, certainty):
    return {"intent": "Complaint" if expected else "NotComplaint", "_llm_ok": llm_ok,
            "certainty": certainty, "confidence": 0.9 if expected else 0.1, "category": ""}


async def main(live: bool):
    fails = 0
    for text, exp, exp_cat in CASES:
        # Worst cases: AI says the WRONG thing with low certainty, or AI is down.
        for label, ai in [("ai_wrong_unsure", fake_ai(not exp, True, 0.5)), ("ai_down", fake_ai(False, False, 0))]:
            got, reason = a.decide_intent(text, ai)
            # AI wrongly saying Complaint on a non-complaint is only blocked for status/resolved phrases.
            if label == "ai_wrong_unsure" and not exp and ai["intent"] == "Complaint" and reason == "ai":
                continue
            if got != exp:
                fails += 1
                print(f"FAIL [{label}] {text!r} -> {got} ({reason})")
        if exp:
            cat = a.keyword_category(text)
            if cat != exp_cat:
                fails += 1
                print(f"FAIL [category] {text!r} -> {cat} (expected {exp_cat})")
        if live:
            res = await a.analyze_message(text)
            ok = (res["intent"] == "Complaint") == exp and (not exp or res["category"] == exp_cat)
            fails += 0 if ok else 1
            print(f"{'OK ' if ok else 'FAIL'} [live] {text!r:62} -> {res['intent']:13} {res.get('category','')!s:13} {res.get('decision_reason')}")
    print("FAILURES:", fails)


if __name__ == "__main__":
    asyncio.run(main("--live" in sys.argv))
