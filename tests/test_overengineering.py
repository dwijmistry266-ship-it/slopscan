"""Tests for the over-engineering detector."""

import ast

from slopscan.detectors.overengineering import detect


def run(source):
    return detect(source, "x.py", ast.parse(source))


def _long_fn(n=65):
    body = "\n".join(f"    x{i} = {i}" for i in range(n))
    return f"def f():\n{body}\n    return x0\n"


def test_long_function_flagged():
    findings = run(_long_fn(65))
    assert any("lines" in f.message and f.severity == "warn" for f in findings)


def test_short_function_not_flagged():
    assert not any("lines" in f.message for f in run(_long_fn(10)))


def test_deep_nesting_flagged():
    src = ("def f(a):\n"
           "    if a:\n"
           "        for i in a:\n"
           "            while i:\n"
           "                with open('f') as fh:\n"
           "                    try:\n"
           "                        pass\n"
           "                    except Exception:\n"
           "                        pass\n")
    findings = run(src)
    assert any("nests" in f.message for f in findings)


def test_shallow_nesting_not_flagged():
    src = "def f(a):\n    if a:\n        for i in a:\n            print(i)\n"
    assert not any("nests" in f.message for f in run(src))


def test_single_use_private_helper_flagged():
    src = ("def _helper(x):\n"
           "    return x * 2\n"
           "def main():\n"
           "    return _helper(1)\n")
    findings = run(src)
    assert any("called exactly once" in f.message for f in findings)


def test_reused_helper_not_flagged():
    src = ("def _helper(x):\n"
           "    return x * 2\n"
           "def main():\n"
           "    return _helper(1) + _helper(2)\n")
    assert not any("called exactly once" in f.message for f in run(src))


def test_recursive_helper_not_flagged():
    src = ("def _fib(n):\n"
           "    return n if n < 2 else _fib(n - 1) + _fib(n - 2)\n"
           "print(_fib(5))\n")
    assert not any("called exactly once" in f.message for f in run(src))


def test_public_function_not_flagged_as_helper():
    src = "def helper(x):\n    return x\nprint(helper(1))\n"
    assert not any("called exactly once" in f.message for f in run(src))


def test_thin_class_flagged():
    src = ("class Greeter:\n"
           "    def __init__(self, g):\n"
           "        self.g = g\n"
           "    def greet(self, n):\n"
           "        return self.g + n\n")
    findings = run(src)
    assert any("only __init__ and one method" in f.message for f in findings)


def test_exception_subclass_not_flagged():
    src = ("class MyError(Exception):\n"
           "    def __init__(self, msg):\n"
           "        super().__init__(msg)\n"
           "    def code(self):\n"
           "        return 42\n")
    assert not any("consider a function" in f.message for f in run(src))


def test_rich_class_not_flagged():
    src = ("class A:\n"
           "    def __init__(self):\n"
           "        pass\n"
           "    def one(self):\n"
           "        pass\n"
           "    def two(self):\n"
           "        pass\n")
    assert not any("consider a function" in f.message for f in run(src))
