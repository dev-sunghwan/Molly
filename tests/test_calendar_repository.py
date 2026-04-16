import config
from calendar_repository import CalendarRepository
import utils


def test_calendar_repository_uses_local_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    repo = CalendarRepository.from_config()
    message = repo.add_event(
        {
            "calendar": "sunghwan",
            "title": "Repository Test",
            "date": utils._today_local(),
            "start": "09:00",
            "end": "10:00",
        }
    )
    events = repo.list_events(utils._today_local())

    assert repo.backend_name == "local"
    assert "Added to SungHwan" in message
    assert any(event["summary"] == "Repository Test" for event in events)
