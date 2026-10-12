"""Shared finding record used by every detector."""

from __future__ import annotations

from dataclasses import dataclass

SEVERITIES = ("info", "warn", "bad")
_SEVERITY_RANK = {"info": 0, "warn": 1, "bad": 2}


@dataclass(order=False)
class Finding:
    """A single slop finding in a scanned file."""

    detector: str
    severity: str  # one of "info", "warn", "bad"
    path: str
    line: int
    message: str

    def sort_key(self):
        return (self.path, self.line, _SEVERITY_RANK.get(self.severity, 0))
