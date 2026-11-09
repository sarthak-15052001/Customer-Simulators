from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo


class ParisFormatter(logging.Formatter):
    """Format log timestamps in Europe/Paris regardless of server locale."""

    paris_tz = ZoneInfo("Europe/Paris")

    def formatTime(self, record, datefmt=None):  # noqa: N802 - logging API name
        dt = datetime.fromtimestamp(record.created, tz=self.paris_tz)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="seconds")


def paris_now() -> str:
    """Return the current timestamp in Europe/Paris for structured log fields."""

    return datetime.now(tz=ParisFormatter.paris_tz).isoformat(timespec="seconds")
