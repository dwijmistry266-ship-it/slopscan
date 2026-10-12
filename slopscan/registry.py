"""Detector registry and runner.

Every detector module exposes::

    NAME = "placeholders"
    DESCRIPTION = "..."
    def detect(source: str, path: str, tree: ast.Module) -> list[Finding]: ...

``run_detectors`` parses each file once and fans the (source, path, tree)
triple out to every registered detector. A file that fails to parse is
skipped silently — slopscan reports on code it can understand, it does not
guess at code it cannot.
"""

from __future__ import annotations

import ast
from typing import Callable, List

from slopscan.findings import Finding

# Registry entries are (name, detect_function) tuples.
DetectorFn = Callable[[str, str, ast.Module], List[Finding]]
REGISTRY: List[tuple] = []


def register(name: str, fn: DetectorFn) -> None:
    REGISTRY.append((name, fn))


def _load_detectors() -> None:
    # Imported here so that importing slopscan.registry has no heavy
    # side effects until the registry is actually needed.
    from slopscan.detectors import comments, deadcode, duplication, hallucinations
    from slopscan.detectors import overengineering, placeholders

    for module in (
        placeholders,
        deadcode,
        comments,
        overengineering,
        hallucinations,
        duplication,
    ):
        register(module.NAME, module.detect)


_load_detectors()


def run_detectors(source: str, path: str) -> List[Finding]:
    """Run every registered detector over one file's source.

    Returns findings sorted by (path, line, severity). Unparseable files
    yield no findings.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    findings: List[Finding] = []
    for _name, fn in REGISTRY:
        try:
            findings.extend(fn(source, path, tree))
        except Exception:
            # A detector must never take down a scan. A crashing detector
            # is a bug in slopscan, not slop in the target — skip it.
            continue
    findings.sort(key=lambda f: f.sort_key())
    return findings


def detector_names() -> List[str]:
    return [name for name, _ in REGISTRY]
