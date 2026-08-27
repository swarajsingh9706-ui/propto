"""Unit-level checks for the graceful-degradation fix in ai_engine._call_llm
(self-host case: no GEMINI_API_KEY and emergentintegrations unavailable)."""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")

import ai_engine  # noqa: E402


def test_call_llm_returns_empty_when_no_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    out = asyncio.run(ai_engine._call_llm("water leak"))
    assert out == ""


def test_call_llm_returns_empty_when_emergent_import_fails(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test-invalid")
    # simulate emergentintegrations not installed (self-host)
    monkeypatch.setitem(sys.modules, "emergentintegrations.llm.chat", None)
    out = asyncio.run(ai_engine._call_llm("water leak"))
    assert out == ""


def test_call_llm_returns_empty_when_gemini_key_invalid(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "invalid-key-xyz")
    out = asyncio.run(ai_engine._call_llm("water leak"))
    assert out == ""


def test_analyze_message_no_llm_does_not_raise(monkeypatch):
    """Excel taxonomy path should still work / and unknown text must not raise with no LLM."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    res = asyncio.run(ai_engine.analyze_message("qwerty zxcvb asdf no idea complaint problem"))
    assert isinstance(res, dict)
    assert "intent" in res
