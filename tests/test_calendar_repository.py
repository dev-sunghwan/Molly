import config
import utils
from calendar_repository import CalendarRepository, format_search_results


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


def test_calendar_repository_finds_local_event_id_for_command(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")

    repo = CalendarRepository.from_config()
    command = {
        "calendar": "sunghwan",
        "title": "Repository Test",
        "date": utils._today_local(),
        "start": "09:00",
        "end": "10:00",
    }
    repo.add_event(command)

    event_id = repo.find_event_id_for_command(command)

    assert event_id is not None


def test_calendar_repository_rejects_google_primary_backend_without_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "google")
    monkeypatch.setattr(config, "ALLOW_GOOGLE_PRIMARY_BACKEND", False)

    try:
        CalendarRepository.from_config()
    except ValueError as exc:
        assert "Google Calendar cannot be used" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_format_search_results_uses_current_summary_when_display_override_exists():
    events = [
        {
            "summary": "Cubs @ Green Lane Primary School",
            "_display_summary": "Cubs",
            "_calendar_name": "YounHa",
            "start": {"dateTime": "2026-04-20T18:30:00+01:00"},
            "end": {"dateTime": "2026-04-20T20:00:00+01:00"},
        }
    ]

    message = format_search_results(events, "cubs")

    assert "Cubs @ Green Lane Primary School" in message
    assert "[윤하] Cubs @ Green Lane Primary School" in message
