from app.config import Settings


def _make_settings(**overrides) -> Settings:
    defaults = dict(
        portal_url="https://portal.example.com/login",
        portal_check_url="https://portal.example.com/attendance",
        portal_user="user",
        portal_pass="pass",
        telegram_bot_token="token",
        chat_id="123",
        port=10000,
        timezone="UTC",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_missing_required_returns_empty_when_all_set():
    settings = _make_settings()
    assert settings.missing_required() == []


def test_missing_required_reports_unset_fields():
    settings = _make_settings(portal_user="", chat_id="")
    missing = settings.missing_required()
    assert "PORTAL_USER" in missing
    assert "CHAT_ID" in missing
    assert "PORTAL_URL" not in missing


def test_portal_check_url_defaults_to_portal_url(monkeypatch):
    monkeypatch.delenv("PORTAL_CHECK_URL", raising=False)
    monkeypatch.setenv("PORTAL_URL", "https://portal.example.com/login")
    monkeypatch.setenv("PORTAL_USER", "user")
    monkeypatch.setenv("PORTAL_PASS", "pass")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("CHAT_ID", "123")

    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.portal_check_url == settings.portal_url
    get_settings.cache_clear()
