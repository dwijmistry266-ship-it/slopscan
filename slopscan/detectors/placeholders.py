"""Placeholder detector: unfinished work left in the code.

Flags:
  - TODO / FIXME comments (warn) — a plan, not code.
  - XXX / HACK comments (info) — milder, but still a smell.
  - "implement later", "not implemented", "coming soon", "to be implemented"
    style comments (bad) — the code equivalent of an empty promise.
  - Function bodies that are only ``...`` (Ellipsis) (warn).
  - Function bodies that are only ``pass`` (info), except @abstractmethod
    stubs which are a legitimate interface pattern.
  - Function bodies that only ``raise NotImplementedError`` (info) — a
    legitimate interface pattern, but still unfinished code.

Limits:
  - Comment matching is textual; a TODO in a URL or string is still matched
    because we scan comments only (via tokenize), never string literals.
  - ``pass``-only bodies are common in legitimate stubs (e.g. exception
    classes); they are reported at info severity for that reason.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from typing import List

from slopscan.findings import Finding

NAME = "placeholders"
DESCRIPTION = "Unfinished work: TODOs, Ellipsis/pass-only bodies, not-implemented stubs."

_TODO_RE = re.compile(r"\b(TODO|FIXME)\b", re.IGNORECASE)
_HACK_RE = re.compile(r"\b(XXX|HACK)\b", re.IGNORECASE)
_EMPTY_PROMISE_RE = re.compile(
    r"\b(implement\s+later|not\s+implemented|to\s+be\s+implemented|"
    r"coming\s+soon|will\s+be\s+implemented|pending\s+implementation)\b",
    re.IGNORECASE,
)


def _iter_comments(source: str):
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                yield tok.start[0], tok.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return


def _is_abstract(node: ast.FunctionDef) -> bool:
    for dec in node.decorator_list:
        name = getattr(dec, "id", None) or getattr(dec, "attr", None)
        if name == "abstractmethod":
            return True
    return False


def _sole_statement(body):
    """Return the single meaningful statement, or None.

    Skips a leading docstring so that 'docstring + pass' still counts as a
    pass-only body.
    """
    stmts = list(body)
    if (
        stmts
        and isinstance(stmts[0], ast.Expr)
        and isinstance(stmts[0].value, ast.Constant)
        and isinstance(stmts[0].value.value, str)
    ):
        stmts = stmts[1:]
    if len(stmts) == 1:
        return stmts[0]
    return None


def detect(source: str, path: str, tree: ast.Module) -> List[Finding]:
    findings: List[Finding] = []

    for lineno, comment in _iter_comments(source):
        text = comment.lstrip("#").strip()
        if _EMPTY_PROMISE_RE.search(text):
            findings.append(
                Finding(NAME, "bad", path, lineno,
                        f"placeholder comment promises future work: {text[:60]!r}")
            )
        elif _TODO_RE.search(text):
            findings.append(
                Finding(NAME, "warn", path, lineno,
                        f"TODO/FIXME left in code: {text[:60]!r}")
            )
        elif _HACK_RE.search(text):
            findings.append(
                Finding(NAME, "info", path, lineno,
                        f"XXX/HACK marker left in code: {text[:60]!r}")
            )

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stmt = _sole_statement(node.body)
        if stmt is None:
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                and stmt.value.value is Ellipsis:
            findings.append(
                Finding(NAME, "warn", path, node.lineno,
                        f"function {node.name!r} body is only '...'")
            )
        elif isinstance(stmt, ast.Pass):
            if not _is_abstract(node):
                findings.append(
                    Finding(NAME, "info", path, node.lineno,
                            f"function {node.name!r} body is only 'pass'")
                )
        elif isinstance(stmt, ast.Raise) and stmt.exc is not None and (
            (isinstance(stmt.exc, ast.Call)
             and getattr(stmt.exc.func, "id", "") == "NotImplementedError")
            or (isinstance(stmt.exc, ast.Name)
                and stmt.exc.id == "NotImplementedError")
        ):
            findings.append(
                Finding(NAME, "info", path, node.lineno,
                        f"function {node.name!r} only raises NotImplementedError")
            )

    return findings
