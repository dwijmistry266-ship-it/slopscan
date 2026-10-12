"""Tests for the hallucination detector."""

import ast

from slopscan.detectors.hallucinations import detect


def run(source):
    return detect(source, "x.py", ast.parse(source))


def test_undefined_call_flagged_as_bad():
    src = "def f():\n    return frobnicate(1)\n"
    findings = run(src)
    assert any(f.severity == "bad" and "frobnicate" in f.message
               for f in findings)


def test_undefined_attribute_base_flagged():
    src = "import os\nresult = client.stream()\n"
    findings = run(src)
    assert any("client" in f.message for f in findings)


def test_undefined_decorator_flagged():
    src = "@register\ndef f():\n    pass\n"
    assert any("register" in f.message for f in run(src))


def test_undefined_base_class_flagged():
    src = "class A(Missing):\n    pass\n"
    assert any("Missing" in f.message for f in run(src))


def test_defined_names_not_flagged():
    src = ("import os\n"
           "from sys import argv\n"
           "CONST = 1\n"
           "def helper(x):\n"
           "    return x\n"
           "class K:\n"
           "    pass\n"
           "def f(a, b=CONST):\n"
           "    y = helper(a)\n"
           "    return os.getcwd(), argv, y, K, b\n")
    assert run(src) == []


def test_builtins_not_flagged():
    src = "def f(x):\n    return len(x), str(x), isinstance(x, int)\n"
    assert run(src) == []


def test_implicit_globals_not_flagged():
    src = 'if __name__ == "__main__":\n    print(__file__)\n'
    assert run(src) == []


def test_star_import_skips_file():
    src = "from m import *\nresult = whatever(1)\n"
    assert run(src) == []


def test_string_annotation_names_not_flagged():
    src = ('def f(x: "Widget") -> "Widget":\n'
           '    return make_widget(x)\n'
           'def make_widget(x):\n'
           '    return x\n')
    # make_widget is defined; Widget only appears in strings.
    assert run(src) == []


def test_method_calls_not_flagged():
    src = ("class A:\n"
           "    def run(self):\n"
           "        return self.helper()\n"
           "    def helper(self):\n"
           "        return 1\n")
    assert run(src) == []


def test_comprehension_and_walrus_defs():
    src = ("def f(items):\n"
           "    total = sum(x * 2 for x in items)\n"
           "    if (n := len(items)) > 0:\n"
           "        return total, n\n"
           "    return 0, 0\n")
    assert run(src) == []
