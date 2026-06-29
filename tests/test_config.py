import config


def test_validate_rejects_google_primary_backend_without_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(config, "ALLOWED_USER_IDS", {1})
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "google")
    monkeypatch.setattr(config, "ALLOW_GOOGLE_PRIMARY_BACKEND", False)
    monkeypatch.setattr(config, "TELEGRAM_EXTRACTOR_BACKEND", "heuristic")

    try:
        config.validate()
    except SystemExit as exc:
        assert "MOLLY_CALENDAR_BACKEND=google is disabled" in str(exc)
    else:
        raise AssertionError("Expected SystemExit")


def test_validate_accepts_local_backend_without_google_credentials(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(config, "ALLOWED_USER_IDS", {1})
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "ALLOW_GOOGLE_PRIMARY_BACKEND", False)
    monkeypatch.setattr(config, "TELEGRAM_EXTRACTOR_BACKEND", "heuristic")

    config.validate()
