"""
intent_models.py — Shared intent and execution models for Molly.

These models provide a common representation for command-style input today and
future natural-language/email interpretation layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class IntentAction(str, Enum):
    VIEW_DAILY = "view_daily"
    VIEW_RANGE = "view_range"
    CREATE_EVENT = "create_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"
    DELETE_SERIES = "delete_series"
    SEARCH = "search"
    HELP = "help"


class IntentSource(str, Enum):
    TELEGRAM_COMMAND = "telegram_command"
    TELEGRAM_FREE_TEXT = "telegram_free_text"
    EMAIL = "email"


class ResolutionStatus(str, Enum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    INVALID = "invalid"


@dataclass(frozen=True)
class DateRange:
    start: date
    end: date


@dataclass(frozen=True)
class TimeRange:
    start: str
    end: str


@dataclass
class ScheduleIntent:
    action: IntentAction
    source: IntentSource
    raw_input: str = ""
    target_calendar: str | None = None
    title: str | None = None
    target_date: date | None = None
    date_range: DateRange | None = None
    time_range: TimeRange | None = None
    recurrence: list[str] = field(default_factory=list)
    search_query: str | None = None
    help_topic: str | None = None
    limit: int | None = None
    changes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentResolution:
    status: ResolutionStatus
    intent: ScheduleIntent
    missing_fields: list[str] = field(default_factory=list)
    clarification_prompt: str | None = None
    reason: str | None = None


@dataclass
class ExecutionResult:
    success: bool
    action: IntentAction
    message: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
