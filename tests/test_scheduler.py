from __future__ import annotations

from datetime import datetime

import asyncio

import config
import local_calendar_backend
import scheduler
import utils
from calendar_repository import CalendarRepository


class DummyBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.messages.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})


def test_check_reminders_uses_override_summary_and_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "SCHEDULER_REMINDER_MINUTES", 60)
    scheduler._reminded.clear()
    scheduler._last_check = None

    service = local_calendar_backend.authenticate()
    local_calendar_backend.add_event(
        service,
        {
            "calendar": "younha",
            "title": "Cubs",
            "date": utils.parse_date("13-04-2026"),
            "start": "18:30",
            "end": "20:00",
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"],
        },
    )
    local_calendar_backend.set_recurring_occurrence_override(
        service,
        "younha",
        "Cubs",
        utils.parse_date("20-04-2026"),
        changes={"title": "Cubs @ Green Lane Primary School"},
        metadata={
            "location": "Green Lane Primary School",
            "notes": "This week only, not Scout Centre.",
        },
    )

    repo = CalendarRepository.from_config()
    bot = DummyBot()

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return tz.localize(datetime(2026, 4, 20, 17, 30, 0))

    monkeypatch.setattr(scheduler, "datetime", FrozenDateTime)

    asyncio.run(scheduler._check_reminders(repo, bot))

    assert len(bot.messages) == 2
    text = bot.messages[0]["text"]
    assert "Cubs @ Green Lane Primary School" in text
    assert "[YounHa]" in text
    assert "18:30" in text
    assert "Green Lane Primary School" in text
    assert "This week only" in text
