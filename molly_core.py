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
from calendar_repository import (
    CalendarRepository,
    format_next_events,
    format_search_results,
    format_upcoming_events,
)
from intent_models import ExecutionResult, IntentAction, IntentResolution, ResolutionStatus
import state_store
import utils


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
            if cmd_name == "month_next":
                first, last = utils.get_month_range(offset=1)
                events = self.calendar_repo.list_events_range(first, last)
                message = utils.format_month(events, first, last)
                self._record_result(intent, message, user_id)
                return message
            if cmd_name == "next":
                events = self.calendar_repo.get_next_events(intent.target_calendar, limit=1)
                message = format_next_events(events, intent.target_calendar)
                self._record_result(intent, message, user_id)
                return message

            events = self.calendar_repo.get_upcoming_events(
                intent.target_calendar,
                limit=intent.limit or 10,
            )
            message = format_upcoming_events(
                events,
                intent.target_calendar,
                intent.limit or 10,
            )
            self._record_result(intent, message, user_id)
            return message

        if intent.action == IntentAction.CREATE_EVENT:
            command = {
                "cmd": "add",
                "calendar": intent.target_calendar,
                "calendar_display": intent.metadata.get(
                    "calendar_display",
                    intent.target_calendar,
                ),
                "title": intent.title,
                "date": intent.target_date,
            }
            if intent.date_range is not None:
                command["end_date"] = intent.date_range.end
                command["all_day"] = True
            else:
                command["all_day"] = intent.metadata.get(
                    "all_day",
                    intent.time_range is None,
                )
            if intent.time_range is not None:
                command["start"] = intent.time_range.start
                command["end"] = intent.time_range.end
            if intent.recurrence:
                command["recurrence"] = list(intent.recurrence)
            message = self.calendar_repo.add_event(command)
            self._record_result(intent, message, user_id)
            return message

        if intent.action == IntentAction.UPDATE_EVENT:
            message = self.calendar_repo.find_and_edit_event(
                intent.target_calendar,
                intent.target_date,
                intent.title,
                intent.changes,
            )
            self._record_result(intent, message, user_id)
            return message

        if intent.action == IntentAction.DELETE_EVENT:
            message = self.calendar_repo.find_and_delete_event(
                intent.target_calendar,
                intent.target_date,
                intent.title,
            )
            self._record_result(intent, message, user_id)
            return message

        if intent.action == IntentAction.DELETE_SERIES:
            message = self.calendar_repo.delete_recurring_series(
                intent.target_calendar,
                intent.title,
            )
            self._record_result(intent, message, user_id)
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

    def _record_result(self, intent, message: str, user_id: int | None) -> None:
        result = ExecutionResult(
            success=not message.startswith("❌"),
            action=intent.action,
            message=message,
            metadata={
                "target_calendar": intent.target_calendar,
                "title": intent.title,
                "source": intent.source.value,
            },
        )
        state_store.record_execution(user_id, result)


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
