"""Tests for the placeholders detector."""

import ast

from slopscan.detectors.placeholders import detect


def run(source):
    return detect(source, "x.py", ast.parse(source))


def test_todo_comment_flagged():
    findings = run("# TODO: fix this later\nx = 1\n")
    assert any(f.severity == "warn" and "TODO" in f.message for f in findings)


def test_fixme_comment_flagged():
    findings = run("# FIXME: broken\nx = 1\n")
    assert any(f.severity == "warn" for f in findings)


def test_empty_promise_is_bad():
    findings = run("# will be implemented later\ndef f():\n    pass\n")
    assert any(f.severity == "bad" for f in findings)


def test_hack_is_info():
    findings = run("# HACK: workaround\nx = 1\n")
    assert any(f.severity == "info" for f in findings)


def test_ellipsis_body_flagged():
    findings = run("def f():\n    ...\n")
    assert any("only '...'" in f.message for f in findings)


def test_pass_only_body_is_info():
    findings = run("def f():\n    pass\n")
    assert any("only 'pass'" in f.message and f.severity == "info"
               for f in findings)


def test_notimplementederror_body_is_info():
    findings = run("def f():\n    raise NotImplementedError\n")
    assert any("NotImplementedError" in f.message for f in findings)


def test_abstractmethod_pass_not_flagged():
    src = ("from abc import abstractmethod\n"
           "class A:\n"
           "    @abstractmethod\n"
           "    def f(self):\n"
           "        pass\n")
    findings = run(src)
    assert not any("only 'pass'" in f.message for f in findings)


def test_clean_code_not_flagged():
    src = ("def add(a, b):\n"
           "    # Sum two numbers.\n"
           "    return a + b\n")
    assert run(src) == []


def test_todo_in_string_not_flagged():
    # Comments are found via tokenize; a TODO inside a string literal is
    # not a comment and must not match.
    src = 'x = "TODO: not a real todo"\n'
    assert run(src) == []
