"""Hallucination detector: names that are used but never defined.

Flags names that are *called* (``foo()``) or used as an attribute base
(``foo.bar``) when ``foo`` is never imported, defined, or assigned anywhere
in the file. AI models love to invent APIs — ``client.stream_response()``
where no ``client`` was ever created is the canonical tell.

Conservative by design (a false positive here is worse than a miss):
  - Files with ``from x import *`` are skipped entirely.
  - Builtins, keyword-adjacent implicit module globals (``__name__``,
    ``__file__``, ...) are allow-listed.
  - Every definition site counts: imports, assignments, function/class defs,
    arguments, loop variables, ``with``/``except`` targets, comprehensions,
    walrus operators, and names bound inside decorators.
  - Identifier-like tokens inside string literals are treated as "maybe
    defined" so that string annotations (``def f(x: "Widget")``) and
    ``TYPE_CHECKING``-style forward references do not false-positive.
  - Only *called* names and *attribute bases* are checked — a bare
    ``return undefined_name`` is left to linters, not slopscan.

Severity is ``bad``: calling something that does not exist is the
strongest single signal of generated-and-never-run code.

Limits:
  - File-scoped: names imported or defined in another module of the same
    project are invisible. Run slopscan per-file mentally, not per-project.
  - Dynamic definitions (``globals()[...] =``, ``exec``, decorators that
    inject names) are not understood.
  - A genuinely hallucinated name that also appears in a docstring will be
    missed because of the string-literal allow-list. Documented trade-off.
"""

from __future__ import annotations

import ast
import builtins
import io
import re
import tokenize
from typing import List, Set

from slopscan.findings import Finding

NAME = "hallucinations"
DESCRIPTION = "Names called/used but never defined, imported, or assigned."

_IMPLICIT_GLOBALS = {
    "__name__", "__file__", "__doc__", "__package__", "__loader__",
    "__spec__", "__annotations__", "__cached__", "__builtins__",
}
_BUILTINS = set(dir(builtins))
_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


class _DefCollector(ast.NodeVisitor):
    def __init__(self):
        self.defined: Set[str] = set()

    def _bind(self, target) -> None:
        for node in ast.walk(target):
            if isinstance(node, ast.Name) and isinstance(
                node.ctx, (ast.Store, ast.Param)
            ):
                self.defined.add(node.id)
            elif isinstance(node, ast.arg):
                self.defined.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                self.defined.add(node.name)
                for dec in node.decorator_list:
                    self.visit(dec)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                self.defined.add(node.name)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.defined.add((alias.asname or alias.name).split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            if alias.name != "*":
                self.defined.add(alias.asname or alias.name)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.defined.add(node.name)
        for arg in list(node.args.args) + list(node.args.kwonlyargs):
            self.defined.add(arg.arg)
        if node.args.vararg:
            self.defined.add(node.args.vararg.arg)
        if node.args.kwarg:
            self.defined.add(node.args.kwarg.arg)
        for dec in node.decorator_list:
            self.visit(dec)
        for stmt in node.body:
            self.visit(stmt)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        self.defined.add(node.name)
        for dec in node.decorator_list:
            self.visit(dec)
        for stmt in node.body:
            self.visit(stmt)

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._bind(target)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        self._bind(node.target)
        if node.value:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign):
        self._bind(node.target)
        self.visit(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr):
        self.defined.add(node.target.id)
        self.visit(node.value)

    def visit_For(self, node: ast.For):
        self._bind(node.target)
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_With(self, node: ast.With):
        for item in node.items:
            if item.optional_vars:
                self._bind(item.optional_vars)
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.name:
            self.defined.add(node.name)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension):
        self._bind(node.target)
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda):
        for arg in list(node.args.args) + list(node.args.kwonlyargs):
            self.defined.add(arg.arg)
        self.generic_visit(node)


def _string_idents(source: str) -> Set[str]:
    """Identifier-like tokens inside string literals (forward refs, docs)."""
    idents: Set[str] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.STRING:
                idents.update(_IDENT_RE.findall(tok.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return idents


def _has_star_import(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(
            a.name == "*" for a in node.names
        ):
            return True
    return False


def detect(source: str, path: str, tree: ast.Module) -> List[Finding]:
    if _has_star_import(tree):
        return []
    collector = _DefCollector()
    collector.visit(tree)
    defined = collector.defined | _BUILTINS | _IMPLICIT_GLOBALS
    defined |= _string_idents(source)

    suspects: dict = {}  # name -> first line seen

    def _note(name, lineno):
        if name is not None and name not in defined:
            suspects.setdefault(name, lineno)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                _note(func.id, node.lineno)
            elif isinstance(func, ast.Attribute) and isinstance(
                func.value, ast.Name
            ):
                _note(func.value.id, node.lineno)
        elif isinstance(node, ast.Attribute) and isinstance(
            node.value, ast.Name
        ):
            # Attribute base, e.g. the `app` in `@app.route`.
            _note(node.value.id, node.lineno)
        elif isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name):
                    _note(base.id, node.lineno)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    _note(dec.id, node.lineno)

    return [
        Finding(NAME, "bad", path, lineno,
                f"{name!r} is used but never defined, imported, or assigned "
                "in this file")
        for name, lineno in sorted(suspects.items(), key=lambda kv: kv[1])
    ]
