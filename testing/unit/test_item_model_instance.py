import item_model.instance as inst
from item_model.instance import resolve_square_token, load_instance_config


def test_token_env_access_wins(monkeypatch):
    monkeypatch.setenv("SQUARE_ACCESS_TOKEN", "tok-access")
    monkeypatch.setenv("SQUARE_TOKEN", "tok-legacy")
    assert resolve_square_token() == "tok-access"


def test_token_falls_back_to_legacy_env(monkeypatch):
    monkeypatch.delenv("SQUARE_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("SQUARE_TOKEN", "tok-legacy")
    assert resolve_square_token() == "tok-legacy"


def test_token_falls_back_to_keychain(monkeypatch):
    monkeypatch.delenv("SQUARE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SQUARE_TOKEN", raising=False)
    monkeypatch.setattr(inst, "_from_keychain", lambda name: "tok-keychain")
    assert resolve_square_token() == "tok-keychain"


def test_token_falls_back_to_dotenv(monkeypatch):
    monkeypatch.delenv("SQUARE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SQUARE_TOKEN", raising=False)
    monkeypatch.setattr(inst, "_from_keychain", lambda name: None)
    monkeypatch.setattr(inst, "_from_dotenv", lambda name, path=inst._WORKSPACE_ENV: "tok-dotenv" if name == "SQUARE_ACCESS_TOKEN" else None)
    assert resolve_square_token() == "tok-dotenv"


def test_token_none_when_all_empty(monkeypatch):
    monkeypatch.delenv("SQUARE_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SQUARE_TOKEN", raising=False)
    monkeypatch.setattr(inst, "_from_keychain", lambda name: None)
    monkeypatch.setattr(inst, "_from_dotenv", lambda name, path=inst._WORKSPACE_ENV: None)
    assert resolve_square_token() is None


def test_instance_config_defaults(monkeypatch):
    for k in ("SQUARE_LOCATION_ID", "SQUARE_MERCHANT_ID", "RG_PAGES_BASE", "RG_ITEMS_DIR"):
        monkeypatch.delenv(k, raising=False)
    c = load_instance_config()
    assert c.location_id == "B87BAEZ0NWV34" and c.merchant_id == "7MM9AFJAD0XHW"
    assert c.pages_base.endswith("/items")


def test_instance_config_env_overrides(monkeypatch):
    monkeypatch.setenv("SQUARE_LOCATION_ID", "LOC999")
    monkeypatch.setenv("RG_ITEMS_DIR", "/tmp/items")
    c = load_instance_config()
    assert c.location_id == "LOC999" and c.items_dir == "/tmp/items"
