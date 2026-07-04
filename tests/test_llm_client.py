
import httpx
import pytest

from src.generation import llm_client as lc


class FakeResp:
    def __init__(self, status_code, body=None, text="", headers=None):
        self.status_code = status_code
        self._body = body or {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._body


def _ok(text="ok", model="deepseek-v4-flash"):
    return FakeResp(
        200,
        body={"model": model, "choices": [{"message": {"content": text}}]},
    )


@pytest.fixture()
def patched_client(monkeypatch):
    """Build a client with a scripted post() sequence + no real sleeping."""
    def make(responses, *, max_retries=3, key="k"):
        calls = {"n": 0}
        sleeps = []

        def fake_post(url, headers, json, timeout):
            calls["n"] += 1
            r = responses[calls["n"] - 1]
            if isinstance(r, Exception):
                raise r
            return r

        monkeypatch.setattr(httpx, "post", fake_post)
        monkeypatch.setattr(lc.time, "sleep", lambda s: sleeps.append(s))
        monkeypatch.setattr(lc.config, "OPENCODE_GO_API_KEY", key)
        cli = lc.OpenCodeGoClient(api_key=key, max_retries=max_retries)
        return cli, calls, sleeps

    return make


def test_parse_ok_openai_shape():
    r = lc.OpenCodeGoClient._parse_ok(
        {"model": "m", "choices": [{"message": {"content": "hi"}}]}
    )
    assert r.text == "hi" and r.model == "m"


def test_parse_ok_bad_shape_raises():
    with pytest.raises(lc.LLMError):
        lc.OpenCodeGoClient._parse_ok({"choices": []})


def test_retry_after_parses():
    assert (
        lc.OpenCodeGoClient._retry_after_sec(
            FakeResp(429, headers={"retry-after": "120"})
        )
        == 120.0
    )
    assert lc.OpenCodeGoClient._retry_after_sec(FakeResp(500)) is None


def test_backoff_caps():
    assert lc.OpenCodeGoClient._backoff_sec(0) == 1.0
    assert lc.OpenCodeGoClient._backoff_sec(10) == 30.0


def test_init_without_key_raises(monkeypatch):
    monkeypatch.setattr(lc.config, "OPENCODE_GO_API_KEY", None)
    with pytest.raises(lc.LLMError, match="OPENCODE_GO_API_KEY"):
        lc.OpenCodeGoClient()


def test_429_raises_ratelimit_no_retry(patched_client):
    cli, calls, _ = patched_client([FakeResp(429, text="rl", headers={"retry-after": "300"})])
    with pytest.raises(lc.RateLimitError) as ei:
        cli.complete([{"role": "user", "content": "hi"}])
    assert "try again in 5 minutes" in str(ei.value)
    assert calls["n"] == 1  # no retry on 429


def test_4xx_raises_no_retry(patched_client):
    cli, calls, _ = patched_client([FakeResp(401, text="nope")])
    with pytest.raises(lc.LLMError, match="401"):
        cli.complete([{"role": "user", "content": "hi"}])
    assert calls["n"] == 1


def test_500_retries_then_succeeds(patched_client):
    cli, calls, sleeps = patched_client([FakeResp(500, text="boom"), _ok("done")])
    r = cli.complete([{"role": "user", "content": "hi"}])
    assert r.text == "done"
    assert calls["n"] == 2
    assert sleeps == [1.0]


def test_network_error_retries(patched_client):
    cli, calls, sleeps = patched_client(
        [httpx.ConnectError("x"), httpx.ConnectError("x"), _ok("done")],
        max_retries=5,
    )
    r = cli.complete([{"role": "user", "content": "hi"}])
    assert r.text == "done" and calls["n"] == 3
    assert sleeps == [1.0, 2.0]


def test_exhausts_retries_raises(patched_client):
    cli, calls, sleeps = patched_client(
        [FakeResp(500, text="x"), FakeResp(500, text="x"), FakeResp(500, text="x")],
        max_retries=2,
    )
    with pytest.raises(lc.LLMError, match="after 2 retries"):
        cli.complete([{"role": "user", "content": "hi"}])
    assert calls["n"] == 3
    assert sleeps == [1.0, 2.0]
