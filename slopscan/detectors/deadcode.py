"""Dead-code detector: code that can never run or never gets used.

Flags:
  - Unreachable statements after return/raise/continue/break in the same
    block (warn). Only flags statements in the same statement list that
    follows the terminator — no cross-branch guessing.
  - Unused imports (warn). An imported name that is never loaded anywhere
    in the file. Skips names listed in ``__all__``, imports under
    ``if TYPE_CHECKING:``, and imports on a line with a ``noqa`` comment.
  - Unused local variables (info, very conservative). Only flags a plain
    ``name = <constant>`` assignment inside a function where the name is
    never loaded afterwards and does not start with an underscore. Anything
    with a possible side effect is left alone.

Limits:
  - Unreachable-code detection does not understand ``try/finally`` control
    flow subtleties; it works on plain statement lists only.
  - Unused-import detection is file-scoped: re-exports without ``__all__``
    and dynamic uses (getattr, eval, string annotations) are not understood.
    When in doubt it stays silent only for the documented skip cases above.
  - ``from m import *`` disables the unused-import check for that file
    entirely rather than risk false positives.
"""

from __future__ import annotations

import ast
import io
import tokenize
from typing import Dict, List, Set

from slopscan.findings import Finding

NAME = "deadcode"
DESCRIPTION = "Unreachable code, unused imports, unused local variables."

_TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)
_IMPLICIT_GLOBALS = {
    "__name__", "__file__", "__doc__", "__package__", "__loader__",
    "__spec__", "__annotations__", "__cached__", "__builtins__",
}


def _statement_lists(tree: ast.Module):
    """Yield every statement list (block) in the tree."""
    for node in ast.walk(tree):
        for attr in ("body", "orelse", "finalbody"):
            stmts = getattr(node, attr, None)
            if isinstance(stmts, list) and stmts and all(
                isinstance(s, ast.stmt) for s in stmts
            ):
                yield node, attr, stmts


def _unreachable(source: str, path: str, tree: ast.Module) -> List[Finding]:
    findings: List[Finding] = []
    seen: Set[int] = set()
    for _node, _attr, stmts in _statement_lists(tree):
        dead_start = None
        for i, stmt in enumerate(stmts):
            if dead_start is None and isinstance(stmt, _TERMINATORS):
                dead_start = i + 1
            elif dead_start is not None and i >= dead_start:
                if stmt.lineno not in seen:
                    seen.add(stmt.lineno)
                    findings.append(
                        Finding(
                            NAME, "warn", path, stmt.lineno,
                            "unreachable code after "
                            + type(stmts[dead_start - 1]).__name__.lower(),
                        )
                    )
    return findings


class _ImportCollector(ast.NodeVisitor):
    def __init__(self):
        self.imports: Dict[str, int] = {}  # bound name -> line
        self.star_import = False
        self.type_checking_lines: Set[int] = set()

    def _in_type_checking(self, node) -> bool:
        parent = getattr(node, "_slop_parent", None)
        while parent is not None:
            if isinstance(parent, ast.If):
                test = parent.test
                if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                    return True
                if (
                    isinstance(test, ast.Attribute)
                    and test.attr == "TYPE_CHECKING"
                ):
                    return True
            parent = getattr(parent, "_slop_parent", None)
        return False

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = (alias.asname or alias.name).split(".")[0]
            if self._in_type_checking(node):
                self.type_checking_lines.add(node.lineno)
            else:
                self.imports.setdefault(name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        # `from __future__ import ...` is a compiler directive, not a
        # binding that code can use — never flag it.
        if node.module == "__future__":
            self.generic_visit(node)
            return
        if any(a.name == "*" for a in node.names):
            self.star_import = True
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            if self._in_type_checking(node):
                self.type_checking_lines.add(node.lineno)
            else:
                self.imports.setdefault(name, node.lineno)
        self.generic_visit(node)


def _set_parents(tree: ast.Module) -> None:
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._slop_parent = node  # type: ignore[attr-defined]


def _noqa_lines(source: str) -> Set[int]:
    lines: Set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT and "noqa" in tok.string.lower():
                lines.add(tok.start[0])
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return lines


def _unused_imports(
    source: str, path: str, tree: ast.Module, collector: _ImportCollector
) -> List[Finding]:
    findings: List[Finding] = []
    if collector.star_import:
        return findings
    loaded: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            loaded.add(node.id)
    dunder_all: Set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    dunder_all.add(elt.value)
    noqa = _noqa_lines(source)
    for name, lineno in collector.imports.items():
        if name in _IMPLICIT_GLOBALS or name in dunder_all:
            continue
        if lineno in noqa or lineno in collector.type_checking_lines:
            continue
        if name not in loaded:
            findings.append(
                Finding(NAME, "warn", path, lineno,
                        f"imported name {name!r} is never used")
            )
    return findings


def _unused_locals(path: str, tree: ast.Module) -> List[Finding]:
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        loaded: Set[str] = set()
        stored: Dict[str, int] = {}
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                if isinstance(child.ctx, ast.Load):
                    loaded.add(child.id)
                elif isinstance(child.ctx, ast.Store):
                    stored.setdefault(child.id, child.lineno)
        # Only consider simple `name = <constant>` assignments.
        constant_assigns: Set[str] = set()
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Assign)
                and len(child.targets) == 1
                and isinstance(child.targets[0], ast.Name)
                and isinstance(child.value, ast.Constant)
            ):
                constant_assigns.add(child.targets[0].id)
        arg_names = {a.arg for a in node.args.args} | {
            a.arg for a in node.args.kwonlyargs
        }
        if node.args.vararg:
            arg_names.add(node.args.vararg.arg)
        if node.args.kwarg:
            arg_names.add(node.args.kwarg.arg)
        for name, lineno in stored.items():
            if (
                name in constant_assigns
                and name not in loaded
                and name not in arg_names
                and not name.startswith("_")
            ):
                findings.append(
                    Finding(NAME, "info", path, lineno,
                            f"local variable {name!r} is assigned but never used")
                )
    return findings


def detect(source: str, path: str, tree: ast.Module) -> List[Finding]:
    _set_parents(tree)
    collector = _ImportCollector()
    collector.visit(tree)
    findings = _unreachable(source, path, tree)
    findings += _unused_imports(source, path, tree, collector)
    findings += _unused_locals(path, tree)
    return findings
