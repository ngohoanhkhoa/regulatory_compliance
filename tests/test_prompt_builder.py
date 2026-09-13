import pytest

from src.generation import prompt_builder as pb


def test_build_context_block_empty():
    s = pb.PromptBuilder.__new__(pb.PromptBuilder)
    s._cached = None
    s._path = None
    assert "No context" in s.build_context_block([])


def test_build_context_block_formats_chunks():
    b = pb.PromptBuilder.__new__(pb.PromptBuilder)
    b._cached = None
    b._path = None
    chunks = [
        {
            "text": "Article 1 subject matter scope of regulation.",
            "metadata": {
                "celex": "32016R0679",
                "act_name": "GDPR",
                "status": "In Force",
                "temporal_status": "",
                "eurlex_link": "http://e/1",
            },
        }
    ]
    out = b.build_context_block(chunks)
    assert "celex=32016R0679" in out
    assert "act_name=GDPR" in out
    assert "status=In Force" in out
    assert "link=http://e/1" in out
    assert "Article 1 subject matter scope of regulation." in out
    assert "[CHUNK 0]" in out


def test_build_messages_structure(tmp_path):
    p = tmp_path / "sp.md"
    p.write_text("SYSTEM BODY HERE.")
    b = pb.PromptBuilder(system_prompt_path=p)
    msgs = b.build_messages("Is GDPR in force?", [{"text": "x", "metadata": {}}])
    assert msgs[0]["role"] == "system"
    assert "SYSTEM BODY HERE." in msgs[0]["content"]
    assert "CONTEXT" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "Is GDPR in force?"


def test_build_messages_language_instruction(tmp_path):
    p = tmp_path / "sp.md"
    p.write_text("SYSTEM BODY HERE.")
    b = pb.PromptBuilder(system_prompt_path=p)
    for code, name in (("en", "English"), ("fr", "French"), ("vi", "Vietnamese")):
        msgs = b.build_messages("Q", [], language=code)
        assert f"Write the entire answer in {name}" in msgs[0]["content"]
    # Unknown / missing language defaults to English.
    assert "in English" in b.build_messages("Q", [])[0]["content"]
    assert "in English" in b.build_messages("Q", [], language="de")[0]["content"]


def test_build_messages_empty_question_raises(tmp_path):
    p = tmp_path / "sp.md"
    p.write_text("x")
    b = pb.PromptBuilder(system_prompt_path=p)
    with pytest.raises(ValueError):
        b.build_messages("   ", [])


def test_missing_prompt_raises(tmp_path):
    b = pb.PromptBuilder(system_prompt_path=tmp_path / "nope.md")
    with pytest.raises(FileNotFoundError):
        _ = b.system_prompt_body
