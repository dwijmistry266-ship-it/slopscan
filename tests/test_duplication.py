"""Tests for the duplication detector."""

import ast

from slopscan.detectors.duplication import detect


def run(source):
    return detect(source, "x.py", ast.parse(source))


_DUP_8 = "\n".join([
    "def validate_a(d):",
    "    if d is None:",
    "        return False",
    "    if not isinstance(d, dict):",
    "        return False",
    "    if 'name' not in d:",
    "        return False",
    "    return True",
    "",
    "def validate_b(d):",
    "    if d is None:",
    "        return False",
    "    if not isinstance(d, dict):",
    "        return False",
    "    if 'email' not in d:",
    "        return False",
    "    return True",
    "",
])


def test_duplicate_blocks_flagged_once():
    findings = run(_DUP_8)
    dup = [f for f in findings if f.detector == "duplication"]
    # One report for the pair, not one per shifted window.
    assert len(dup) == 1
    assert dup[0].severity == "warn"
    assert "10 lines" in dup[0].message or "lines" in dup[0].message


def test_renamed_identifiers_still_match():
    src = ("def a():\n"
           "    total = 0\n"
           "    for i in items:\n"
           "        total = total + i\n"
           "    out = total * 2\n"
           "    print(out)\n"
           "    return total\n"
           "def b():\n"
           "    sum_ = 0\n"
           "    for j in things:\n"
           "        sum_ = sum_ + j\n"
           "    res = sum_ * 2\n"
           "    print(res)\n"
           "    return sum_\n")
    findings = run(src)
    assert any(f.detector == "duplication" for f in findings)


def test_large_duplicate_is_bad():
    block = "\n".join(f"    x{i} = compute({i})" for i in range(16))
    src = f"def a():\n{block}\n    return x0\ndef b():\n{block}\n    return x0\n"
    findings = run(src)
    dup = [f for f in findings if f.detector == "duplication"]
    assert dup and any(f.severity == "bad" for f in dup)


def test_unique_code_not_flagged():
    src = ("def add(a, b):\n"
           "    return a + b\n"
           "\n"
           "def mul(a, b):\n"
           "    result = 0\n"
           "    for _ in range(b):\n"
           "        result += a\n"
           "    return result\n"
           "\n"
           "class Config:\n"
           "    def __init__(self, path):\n"
           "        self.path = path\n"
           "        self.cache = {}\n")
    assert not any(f.detector == "duplication" for f in run(src))


def test_short_idioms_not_flagged():
    # Repeated 2-3 line idioms are fine.
    src = ("def a():\n"
           "    try:\n"
           "        return risky()\n"
           "    except ValueError:\n"
           "        return None\n"
           "def b():\n"
           "    try:\n"
           "        return other()\n"
           "    except ValueError:\n"
           "        return None\n")
    assert not any(f.detector == "duplication" for f in run(src))


def test_tiny_file_not_flagged():
    assert run("x = 1\n") == []
