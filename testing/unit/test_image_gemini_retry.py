"""Retry behavior for the Gemini image endpoint.

Regression for the RG-0030 incident: a depleted-credits 429
(RESOURCE_EXHAUSTED, "prepayment credits are depleted") is NOT a transient
rate limit — backing off 5x wastes ~70s and then surfaces a vague "Too Many
Requests". It must fail fast with the actionable billing message. Ordinary
rate-limit 429s must still retry.
"""
import json
import pytest
from models import gemini_image
from models.gemini_image import _post_with_retry, GeminiAPIError


class FakeResp:
    def __init__(self, status, text="", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} Client Error")


_BILLING_BODY = json.dumps({"error": {
    "code": 429,
    "message": ("Your prepayment credits are depleted. Please go to AI Studio "
                "at https://ai.studio/projects to manage your project and billing."),
    "status": "RESOURCE_EXHAUSTED"}})

_RATELIMIT_BODY = json.dumps({"error": {
    "code": 429,
    "message": "Resource exhausted: too many requests per minute. Try again later.",
    "status": "RESOURCE_EXHAUSTED"}})


def test_billing_429_fails_fast_no_retry(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(gemini_image.requests, "post",
                        lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1)
                                         or FakeResp(429, _BILLING_BODY)))
    slept = []
    monkeypatch.setattr(gemini_image.time, "sleep", lambda s: slept.append(s))

    with pytest.raises(GeminiAPIError) as ei:
        _post_with_retry("http://x", {}, timeout=5)

    assert calls["n"] == 1, "billing 429 must not be retried"
    assert slept == [], "billing 429 must not sleep/back off"
    msg = str(ei.value).lower()
    assert "billing" in msg or "credit" in msg
    assert "ai.studio" in msg


def test_transient_429_still_retries(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(gemini_image.requests, "post",
                        lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1)
                                         or FakeResp(429, _RATELIMIT_BODY)))
    monkeypatch.setattr(gemini_image.time, "sleep", lambda s: None)

    with pytest.raises(Exception):
        _post_with_retry("http://x", {}, timeout=5, max_retries=2)

    assert calls["n"] == 3, "ordinary rate-limit 429 should retry (1 + 2)"
