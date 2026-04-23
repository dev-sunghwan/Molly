from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import local_calendar_backend
import utils
from scripts import molly_schedule_action


def _seed_event(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    service = local_calendar_backend.authenticate()
    target_date = utils.parse_date("23-04-2026")
    local_calendar_backend.add_event(
        service,
        {
            "calendar": "jeeyoung",
            "title": "Governor meeting 27 May",
            "date": target_date,
            "start": "08:00",
            "end": "09:00",
        },
    )
    return target_date


def test_flexible_delete_with_trailing_on_date(monkeypatch, tmp_path):
    _seed_event(monkeypatch, tmp_path)

    result = molly_schedule_action._execute_command_text(
        "Delete JeeYoung governor meeting 27 May on 23-04",
        actor_user_id=8793305621,
    )

    assert result["success"] is True
    assert "Deleted from JeeYoung" in result["message"]


def test_flexible_delete_from_rendered_line(monkeypatch, tmp_path):
    _seed_event(monkeypatch, tmp_path)

    result = molly_schedule_action._execute_command_text(
        "Delete Thu 23-04\n• 08:00–09:00 [지영] Governor meeting 27 May",
        actor_user_id=8793305621,
    )

    assert result["success"] is True
    assert "Deleted from JeeYoung" in result["message"]


def test_flexible_delete_by_date_time_uses_actor_calendar(monkeypatch, tmp_path):
    _seed_event(monkeypatch, tmp_path)

    result = molly_schedule_action._execute_command_text(
        "Delete the 23-04 08:00 event",
        actor_user_id=8793305621,
    )

    assert result["success"] is True
    assert "Deleted from JeeYoung" in result["message"]
