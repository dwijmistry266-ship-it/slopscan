"""Tests for the comment-quality detector."""

import ast

from slopscan.detectors.comments import detect


def run(source):
    return detect(source, "x.py", ast.parse(source))


def test_sycophantic_comment_flagged():
    src = "# This is an awesome and perfect implementation!\ndef f():\n    pass\n"
    findings = run(src)
    assert any("sycophantic" in f.message for f in findings)


def test_great_in_comment_flagged():
    src = "# great function\ndef f():\n    pass\n"
    assert any("sycophantic" in f.message for f in run(src))


def test_plain_comment_not_flagged():
    src = "# Sum the values with Kahan compensation.\ndef f():\n    pass\n"
    assert run(src) == []


def test_restating_comment_flagged():
    src = "def f():\n    # return the result\n    return result\n"
    findings = run(src)
    assert any("restates" in f.message for f in findings)


def test_trailing_restating_comment_flagged():
    src = "def f():\n    result = compute()  # compute the result\n    return result\n"
    findings = run(src)
    assert any("restates" in f.message for f in findings)


def test_explanatory_comment_not_flagged():
    src = ("def f():\n"
           "    # Retry with backoff: the API flakes under load.\n"
           "    return call()\n")
    assert not any("restates" in f.message for f in run(src))


def test_commented_out_code_flagged():
    src = ("# def old():\n"
           "#     x = 1\n"
           "#     return x\n"
           "def new():\n"
           "    pass\n")
    findings = run(src)
    assert any("commented-out code" in f.message and f.severity == "warn"
               for f in findings)


def test_short_comment_run_not_flagged():
    # Only 2 comment lines: below the 3-line threshold.
    src = "# x = 1\n# y = 2\nz = 3\n"
    assert not any("commented-out code" in f.message for f in run(src))


def test_prose_comments_not_code():
    src = ("# First we validate the input.\n"
           "# Then we normalize it.\n"
           "# Finally we store the record.\n"
           "def f():\n"
           "    pass\n")
    assert not any("commented-out code" in f.message for f in run(src))
