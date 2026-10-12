"""Command-line interface for slopscan."""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from typing import List

from slopscan import __version__
from slopscan.registry import run_detectors
from slopscan.reporters import ScanResult, render_json, render_md, render_term
from slopscan.scoring import file_score

SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".tox", ".venv", "venv",
    ".env", "node_modules", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".eggs",
}


def _should_skip_dir(dirname: str) -> bool:
    base = os.path.basename(dirname)
    return base in SKIP_DIRS or base.startswith(".")


def _matches_ignore(path: str, patterns: List[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(
            os.path.basename(path), pat
        ):
            return True
    return False


def collect_files(target: str, ignore: List[str]) -> List[str]:
    """Return sorted .py files under target (file or directory)."""
    if os.path.isfile(target):
        return [target] if target.endswith(".py") else []
    files: List[str] = []
    for root, dirs, filenames in os.walk(target):
        dirs[:] = [d for d in dirs
                   if not _should_skip_dir(os.path.join(root, d))]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, target)
            if _matches_ignore(rel, ignore) or _matches_ignore(full, ignore):
                continue
            files.append(full)
    return sorted(files)


def scan_files(files: List[str], root: str) -> ScanResult:
    result = ScanResult()
    for full in files:
        rel = os.path.relpath(full, root)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError:
            continue
        findings = run_detectors(source, rel)
        loc = len(source.splitlines())
        result.add_file(rel, findings, file_score(findings, loc), loc)
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="slopscan",
        description="Detect AI-generated slop in your Python codebase.",
    )
    p.add_argument("path", nargs="?", default=".",
                   help="file or directory to scan (default: .)")
    p.add_argument("--format", choices=["term", "json", "md"], default="term",
                   help="output format (default: term)")
    p.add_argument("--min-severity", choices=["info", "warn", "bad"],
                   default="info", help="hide findings below this severity")
    p.add_argument("--fail-under", type=int, metavar="N", default=None,
                   help="exit 1 if repo cleanliness (100 - slop) is below N")
    p.add_argument("--ignore", action="append", default=[],
                   metavar="PATTERN",
                   help="skip files matching glob (repeatable)")
    p.add_argument("--no-color", action="store_true",
                   help="disable ANSI colors in terminal output")
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__}")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    target = args.path
    if not os.path.exists(target):
        parser.error(f"path does not exist: {target}")

    root = target if os.path.isdir(target) else os.path.dirname(
        os.path.abspath(target)) or "."
    files = collect_files(target, args.ignore)
    if not files:
        print("slopscan: no Python files found.", file=sys.stderr)
        return 0

    result = scan_files(files, root)

    if args.format == "json":
        out = render_json(result, args.min_severity)
    elif args.format == "md":
        out = render_md(result, args.min_severity)
    else:
        out = render_term(result, use_color=not args.no_color,
                          min_severity=args.min_severity)
    sys.stdout.write(out)

    if args.fail_under is not None:
        clean = result.summary()["cleanliness"]
        if clean < args.fail_under:
            print(f"slopscan: cleanliness {clean}/100 is below "
                  f"--fail-under {args.fail_under}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
