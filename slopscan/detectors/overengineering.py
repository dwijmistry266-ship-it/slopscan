"""Over-engineering detector: complexity that earns nothing.

Flags:
  - Functions longer than 60 lines (warn). Measured by source span
    (end_lineno - lineno + 1), decorators excluded from the count start.
  - Nesting depth greater than 4 (warn). Counts if/for/while/with/try
    nesting inside a function body.
  - Single-use private helpers (info): a ``_private`` function or method
    that is defined once and called exactly once in the file. A helper
    nobody reuses is abstraction theater.
  - Classes with only ``__init__`` plus one other method (info): usually
    a function wearing a class costume. Skipped for classes with explicit
    non-``object`` base classes (e.g. exception hierarchies).

Limits:
  - The 60-line / depth-4 thresholds are opinions, documented here rather
    than hidden. Long does not always mean wrong.
  - Single-use detection is file-scoped and counts plain ``Name`` loads;
    a helper referenced via getattr or from another module is not seen.
    Dunder methods and decorated functions are never flagged.
  - Generated or test code often trips the length check; that is why it
    is warn, not bad.
"""

from __future__ import annotations

import ast
from collections import Counter
from typing import Dict, List

from slopscan.findings import Finding

NAME = "overengineering"
DESCRIPTION = "Overlong functions, deep nesting, single-use helpers, class-for-one-method."

MAX_FUNCTION_LINES = 60
MAX_NESTING_DEPTH = 4
_NESTERS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With,
            ast.AsyncWith, ast.Try)


def _function_length(node) -> int:
    start = node.lineno
    if node.decorator_list:
        start = node.decorator_list[0].lineno
    end = getattr(node, "end_lineno", None) or node.lineno
    return end - start + 1


def _max_nesting(node) -> int:
    best = 0

    def visit(n, depth):
        nonlocal best
        if isinstance(n, _NESTERS):
            depth += 1
            best = max(best, depth)
        for child in ast.iter_child_nodes(n):
            # Do not descend into nested definitions; they get their own check.
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Lambda)):
                continue
            visit(child, depth)

    visit(node, 0)
    return best


def _long_and_deep(path: str, tree: ast.Module) -> List[Finding]:
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        length = _function_length(node)
        if length > MAX_FUNCTION_LINES:
            findings.append(
                Finding(NAME, "warn", path, node.lineno,
                        f"function {node.name!r} is {length} lines "
                        f"(over {MAX_FUNCTION_LINES})")
            )
        depth = _max_nesting(node)
        if depth > MAX_NESTING_DEPTH:
            findings.append(
                Finding(NAME, "warn", path, node.lineno,
                        f"function {node.name!r} nests {depth} levels deep "
                        f"(over {MAX_NESTING_DEPTH})")
            )
    return findings


def _single_use_helpers(path: str, tree: ast.Module) -> List[Finding]:
    findings: List[Finding] = []
    defined: Dict[str, tuple] = {}  # name -> (lineno, node)
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("_")
            and not node.name.startswith("__")
            and not node.decorator_list
        ):
            defined.setdefault(node.name, (node.lineno, node))
    if not defined:
        return findings

    def _self_references(name: str, node) -> bool:
        for child in ast.walk(node):
            if child is node:
                continue
            if isinstance(child, ast.Name) and child.id == name:
                return True
            if isinstance(child, ast.Attribute) and child.attr == name:
                return True
        return False

    uses: Counter = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in defined:
                uses[node.id] += 1
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            if node.attr in defined:
                uses[node.attr] += 1
    for name, (lineno, node) in defined.items():
        if uses.get(name, 0) == 1 and not _self_references(name, node):
            findings.append(
                Finding(NAME, "info", path, lineno,
                        f"private helper {name!r} is defined once and "
                        "called exactly once")
            )
    return findings


def _thin_classes(path: str, tree: ast.Module) -> List[Finding]:
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [b for b in node.bases
                 if not (isinstance(b, ast.Name) and b.id == "object")]
        if bases or node.keywords:
            continue
        methods = [
            n for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        non_dunder = [m for m in methods
                      if not (m.name.startswith("__") and m.name.endswith("__"))]
        has_init = any(m.name == "__init__" for m in methods)
        if has_init and len(non_dunder) == 1:
            findings.append(
                Finding(NAME, "info", path, node.lineno,
                        f"class {node.name!r} has only __init__ and one method "
                        f"({non_dunder[0].name!r}) — consider a function")
            )
    return findings


def detect(source: str, path: str, tree: ast.Module) -> List[Finding]:
    findings = _long_and_deep(path, tree)
    findings += _single_use_helpers(path, tree)
    findings += _thin_classes(path, tree)
    return findings
