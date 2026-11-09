from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


MAX_PAGE_LIMIT = 100
DEFAULT_PAGE_LIMIT = 100
LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\S+)\s+"
    r"(?P<level>\S+)\s+"
    r"\[(?P<process>\d+):(?P<thread>[^\]]+)\]\s+"
    r"(?P<logger>[^:]+):\s+"
    r"(?P<message>.*)$"
)
KEY_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=")


def parse_positive_int(raw: str | None, default: int) -> int:
    try:
        value = int(raw or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def read_log_entries(path: Path, *, logger_name: str | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    raw_entries: list[str] = []
    current: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if LOG_LINE_RE.match(line):
                if current:
                    raw_entries.append("".join(current).rstrip("\n"))
                current = [line]
            elif current:
                current.append(line)
            else:
                raw_entries.append(line.rstrip("\n"))
        if current:
            raw_entries.append("".join(current).rstrip("\n"))

    entries = []
    for index, raw_entry in enumerate(raw_entries):
        entry = parse_log_entry(raw_entry)
        if logger_name and entry.get("logger") != logger_name:
            continue
        entries.append((index, entry))

    entries.sort(
        key=lambda item: (
            item[1].get("timestamp") or "",
            item[0],
        ),
        reverse=True,
    )
    return [entry for _, entry in entries]


def paginate_log_entries(entries: list[dict[str, Any]], page: int, limit: int) -> dict[str, Any]:
    total = len(entries)
    total_pages = math.ceil(total / limit) if total else 0
    start = (page - 1) * limit
    end = start + limit
    return {
        "count": total,
        "page": page,
        "limit": limit,
        "totalPages": total_pages,
        "nextPage": page + 1 if end < total else None,
        "previousPage": page - 1 if page > 1 and total else None,
        "results": entries[start:end],
    }


def parse_log_entry(raw_line: str) -> dict[str, Any]:
    line = raw_line.rstrip("\n")
    match = LOG_LINE_RE.match(line)
    if not match:
        return {
            "timestamp": "",
            "level": "",
            "logger": "",
            "message": line,
            "details": {},
        }

    data = match.groupdict()
    message = data["message"]
    return {
        "timestamp": data["timestamp"],
        "level": data["level"],
        "logger": data["logger"],
        "message": message,
        "process": data["process"],
        "thread": data["thread"],
        "details": parse_key_values(message),
    }


def parse_key_values(message: str) -> dict[str, Any]:
    details: dict[str, Any] = {}
    position = 0
    while match := KEY_RE.search(message, position):
        key = match.group("key")
        raw_value, position = _read_log_value(message, match.end())
        if (raw_value.startswith('"') and raw_value.endswith('"')) or (
            raw_value.startswith("'") and raw_value.endswith("'")
        ):
            raw_value = raw_value[1:-1]
        try:
            details[key] = json.loads(raw_value)
        except (TypeError, ValueError):
            details[key] = raw_value
    return details


def _read_log_value(message: str, start: int) -> tuple[str, int]:
    if start >= len(message):
        return "", start

    if message[start] in "{[":
        return _read_json_like_value(message, start)

    if message[start] in "\"'":
        return _read_quoted_value(message, start)

    end = start
    while end < len(message) and not message[end].isspace():
        end += 1
    return message[start:end].strip(), end


def _read_json_like_value(message: str, start: int) -> tuple[str, int]:
    opening = message[start]
    closing = "}" if opening == "{" else "]"
    stack = [closing]
    in_string = False
    escaped = False
    end = start + 1

    while end < len(message):
        char = message[end]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif stack and char == stack[-1]:
            stack.pop()
            if not stack:
                end += 1
                break

        end += 1

    return message[start:end].strip(), end


def _read_quoted_value(message: str, start: int) -> tuple[str, int]:
    quote = message[start]
    escaped = False
    end = start + 1

    while end < len(message):
        char = message[end]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            end += 1
            break
        end += 1

    return message[start:end].strip(), end

