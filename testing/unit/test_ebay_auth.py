import pytest

import ebay_auth


def test_hosts_rejects_unknown_environment(monkeypatch):
    monkeypatch.setattr(
        ebay_auth,
        "resolve",
        lambda name: "prodution" if name == "EBAY_ENV" else None,
    )

    with pytest.raises(ebay_auth.EbayAuthError, match="Invalid EBAY_ENV"):
        ebay_auth.hosts()


def test_check_output_does_not_expose_token(monkeypatch, capsys):
    monkeypatch.setattr(ebay_auth, "get_access_token", lambda: "secret-token")
    monkeypatch.setattr(ebay_auth, "_env_mode", lambda: "sandbox")

    assert ebay_auth._main(["check"]) == 0
    output = capsys.readouterr().out
    assert "secret-token" not in output
    assert "access_token" not in output
