"""Slop scoring: turn findings into 0–100 scores.

Definitions:
  - Every finding has a severity weight: info=1, warn=3, bad=10.
  - A file's **slop score** is 0 (spotless) to 100 (maximum slop),
    normalized by lines of code so long files are not punished for their
    length::

        slop = min(100, round(100 * total_weight / max(lines_of_code, 1)))

    A 100-line file needs a combined weight of 100 (e.g. ten ``bad``
    findings) to hit the ceiling; a single ``info`` in a 100-line file
    scores 1.
  - A file's **cleanliness** is ``100 - slop``. The ``--fail-under`` CLI
    flag gates on cleanliness: ``--fail-under 80`` fails the build when
    cleanliness drops below 80 (i.e. slop above 20).
  - The **repo slop** is the lines-of-code-weighted mean of file slop
    scores; repo cleanliness is ``100 - repo slop``.
"""

from __future__ import annotations

from typing import Dict, List

from slopscan.findings import Finding

WEIGHTS = {"info": 1, "warn": 3, "bad": 10}


def weight(finding: Finding) -> int:
    return WEIGHTS.get(finding.severity, 0)


def file_score(findings: List[Finding], lines_of_code: int) -> int:
    """Slop score 0–100 for one file (0 = clean)."""
    if lines_of_code <= 0:
        return 0
    total = sum(weight(f) for f in findings)
    return min(100, round(100 * total / lines_of_code))


def cleanliness(sloppiness: int) -> int:
    """Convert a slop score to a cleanliness score (100 = spotless)."""
    return 100 - sloppiness


def severity_counts(findings: List[Finding]) -> Dict[str, int]:
    counts = {"info": 0, "warn": 0, "bad": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    return counts


def repo_score(file_scores: List[tuple]) -> int:
    """Repo slop 0–100.

    ``file_scores`` is a list of ``(slop, lines_of_code)`` tuples; the
    result is the LOC-weighted mean, so big files count more than stubs.
    """
    total_lines = sum(lines for _, lines in file_scores)
    if total_lines <= 0:
        return 0
    weighted = sum(slop * lines for slop, lines in file_scores)
    return min(100, round(weighted / total_lines))
