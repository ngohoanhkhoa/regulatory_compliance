"""Tests for the intent router's deterministic fallback (no network)."""

from __future__ import annotations

from src.agents.intent_router import IntentRouter, _heuristic


def test_heuristic_greeting():
    assert _heuristic("Hello!") == "greeting"
    assert _heuristic("thanks") == "greeting"
    assert _heuristic("good morning") == "greeting"


def test_heuristic_explore():
    assert _heuristic("How many acts are there?") == "explore"
    assert _heuristic("list all regulations about data protection") == "explore"
    assert _heuristic("show me acts about AI") == "explore"


def test_heuristic_question():
    assert _heuristic("Is the GDPR still in force?") == "question"
    assert _heuristic("What obligations does the AML directive impose?") == "question"
    assert _heuristic("") == "question"


def test_router_without_key_uses_heuristic(monkeypatch):
    monkeypatch.setattr("src.agents.intent_router.config.OPENROUTER_API_KEY", None)
    router = IntentRouter()
    assert router.classify("How many acts are there?") == "explore"
    assert router.classify("Is the GDPR still in force?") == "question"
