"""Google Calendar integration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except Exception:  # pragma: no cover - optional dependency
    Credentials = None  # type: ignore
    build = None  # type: ignore


@dataclass(slots=True)
class CalendarConfig:
    credentials_file: Optional[str]


class GoogleCalendarService:
    """Wraps Google Calendar API operations."""

    def __init__(self, config: CalendarConfig) -> None:
        self.config = config
        self._service = None

    def _ensure_service(self):
        if self._service or not self.config.credentials_file or not Credentials:
            return
        credentials = Credentials.from_service_account_file(self.config.credentials_file, scopes=["https://www.googleapis.com/auth/calendar"])
        self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)

    def ensure_event(self, calendar_id: str, *, event_id: str, summary: str, start: datetime, end: datetime) -> None:
        self._ensure_service()
        if not self._service:
            return
        body = {
            "id": event_id,
            "summary": summary,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }
        self._service.events().insert(calendarId=calendar_id, body=body, supportsAttachments=False).execute()

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        self._ensure_service()
        if not self._service:
            return
        self._service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


__all__ = ["GoogleCalendarService", "CalendarConfig"]
