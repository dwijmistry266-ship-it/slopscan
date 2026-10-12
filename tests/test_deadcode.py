"""Tests for the dead-code detector."""

import ast

from slopscan.detectors.deadcode import detect


def run(source):
    return detect(source, "x.py", ast.parse(source))


def test_unreachable_after_return():
    src = "def f():\n    return 1\n    print('dead')\n"
    findings = run(src)
    assert any("unreachable" in f.message for f in findings)


def test_unreachable_after_raise():
    src = "def f():\n    raise ValueError\n    x = 1\n"
    findings = run(src)
    assert any("unreachable" in f.message for f in findings)


def test_no_unreachable_when_clean():
    src = "def f(x):\n    if x:\n        return 1\n    return 2\n"
    assert not any("unreachable" in f.message for f in run(src))


def test_unused_import_flagged():
    src = "import os\nimport sys\nprint(sys.argv)\n"
    findings = run(src)
    assert any("os" in f.message and "never used" in f.message
               for f in findings)
    assert not any("'sys'" in f.message for f in findings)


def test_used_import_not_flagged():
    src = "import os\nprint(os.getcwd())\n"
    assert not any("never used" in f.message for f in run(src))


def test_from_import_alias_flagged():
    src = "from os import getcwd as gc\nprint('hi')\n"
    findings = run(src)
    assert any("gc" in f.message for f in findings)


def test_all_listed_import_not_flagged():
    src = '__all__ = ["helper"]\nfrom m import helper\n'
    assert not any("never used" in f.message for f in run(src))


def test_noqa_import_not_flagged():
    src = "import os  # noqa\n"
    assert not any("never used" in f.message for f in run(src))


def test_star_import_disables_check():
    src = "from m import *\nimport os\nprint('hi')\n"
    assert not any("never used" in f.message for f in run(src))


def test_type_checking_import_not_flagged():
    src = ("from typing import TYPE_CHECKING\n"
           "if TYPE_CHECKING:\n"
           "    import os\n"
           "print('hi')\n")
    assert not any("'os'" in f.message and "never used" in f.message
                   for f in run(src))


def test_unused_local_constant_flagged():
    src = "def f():\n    x = 42\n    return 1\n"
    findings = run(src)
    assert any("never used" in f.message and "'x'" in f.message
               for f in findings)


def test_used_local_not_flagged():
    src = "def f():\n    x = 42\n    return x\n"
    assert not any("never used" in f.message for f in run(src))


def test_side_effect_call_not_flagged_as_unused():
    # Conservative: only constant assignments are checked.
    src = "def f():\n    x = compute()\n    return 1\n"
    assert not any("never used" in f.message for f in run(src))


def test_future_import_not_flagged():
    src = "from __future__ import annotations\ndef f(x: int) -> int:\n    return x\n"
    assert not any("never used" in f.message for f in run(src))


def test_underscore_var_not_flagged():
    src = "def f():\n    _x = 42\n    return 1\n"
    assert not any("never used" in f.message for f in run(src))
