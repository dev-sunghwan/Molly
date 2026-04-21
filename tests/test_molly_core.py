import config
from calendar_repository import CalendarRepository
from intent_models import (
    IntentAction,
    IntentResolution,
    IntentSource,
    ResolutionStatus,
    ScheduleIntent,
    TimeRange,
)
from molly_core import MollyCore
import state_store
import utils


def test_molly_core_executes_create_event(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CALENDAR_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_CALENDAR_DB_PATH", tmp_path / "local_calendar.db")
    monkeypatch.setattr(config, "STATE_DB_PATH", tmp_path / "molly_state.db")

    state_store.init_db()
    repo = CalendarRepository.from_config()
    core = MollyCore(repo)

    resolution = IntentResolution(
        status=ResolutionStatus.READY,
        intent=ScheduleIntent(
            action=IntentAction.CREATE_EVENT,
            source=IntentSource.TELEGRAM_FREE_TEXT,
            raw_input="윤하 테니스 넣어줘",
            target_calendar="younha",
            title="Tennis",
            target_date=utils._today_local(),
            time_range=TimeRange(start="17:00", end="18:00"),
            metadata={"all_day": False},
        ),
    )

    message = core.execute_resolution(resolution, user_id=123)
    events = repo.list_events(utils._today_local())
    log_rows = state_store.list_execution_log(limit=1)

    assert "Added to YounHa" in message
    assert any(event["summary"] == "Tennis" for event in events)
    assert log_rows[0]["user_id"] == 123
    assert log_rows[0]["action"] == "create_event"
    assert log_rows[0]["metadata"]["actor_user_id"] == 123
