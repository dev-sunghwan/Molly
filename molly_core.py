"""
molly_core.py — Deterministic Molly execution interface.

This module exposes the reusable execution boundary that sits behind any UI or
assistant layer. Telegram bots, OpenClaw bridges, or future adapters should
convert user intent into a ScheduleIntent/IntentResolution and let Molly Core
perform the actual validated calendar work.
"""
from __future__ import annotations

from datetime import timedelta

import commands
import config
import state_store
import utils
from calendar_repository import (
    CalendarRepository,
    format_next_events,
    format_search_results,
    format_upcoming_events,
)
from intent_models import ExecutionResult, IntentAction, IntentResolution, ResolutionStatus


class MollyCore:
    def __init__(self, calendar_repo: CalendarRepository) -> None:
        self.calendar_repo = calendar_repo

    def execute_resolution(
        self,
        resolution: IntentResolution,
        user_id: int | None = None,
    ) -> str:
        if resolution.status != ResolutionStatus.READY:
            raise ValueError(f"Resolution must be READY, got: {resolution.status}")
        return self.execute_intent(resolution.intent, user_id=user_id)

    def execute_intent(self, intent, user_id: int | None = None) -> str:
        cmd_name = intent.metadata.get("command")

        if intent.action == IntentAction.VIEW_DAILY:
            if cmd_name == "tomorrow":
                target = utils._today_local() + timedelta(days=1)
            elif cmd_name == "date":
                target = intent.target_date
            else:
                target = utils._today_local()
            events = self.calendar_repo.list_events(target)
            message = utils.format_event_list(events, target)
            self._record_result(intent, message, user_id)
            return message

        if intent.action == IntentAction.VIEW_RANGE:
            if cmd_name == "week":
                monday, sunday = utils.get_week_range()
                events = self.calendar_repo.list_events_range(monday, sunday)
                message = utils.format_week(events, monday, sunday)
                self._record_result(intent, message, user_id)
                return message
            if cmd_name == "week_next":
                monday, sunday = utils.get_next_week_range()
                events = self.calendar_repo.list_events_range(monday, sunday)
                message = utils.format_week(events, monday, sunday)
                self._record_result(intent, message, user_id)
                return message
            if cmd_name == "month":
                first, last = utils.get_month_range(offset=0)
                events = self.calendar_repo.list_events_range(first, last)
                message = utils.format_month(events, first, last)
                self._record_result(intent, message, user_id)
                return message
            if cmd_name == "month_remaining":
                first, last = utils.get_remaining_month_range()
                events = self.calendar_repo.list_events_range(first, last)
                events = utils.filter_events_from_now(events)
                message = utils.format_month(events, first, last)
                self._record_result(intent, message, user_id)
                return message
            if cmd_name == "month_next":
                first, last = utils.get_month_range(offset=1)
                events = self.calendar_repo.list_events_range(first, last)
                message = utils.format_month(events, first, last)
                self._record_result(intent, message, user_id)
                return message
            if isinstance(cmd_name, str) and cmd_name.startswith("month:"):
                from datetime import date
                month_value = cmd_name.split(":", 1)[1]
                year_text, month_text = month_value.split("-", 1)
                year = int(year_text)
                month = int(month_text)
                first = date(year, month, 1)
                if month == 12:
                    last = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    last = date(year, month + 1, 1) - timedelta(days=1)
                events = self.calendar_repo.list_events_range(first, last)
                message = utils.format_month(events, first, last)
                self._record_result(intent, message, user_id)
                return message
            if isinstance(cmd_name, str) and cmd_name.startswith("month_remaining:"):
                from datetime import date
                month_value = cmd_name.split(":", 1)[1]
                year_text, month_text = month_value.split("-", 1)
                year = int(year_text)
                month = int(month_text)
                first = date(year, month, 1)
                if month == 12:
                    last = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    last = date(year, month + 1, 1) - timedelta(days=1)

                today = utils._today_local()
                if today > last:
                    events = []
                    message = utils.format_month(events, first, last)
                else:
                    query_first = today if first <= today <= last else first
                    events = self.calendar_repo.list_events_range(query_first, last)
                    if query_first == today:
                        events = utils.filter_events_from_now(events)
                    message = utils.format_month(events, query_first, last)
                self._record_result(intent, message, user_id)
                return message
            if cmd_name == "next":
                if intent.target_calendar is None:
                    events = self.calendar_repo.get_upcoming_events(
                        None,
                        limit=max(1, len(config.CALENDARS)),
                    )
                    events, label = self._filter_events_for_actor(
                        events,
                        intent.target_calendar,
                        user_id,
                    )
                    events = events[:1]
                else:
                    events = self.calendar_repo.get_next_events(intent.target_calendar, limit=1)
                    events, label = self._filter_events_for_actor(
                        events,
                        intent.target_calendar,
                        user_id,
                    )
                message = format_next_events(events, intent.target_calendar, label_override=label)
                self._record_result(intent, message, user_id)
                return message

            events = self.calendar_repo.get_upcoming_events(
                intent.target_calendar,
                limit=intent.limit or 10,
            )
            events, label = self._filter_events_for_actor(events, intent.target_calendar, user_id)
            message = format_upcoming_events(
                events,
                intent.target_calendar,
                intent.limit or 10,
                label_override=label,
            )
            self._record_result(intent, message, user_id)
            return message

        if intent.action == IntentAction.CREATE_EVENT:
            all_day = intent.metadata.get(
                "all_day",
                intent.time_range is None,
            )
            command = {
                "cmd": "add",
                "calendar": intent.target_calendar,
                "calendar_display": intent.metadata.get(
                    "calendar_display",
                    intent.target_calendar,
                ),
                "title": intent.title,
                "date": intent.target_date,
                "all_day": all_day,
            }
            if intent.date_range is not None:
                command["end_date"] = intent.date_range.end
            if intent.time_range is not None:
                command["start"] = intent.time_range.start
                command["end"] = intent.time_range.end
            if intent.recurrence:
                command["recurrence"] = list(intent.recurrence)
            message, mutation_result = self.calendar_repo.add_event_result(command)
            local_event_id = self._local_event_id_for_command(
                command,
                message,
                mutation_result=mutation_result,
            )
            validation_error = self._validate_created_event(command, local_event_id, message)
            if validation_error is not None:
                message = validation_error
            self._record_result(intent, message, user_id)
            self._enqueue_google_sync_if_needed(
                intent,
                message,
                user_id,
                operation="create",
                local_event_id=local_event_id,
                mutation_result=mutation_result,
            )
            return message

        if intent.action == IntentAction.UPDATE_EVENT:
            message, mutation_result = self.calendar_repo.find_and_edit_event_result(
                intent.target_calendar,
                intent.target_date,
                intent.title,
                intent.changes,
            )
            self._record_result(intent, message, user_id)
            self._enqueue_google_sync_if_needed(
                intent,
                message,
                user_id,
                operation="update",
                local_event_id=self._mutation_local_event_id(mutation_result),
                mutation_result=mutation_result,
            )
            return message

        if intent.action == IntentAction.DELETE_EVENT:
            message, mutation_result = self.calendar_repo.find_and_delete_event_result(
                intent.target_calendar,
                intent.target_date,
                intent.title,
            )
            self._record_result(intent, message, user_id)
            self._enqueue_google_sync_if_needed(
                intent,
                message,
                user_id,
                operation="delete",
                local_event_id=self._mutation_local_event_id(mutation_result),
                mutation_result=mutation_result,
            )
            return message

        if intent.action == IntentAction.MOVE_EVENT:
            message, mutation_result = self.calendar_repo.move_event_result(
                intent.source_calendar,
                intent.target_calendar,
                intent.target_date,
                intent.title,
            )
            self._record_result(intent, message, user_id)
            self._enqueue_google_sync_if_needed(
                intent,
                message,
                user_id,
                operation="move",
                local_event_id=self._mutation_local_event_id(mutation_result),
                mutation_result=mutation_result,
            )
            return message

        if intent.action == IntentAction.DELETE_SERIES:
            message, mutation_result = self.calendar_repo.delete_recurring_series_result(
                intent.target_calendar,
                intent.title,
            )
            self._record_result(intent, message, user_id)
            self._enqueue_google_sync_if_needed(
                intent,
                message,
                user_id,
                operation="delete_series",
                local_event_id=self._mutation_local_event_id(mutation_result),
                mutation_result=mutation_result,
            )
            return message

        if intent.action == IntentAction.SEARCH:
            events = self.calendar_repo.search_events(intent.search_query)
            message = format_search_results(events, intent.search_query)
            self._record_result(intent, message, user_id)
            return message

        if intent.action == IntentAction.HELP:
            message = help_reply(intent.help_topic)
            self._record_result(intent, message, user_id)
            return message

        raise ValueError(f"Unsupported intent action: {intent.action}")


    def _filter_events_for_actor(
        self,
        events: list[dict],
        target_calendar: str | None,
        user_id: int | None,
    ) -> tuple[list[dict], str | None]:
        if target_calendar is not None or user_id is None:
            return events, None

        actor = config.USERS.get(user_id)
        subscribed = set(actor.get("reminder_calendars", [])) if actor else set()
        if not subscribed:
            return events, None

        filtered = [
            event
            for event in events
            if self._event_calendar_key(event) in subscribed
        ]
        return filtered, f"{actor['name']} calendars"

    @staticmethod
    def _event_calendar_key(event: dict) -> str:
        display = (event.get("_calendar_name") or "").lower()
        if display in config.CALENDAR_DISPLAY_NAMES:
            return display
        for key, label in config.CALENDAR_DISPLAY_NAMES.items():
            if label.lower() == display:
                return key
        return display

    def _record_result(self, intent, message: str, user_id: int | None) -> None:
        actor_name = None
        if user_id is not None and user_id in config.USERS:
            actor_name = config.USERS[user_id]["name"]
        result = ExecutionResult(
            success=not message.startswith("❌"),
            action=intent.action,
            message=message,
            metadata={
                "target_calendar": intent.target_calendar,
                "title": intent.title,
                "source": intent.source.value,
                "actor_user_id": user_id,
                "actor_name": actor_name,
            },
        )
        state_store.record_execution(user_id, result)

    def _enqueue_google_sync_if_needed(
        self,
        intent,
        message: str,
        user_id: int | None,
        *,
        operation: str,
        local_event_id: str | None = None,
        mutation_result=None,
    ) -> None:
        if not config.GOOGLE_SYNC_OUTBOX_ENABLED:
            return
        if self.calendar_repo.backend_name != "local":
            return
        if message.startswith("❌"):
            return

        try:
            state_store.enqueue_google_sync(
                operation=operation,
                local_event_id=local_event_id,
                payload={
                    "action": intent.action.value,
                    "source": intent.source.value,
                    "raw_input": intent.raw_input,
                    "target_calendar": intent.target_calendar,
                    "source_calendar": intent.source_calendar,
                    "title": intent.title,
                    "target_date": intent.target_date.isoformat() if intent.target_date else None,
                    "date_range": (
                        {
                            "start": intent.date_range.start.isoformat(),
                            "end": intent.date_range.end.isoformat(),
                        }
                        if intent.date_range is not None
                        else None
                    ),
                    "time_range": (
                        {
                            "start": intent.time_range.start,
                            "end": intent.time_range.end,
                        }
                        if intent.time_range is not None
                        else None
                    ),
                    "recurrence": list(intent.recurrence),
                    "changes": dict(intent.changes),
                    "actor_user_id": user_id,
                    "metadata": dict(intent.metadata),
                    "mutation_result": self._mutation_result_payload(mutation_result),
                },
            )
        except Exception:
            # Google sync is explicitly asynchronous and must not block the user response.
            return

    def _local_event_id_for_command(self, command: dict, message: str, *, mutation_result=None) -> str | None:
        if message.startswith("❌"):
            return None
        mutation_id = self._mutation_local_event_id(mutation_result)
        if mutation_id:
            return mutation_id
        if self.calendar_repo.backend_name != "local":
            return None
        try:
            return self.calendar_repo.find_event_id_for_command(command)
        except Exception:
            return None

    @staticmethod
    def _mutation_local_event_id(mutation_result) -> str | None:
        if mutation_result is None:
            return None
        if hasattr(mutation_result, "local_event_id"):
            return mutation_result.local_event_id
        if isinstance(mutation_result, dict):
            value = mutation_result.get("local_event_id")
            return str(value) if value else None
        return None

    @staticmethod
    def _mutation_result_payload(mutation_result) -> dict | None:
        if mutation_result is None:
            return None
        if hasattr(mutation_result, "to_dict"):
            return mutation_result.to_dict()
        if isinstance(mutation_result, dict):
            return dict(mutation_result)
        return None


    def _validate_created_event(self, command: dict, local_event_id: str | None, message: str) -> str | None:
        if message.startswith("❌"):
            return None
        if self.calendar_repo.backend_name != "local":
            return None
        if not local_event_id:
            return "❌ Molly could not verify the saved event after creation. Nothing confirmed."
        try:
            event = self.calendar_repo.get_event_by_id(local_event_id)
        except Exception:
            return "❌ Molly could not verify the saved event after creation. Nothing confirmed."
        if event is None:
            return "❌ Molly could not verify the saved event after creation. Nothing confirmed."

        if event.get("summary") != command.get("title"):
            return "❌ Saved event title did not match the request, so Molly did not confirm it."

        start = event.get("start", {})
        end = event.get("end", {})
        expected_start = utils.make_datetime(command["date"], command["start"]).isoformat() if command.get("start") else None
        expected_end_date = command.get("end_date", command["date"])
        expected_end = utils.make_datetime(expected_end_date, command["end"]).isoformat() if command.get("end") else None

        if expected_start is not None and start.get("dateTime") != expected_start:
            return "❌ Saved event start time did not match the request, so Molly did not confirm it."
        if expected_end is not None and end.get("dateTime") != expected_end:
            return "❌ Saved event end time did not match the request, so Molly did not confirm it."
        if expected_start is None:
            expected_start_date = command["date"].isoformat()
            expected_end_date_exclusive = (expected_end_date + timedelta(days=1)).isoformat()
            if start.get("date") != expected_start_date or end.get("date") != expected_end_date_exclusive:
                return "❌ Saved all-day event dates did not match the request, so Molly did not confirm it."

        return None


def help_reply(topic: str | None) -> str:
    if topic is None:
        return commands.USAGE

    normalized = topic.strip().lower()
    mapping = {
        "view": commands.HELP_VIEW,
        "add": commands.HELP_ADD,
        "edit": commands.HELP_EDIT,
        "delete": commands.HELP_DELETE,
        "search": commands.HELP_SEARCH,
        "calendars": commands.HELP_CALENDARS,
    }
    if normalized in mapping:
        return mapping[normalized]
    return (
        f"No help available for '{topic}'.\n\n"
        "Topics: view · add · edit · delete · search · calendars"
    )
