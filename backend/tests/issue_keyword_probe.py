from dotenv import load_dotenv; load_dotenv()
import ai_engine as a

cases = [
    ("water issue in my flat", True),
    ("swimming pool issue is resolved", False),
    ("lift problem again", True),
    ("water issue still not resolved", True),
    ("thanks, the water problem is fixed now", False),
    ("good morning everyone", False),  # greeting -> no keyword
]
for text, expect_signal in cases:
    kw, cat = a.strong_keyword_hit(text)
    resolved = a.is_resolved_context(text)
    would_override = kw and not resolved
    print(f"{text!r:55} kw={kw!s:5} resolved={resolved!s:5} -> override_to_complaint={would_override} (expect {expect_signal})")
