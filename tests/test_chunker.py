from src import config
from src.ingestion.chunker import chunk_act


def test_empty_returns_empty():
    assert chunk_act("", "32016R0679") == []
    assert chunk_act("   \n  \n", "32016R0679") == []


def _act_text(n_articles: int = 3, body_repeat: int = 1) -> str:
    header = (
        "25.5.2016 EN Official Journal L 135/1\n"
        "REGULATION (EU) 2016/679 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL\n"
        "on the protection of natural persons with regard to processing of personal data.\n"
        "WHEREAS:\n"
        "(1) The protection of natural persons is a fundamental right of the Union.\n"
        "(2) Personal data should be processed lawfully fairly and in a transparent manner.\n"
        "(3) Member states shall ensure that controllers and processors are accountable.\n"
    )
    arts = ""
    for i in range(1, n_articles + 1):
        arts += (
            f"Article {i}\n"
            f"Subject matter and scope. This Article sets out obligation number {i}. "
            f"The member states shall ensure that this Article is "
            f"fully applied within their territory. "
            * body_repeat
        ) + "\n"
    return header + arts


def test_chunks_have_consistent_metadata():
    chunks = chunk_act(_act_text(n_articles=3), "32016R0679")
    assert len(chunks) >= 3  # preamble + >=1 per article-ish region
    ids = [c.chunk_id for c in chunks]
    assert all(i.startswith("32016R0679#") for i in ids)
    idxs = [c.chunk_index for c in chunks]
    assert idxs == list(range(len(chunks)))  # sequential, zero-based
    assert all(c.celex == "32016R0679" for c in chunks)


def test_article_boundaries_detected():
    chunks = chunk_act(_act_text(n_articles=4, body_repeat=1), "32016R0679")
    article_chunks = [c for c in chunks if c.boundary.startswith("Article")]
    # one body per article, each well below ceiling -> each should be its own Article chunk
    assert {c.boundary for c in article_chunks} == {
        "Article 1",
        "Article 2",
        "Article 3",
        "Article 4",
    }


def test_recitals_merge_when_small():
    # Tiny recitals + the `WHEREAS:` line fold into the single Preamble chunk.
    chunks = chunk_act(_act_text(n_articles=2), "32016R0679")
    preamble = [c for c in chunks if c.boundary == "Preamble"]
    assert len(preamble) == 1
    body = preamble[0].chunk_text
    assert "(1)" in body and "(2)" in body and "WHEREAS" in body
    assert not [c for c in chunks if c.boundary.startswith("Recital")]


def test_recitals_split_when_large():
    # When each recital exceeds the min-token floor, they stay separate.
    long_sentence = (
        "The protection of natural persons with regard to the processing of "
        "personal data is a fundamental right which contributes to the "
        "preservation of the shared values of the member states of the Union "
    ) * 60
    text = (
        "WHEREAS:\n"
        f"(1) {long_sentence}\n"
        f"(2) {long_sentence}\n"
        f"(3) {long_sentence}\n"
        "Article 1 Subject matter This Regulation lays down the rules.\n"
    )
    chunks = chunk_act(text, "32016R0679")
    recital_labels = {c.boundary for c in chunks if c.boundary.startswith("Recital")}
    assert {"Recital 1", "Recital 2", "Recital 3"} <= recital_labels


def test_offsets_within_bounds_and_sorted():
    text = _act_text(n_articles=4, body_repeat=2)
    chunks = chunk_act(text, "32016R0679")
    for c in chunks:
        assert 0 <= c.char_offset_start < c.char_offset_end <= len(text)
        assert text[c.char_offset_start:c.char_offset_end].strip()  # non-empty slice
    starts = [c.char_offset_start for c in chunks]
    assert starts == sorted(starts)


def test_oversized_segment_window_split_with_overlap():
    # One giant article far above the ceiling -> must be window-split.
    body = "Article 1\n" + ("The member states shall apply this Regulation. " * 400)
    chunks = chunk_act(body, "32019R0001")
    assert len(chunks) > 1
    # Every fragment of this single article should carry a window/Article label
    assert all(c.boundary in ("Article 1", "window") for c in chunks)
    # Consecutive windows must overlap (shared suffix/prefix text)
    texts = [c.chunk_text for c in chunks]
    overlap_found = any(texts[i][-50:] in texts[i + 1] for i in range(len(texts) - 1))
    assert overlap_found


def test_no_article_anchors_falls_back_to_window():
    # An act body with no article markers: must still chunk (window / single Preamble).
    text = (
        "This regulation concerns technical measures for the conservation of marine "
        "ecosystems. The member states shall ensure that fishing is sustainable and that "
        "stocks are maintained at biologically safe levels. " * 50
    )
    chunks = chunk_act(text, "32018R2037")
    assert chunks
    for c in chunks:
        assert 0 <= c.char_offset_start < c.char_offset_end <= len(text)


def test_respects_max_token_ceiling_mostly():
    max_chars = config.CHUNK_MAX_TOKENS * config.CHARS_PER_TOKEN
    text = "Article 1\n" + ("Member states shall apply this. " * 1000)
    chunks = chunk_act(text, "32019R0001")
    # allow small overshoot from line-snapping, but never double the ceiling
    for c in chunks:
        assert len(c.chunk_text) <= max_chars * 1.3
