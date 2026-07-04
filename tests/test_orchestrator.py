
from src.generation import orchestrator as orch


class FakeLLM:
    def __init__(self, text="here is the answer"):
        self.text = text
        self.calls = []

    def complete(self, messages, **kw):
        self.calls.append(messages)
        from src.generation.llm_client import LLMResponse
        return LLMResponse(text=self.text, model="deepseek-v4-flash")


def test_answer_question_returns_schema(monkeypatch):
    retrieved = [
        {
            "text": "Article 1 subject matter.",
            "metadata": {
                "celex": "32016R0679",
                "act_name": "GDPR",
                "status": "In Force",
                "temporal_status": "",
                "eurlex_link": "http://e/1",
            },
            "chunk_id": "32016R0679#0000",
            "score": 0.5,
            "rerank_score": 0.9,
        }
    ]
    llm = FakeLLM(text="Answer: GDPR (32016R0679) is in force.")
    out = orch.answer_question(
        "Is GDPR in force?", retrieved=retrieved, llm=llm
    )
    assert set(out.keys()) >= {"answer", "sources", "warnings", "disclaimer",
                               "grounded", "ungrounded_celex", "model"}
    assert out["answer"].startswith("Answer:")
    assert out["sources"][0]["celex"] == "32016R0679"
    assert out["grounded"] is True
    assert out["ungrounded_celex"] == []
    assert out["model"] == "deepseek-v4-flash"
    # dataset cutoff warning always present
    assert any("frozen at" in w for w in out["warnings"])
    assert "PROVISIONAL DISCLAIMER" in out["disclaimer"]


def test_warnings_include_not_in_force():
    retrieved = [
        {"text": "x", "metadata": {"celex": "32013R0098", "act_name": "old",
         "status": "Not in Force", "temporal_status": "2019-01-01",
         "eurlex_link": "u"}}
    ]
    llm = FakeLLM(text="Repealed act 32013R0098 mentioned.")
    out = orch.answer_question("q", retrieved=retrieved, llm=llm)
    assert any("Not in Force" in w for w in out["warnings"])


def test_grounding_warning_when_hallucinated():
    retrieved = [
        {"text": "x", "metadata": {"celex": "32016R0679", "act_name": "g",
         "status": "In Force", "eurlex_link": "u"}}
    ]
    llm = FakeLLM(text="Actually 31999R9999 is the relevant act.")
    out = orch.answer_question("q", retrieved=retrieved, llm=llm)
    assert out["grounded"] is False
    assert "1999R9999" in out["ungrounded_celex"]
    assert any("not present in retrieved context" in w for w in out["warnings"])


def test_no_sources_warning(monkeypatch):
    out = orch.answer_question("q", retrieved=[], llm=FakeLLM(text="I don't know."))
    assert any("No supporting sources" in w for w in out["warnings"])
    assert out["sources"] == []


def test_uses_retrieved_when_not_provided(monkeypatch):
    monkeypatch.setattr(
        "src.generation.orchestrator.hybrid_retriever.retrieve",
        lambda *a, **kw: [{"text": "x", "metadata": {"celex": "32016R0679",
         "act_name": "g", "status": "In Force", "eurlex_link": "u"}}],
    )
    out = orch.answer_question("q", llm=FakeLLM(text="ok"))
    assert out["sources"][0]["celex"] == "32016R0679"
