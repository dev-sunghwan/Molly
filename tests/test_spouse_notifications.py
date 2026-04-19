from datetime import date

from intent_models import IntentAction, IntentSource, ScheduleIntent, TimeRange
import spouse_notifications


def test_spouse_notification_target_maps_between_parents():
    assert spouse_notifications.spouse_notification_target(8289608844) == 8793305621
    assert spouse_notifications.spouse_notification_target(8793305621) == 8289608844


def test_spouse_notification_target_accepts_actor_name_aliases():
    assert spouse_notifications.spouse_notification_target(None, actor_name="성환") == 8793305621
    assert spouse_notifications.spouse_notification_target(None, actor_name="dev.sunghwan") == 8793305621
    assert spouse_notifications.spouse_notification_target(None, actor_name="지영") == 8289608844


def test_build_spouse_notification_for_create_event():
    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        target_calendar="younha",
        title="Alpha-Math",
        target_date=date(2026, 4, 17),
        time_range=TimeRange(start="17:00", end="18:00"),
    )

    text = spouse_notifications.build_spouse_notification(8289608844, intent, success=True)

    assert text is not None
    assert "성환" in text
    assert "[윤하]" in text
    assert "Alpha-Math" in text
    assert "추가했어요" in text


def test_build_spouse_notification_for_create_event_with_actor_name_fallback():
    intent = ScheduleIntent(
        action=IntentAction.CREATE_EVENT,
        source=IntentSource.TELEGRAM_FREE_TEXT,
        target_calendar="family",
        title="BBQ",
        target_date=date(2026, 4, 19),
        time_range=TimeRange(start="17:00", end="19:00"),
    )

    text = spouse_notifications.build_spouse_notification(None, intent, success=True, actor_name="성환")

    assert text is not None
    assert "성환" in text
    assert "[가족]" in text
    assert "BBQ" in text


def test_build_spouse_notification_skips_non_mutating_actions():
    intent = ScheduleIntent(
        action=IntentAction.VIEW_DAILY,
        source=IntentSource.TELEGRAM_FREE_TEXT,
    )

    text = spouse_notifications.build_spouse_notification(8289608844, intent, success=True)

    assert text is None
