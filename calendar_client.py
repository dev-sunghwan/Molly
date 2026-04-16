"""
calendar_client.py — Legacy compatibility layer.

New code should prefer `calendar_repository.py`. This module remains only to
avoid breaking older imports while the codebase is being cleaned up.
"""
from calendar_repository import CalendarRepository, format_next_events, format_search_results, format_upcoming_events

