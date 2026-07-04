
from src.generation import citation_formatter as cf


def test_extract_canonical_celex():
    txt = "See 32016R0679 and 32013R0098 for details. Also 31987L0362."
    # normalised to year+type+serial, sector digit stripped
    assert cf.extract_celex_numbers(txt) == ["2016R0679", "2013R0098", "1987L0362"]


def test_extract_dedupes():
    txt = "32016R0679 then 32016R0679 again"
    assert cf.extract_celex_numbers(txt) == ["2016R0679"]


def test_extract_prose_eu_year_serial():
    txt = "Regulation (EU) 2016/679 and Council (EC) No 98/2013 apply."
    found = cf.extract_celex_numbers(txt)
    assert "2016R0679" in found
    assert "2013R0098" in found


def test_extract_canonical_and_prose_normalise_equal():
    # canonical and prose citations of the same act must compare equal
    assert cf.extract_celex_numbers("32016R0679") == cf.extract_celex_numbers(
        "Regulation (EU) 2016/679"
    )
    assert cf.extract_celex_numbers("32013R0098") == cf.extract_celex_numbers("(EU) No 98/2013")


def test_extract_empty():
    assert cf.extract_celex_numbers("") == []
    assert cf.extract_celex_numbers("no citations here") == []


def test_build_sources_dedupes_by_celex_and_preserves_order():
    chunks = [
        {"text": "aaaa", "metadata": {"celex": "32016R0679", "act_name": "GDPR",
         "status": "In Force", "eurlex_link": "http://e/1"}},
        {"text": "bbbb", "metadata": {"celex": "32016R0679", "act_name": "GDPR",
         "status": "In Force", "eurlex_link": "http://e/1"}},
        {"text": "cccc", "metadata": {"celex": "32019R1241", "act_name": "Tech",
         "status": "In Force", "eurlex_link": "http://e/2"}},
    ]
    srcs = cf.build_sources(chunks)
    assert [s["celex"] for s in srcs] == ["32016R0679", "32019R1241"]
    assert srcs[0]["chunk_excerpt"] == "aaaa"
    assert srcs[0]["link"] == "http://e/1"


def test_build_sources_skips_missing_celex():
    chunks = [
        {"text": "x", "metadata": {"celex": "", "act_name": "n"}},
        {"text": "y", "metadata": {"celex": None, "act_name": "n"}},
    ]
    assert cf.build_sources(chunks) == []


def test_build_sources_excerpt_truncated_to_240():
    long = "z" * 500
    chunks = [{"text": long, "metadata": {"celex": "32016R0679", "act_name": "g",
             "status": "In Force", "eurlex_link": "u"}}]
    srcs = cf.build_sources(chunks)
    assert len(srcs[0]["chunk_excerpt"]) == 240


def test_grounding_pass_when_answer_celex_in_context():
    ans = "GDPR (32016R0679) applies."
    chunks = [{"metadata": {"celex": "32016R0679"}, "text": "..."}]
    g = cf.check_grounding(ans, chunks)
    assert g.grounded is True
    assert g.ungrounded == []
    assert g.answer_celex == ["2016R0679"]
    assert g.context_celex == ["32016R0679"]  # raw canonical preserved for display


def test_grounding_pass_prose_citation_matches_canonical_context():
    ans = "Regulation (EU) 2016/679 applies."
    chunks = [{"metadata": {"celex": "32016R0679"}, "text": "..."}]
    g = cf.check_grounding(ans, chunks)
    assert g.grounded is True


def test_grounding_flags_hallucinated_celex():
    ans = "GDPR (32016R0679) and the imaginary 31999R9999 apply."
    chunks = [{"metadata": {"celex": "32016R0679"}, "text": "..."}]
    g = cf.check_grounding(ans, chunks)
    assert g.grounded is False
    assert "1999R9999" in g.ungrounded


def test_grounding_answer_with_no_celex_is_grounded():
    g = cf.check_grounding("No citations.", [{"metadata": {"celex": "32016R0679"}}])
    assert g.grounded is True
    assert g.answer_celex == []
