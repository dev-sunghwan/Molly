import pytest

import bot
import config


def test_legacy_bot_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(config, "LEGACY_TELEGRAM_BOT_ENABLED", False)

    with pytest.raises(SystemExit) as exc:
        bot._ensure_legacy_bot_enabled()

    assert "legacy direct Telegram polling runtime" in str(exc.value)
    assert "MOLLY_LEGACY_TELEGRAM_BOT_ENABLED=1" in str(exc.value)


def test_legacy_bot_allows_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(config, "LEGACY_TELEGRAM_BOT_ENABLED", True)

    bot._ensure_legacy_bot_enabled()
