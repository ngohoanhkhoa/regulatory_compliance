"""Grounding + audit-trail tests (§9.3, §9.5, §10).

- Grounding eval: automated check that CELEX numbers in a generated answer
  exist in the retrieved context (catches hallucination, §10).
- Audit trail: verify that every query is logged with the right user, question,
  answer, and sources.
"""

from __future__ import annotations

from src.generation import citation_formatter as cf

# --- grounding eval cases (§10) -------------------------------------------- #

GROUNDING_CASES = [
    # (answer_text, context_celex_list, expected_grounded, expected_ungrounded)
    ("The GDPR (32016R0679) is in force.", ["32016R0679"], True, []),
    ("Regulation (EU) 2016/679 applies.", ["32016R0679"], True, []),  # prose cite
    ("Both 32016R0679 and 31999R9999 apply.", ["32016R0679"], False, ["1999R9999"]),
    ("No CELEX mentioned here.", ["32016R0679"], True, []),
    ("See (EU) No 98/2013 for details.", ["32013R0098"], True, []),  # No-style prose
    ("Council Regulation (EC) No 1005/2008", ["32008R1005"], True, []),
    ("32019R1241 was amended by 32019R1148.", ["32019R1241", "32019R1148"], True, []),
]


def test_grounding_eval_suite():
    """Every grounding case must agree with the expected outcome."""
    passed = 0
    for answer, ctx_celex, exp_grounded, exp_ungrounded in GROUNDING_CASES:
        chunks = [{"metadata": {"celex": c}, "text": "..."} for c in ctx_celex]
        g = cf.check_grounding(answer, chunks)
        assert g.grounded == exp_grounded, (
            f"answer={answer!r} expected grounded={exp_grounded} got {g.grounded}"
        )
        assert set(g.ungrounded) == set(exp_ungrounded), (
            f"answer={answer!r} expected ungrounded={exp_ungrounded} got {g.ungrounded}"
        )
        passed += 1
    assert passed == len(GROUNDING_CASES)


# --- audit trail ----------------------------------------------------------- #

def test_audit_trail_logged_correctly(tmp_path, monkeypatch):
    """§9.3: every query + answer + sources logged to the DB."""
    from src import config
    monkeypatch.setattr(config, "METADATA_DB_PATH", tmp_path / "audit.db")
    from src.auth import models
    monkeypatch.setattr(models, "DB_PATH", tmp_path / "audit.db")

    conn = models.get_db()
    uid = models.create_user(
        conn, username="audituser", hashed_password="fakehash", is_admin=False
    )
    qid = models.log_query(
        conn, user_id=uid, question="Is GDPR in force?",
        answer="Yes, 32016R0679 is in force.",
        sources=[{"celex": "32016R0679", "act_name": "GDPR"}],
        grounded=True, model="mock",
    )
    history = models.get_history(conn, uid)
    assert len(history) == 1
    entry = history[0]
    assert entry["id"] == qid
    assert entry["user_id"] == uid
    assert entry["question"] == "Is GDPR in force?"
    assert "32016R0679" in entry["answer"]
    assert entry["sources"][0]["celex"] == "32016R0679"
    assert entry["grounded"] is True
    assert entry["model"] == "mock"
    conn.close()


def test_audit_trail_isolated_per_user(tmp_path, monkeypatch):
    from src import config
    monkeypatch.setattr(config, "METADATA_DB_PATH", tmp_path / "audit2.db")
    from src.auth import models
    monkeypatch.setattr(models, "DB_PATH", tmp_path / "audit2.db")

    conn = models.get_db()
    u1 = models.create_user(conn, username="u1", hashed_password="h", is_admin=False)
    u2 = models.create_user(conn, username="u2", hashed_password="h", is_admin=False)
    _args = {"sources": [], "grounded": True, "model": "m"}
    models.log_query(conn, user_id=u1, question="Q1", answer="A1", **_args)
    models.log_query(conn, user_id=u2, question="Q2", answer="A2", **_args)
    models.log_query(conn, user_id=u1, question="Q3", answer="A3", **_args)
    assert len(models.get_history(conn, u1)) == 2
    assert len(models.get_history(conn, u2)) == 1
    conn.close()
