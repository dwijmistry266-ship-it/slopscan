"""Reporters: term (colored), json, and md output formats."""

from __future__ import annotations

import json
from typing import Dict, List

from slopscan.findings import Finding
from slopscan.scoring import cleanliness, severity_counts

_GLYPHS = {"bad": "✖", "warn": "⚠", "info": "ℹ"}
_COLORS = {"bad": "\033[31m", "warn": "\033[33m", "info": "\033[36m"}
_RESET = "\033[0m"
_BOLD = "\033[1m"
_SEV_ORDER = {"bad": 0, "warn": 1, "info": 2}


def _bar(score: int, width: int = 20) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


class ScanResult:
    """Everything a reporter needs: per-file findings, scores, and LOC."""

    def __init__(self):
        # path -> {"findings": [...], "slop": int, "loc": int}
        self.files: Dict[str, dict] = {}

    def add_file(self, path: str, findings: List[Finding],
                 slop: int, loc: int) -> None:
        self.files[path] = {"findings": findings, "slop": slop, "loc": loc}

    def all_findings(self) -> List[Finding]:
        out: List[Finding] = []
        for data in self.files.values():
            out.extend(data["findings"])
        return out

    def summary(self) -> dict:
        findings = self.all_findings()
        counts = severity_counts(findings)
        total_loc = sum(d["loc"] for d in self.files.values())
        slop = 0
        if total_loc:
            slop = min(100, round(sum(
                d["slop"] * d["loc"] for d in self.files.values()
            ) / total_loc))
        return {
            "files_scanned": len(self.files),
            "total_findings": len(findings),
            "by_severity": counts,
            "total_loc": total_loc,
            "slop": slop,
            "cleanliness": cleanliness(slop),
        }


def render_term(result: ScanResult, use_color: bool = True,
                min_severity: str = "info") -> str:
    """Human-readable terminal report grouped by file."""
    rank = {"info": 0, "warn": 1, "bad": 2}
    threshold = rank[min_severity]
    lines: List[str] = []

    def paint(text: str, color: str) -> str:
        return f"{color}{text}{_RESET}" if use_color else text

    for path in sorted(result.files):
        data = result.files[path]
        shown = [f for f in data["findings"]
                 if rank[f.severity] >= threshold]
        if not shown and data["slop"] == 0:
            continue
        shown.sort(key=lambda f: (_SEV_ORDER[f.severity], f.line))
        header = f"{path}  ·  slop {data['slop']}/100"
        lines.append(paint(header, _BOLD) if use_color else header)
        for f in shown:
            glyph = _GLYPHS[f.severity]
            color = _COLORS[f.severity]
            sev = paint(f"{glyph} {f.severity.upper():4}", color)
            lines.append(
                f"  {sev}  L{f.line:<5} [{f.detector}] {f.message}"
            )
        lines.append("")

    s = result.summary()
    lines.append(paint("─" * 52, _BOLD) if use_color else "─" * 52)
    lines.append(
        f"Scanned {s['files_scanned']} files ({s['total_loc']} LOC) · "
        f"{s['total_findings']} findings "
        f"(✖{s['by_severity']['bad']} ⚠{s['by_severity']['warn']} "
        f"ℹ{s['by_severity']['info']})"
    )
    bar = _bar(s["slop"])
    score_line = f"Repo slop: {s['slop']}/100 {bar}  (cleanliness {s['cleanliness']}/100)"
    if use_color:
        color = _COLORS["bad"] if s["slop"] >= 50 else (
            _COLORS["warn"] if s["slop"] >= 20 else _COLORS["info"])
        score_line = paint(score_line, color + _BOLD)
    lines.append(score_line)
    return "\n".join(lines).rstrip() + "\n"


def render_json(result: ScanResult, min_severity: str = "info") -> str:
    rank = {"info": 0, "warn": 1, "bad": 2}
    threshold = rank[min_severity]
    files = []
    for path in sorted(result.files):
        data = result.files[path]
        findings = [
            {"detector": f.detector, "severity": f.severity,
             "line": f.line, "message": f.message}
            for f in data["findings"] if rank[f.severity] >= threshold
        ]
        files.append({"path": path, "slop": data["slop"],
                      "loc": data["loc"], "findings": findings})
    return json.dumps({"files": files, "summary": result.summary()},
                      indent=2) + "\n"


def render_md(result: ScanResult, min_severity: str = "info") -> str:
    rank = {"info": 0, "warn": 1, "bad": 2}
    threshold = rank[min_severity]
    s = result.summary()
    lines = ["# Slopscan report", "",
             f"Scanned **{s['files_scanned']}** files "
             f"({s['total_loc']} LOC) — **{s['total_findings']}** findings "
             f"(✖ {s['by_severity']['bad']}, "
             f"⚠ {s['by_severity']['warn']}, "
             f"ℹ {s['by_severity']['info']}).",
             "",
             f"**Repo slop: {s['slop']}/100** "
             f"(cleanliness {s['cleanliness']}/100)", ""]
    for path in sorted(result.files):
        data = result.files[path]
        shown = [f for f in data["findings"]
                 if rank[f.severity] >= threshold]
        if not shown:
            continue
        shown.sort(key=lambda f: (_SEV_ORDER[f.severity], f.line))
        lines.append(f"## `{path}` — slop {data['slop']}/100")
        lines.append("")
        lines.append("| Severity | Line | Detector | Finding |")
        lines.append("|---|---|---|---|")
        for f in shown:
            msg = f.message.replace("|", "\\|")
            lines.append(
                f"| {f.severity} | {f.line} | `{f.detector}` | {msg} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
