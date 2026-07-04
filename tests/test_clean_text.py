import pytest

from src.ingestion import clean_text


def test_fix_mojibake():
    assert clean_text.clean_text("cafÃ© rÃ©sumÃ©") == "café résumé"


def test_strip_html_tags_and_entities():
    out = clean_text.clean_text("Article 1 <b>scope</b> &amp; purpose &lt;x&gt;")
    assert "<b>" not in out and "&amp;" not in out
    assert "&" in out and "<x>" not in out
    assert "Article 1" in out


def test_normalizes_whitespace_and_control_chars():
    s = "line1\r\n\r\n\r\nline2   tail\x00\x07\tend"
    out = clean_text.clean_text(s)
    assert "\r" not in out
    assert "\x00" not in out and "\x07" not in out
    assert "   " not in out  # no triple spaces
    assert "\n\n\n" not in out  # collapsed multiline blanks


def test_empty_returns_empty_string():
    assert clean_text.clean_text("") == ""
    assert clean_text.clean_text(None) == ""  # type: ignore[arg-type]


def test_is_acceptable_rejects_empty_and_short():
    ok, reason = clean_text.is_acceptable("", min_chars=200)
    assert not ok and reason == "empty"
    ok, reason = clean_text.is_acceptable("short", min_chars=200)
    assert not ok and reason.startswith("too_short")


def test_is_acceptable_rejects_gibberish():
    gibber = "@#$%^ 12345 !@# 67890 %% @#$ *()_+ " * 30
    ok, reason = clean_text.is_acceptable(gibber, min_chars=50)
    assert not ok
    assert reason.startswith("gibberish")


def test_is_acceptable_rejects_non_english():
    # Pure Bulgarian/Cyrillic: letter ratio is high but no English stopwords.
    non_en = "Това е текст на български език за тестване на откриване на език. " * 20
    ok, reason = clean_text.is_acceptable(non_en, min_chars=200)
    assert not ok
    assert reason.startswith("not_english")


def test_is_acceptable_accepts_english_legal_text():
    legal = (
        "REGULATION (EU) 2016/679 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL "
        "on the protection of natural persons with regard to the processing of personal data. "
        "Article 1 Subject matter. This Regulation lays down rules relating to the protection "
        "of natural persons with regard to the processing of personal data by member states. "
    ) * 5
    ok, _ = clean_text.is_acceptable(legal, min_chars=200)
    assert ok


def test_clean_row_none():
    r = clean_text.clean_row(None)
    assert not r.accepted and r.text is None and r.reason == "empty"


def test_clean_row_short():
    r = clean_text.clean_row("hello")
    assert not r.accepted and r.reason and r.reason.startswith("too_short")


def test_clean_row_accepts_and_cleans():
    r = clean_text.clean_row("REGULATION (EU) … Article 1 the member states shall apply this " * 30)
    assert r.accepted and r.text and "Ã©" not in r.text


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
