"""Comment-quality detector: comments that add noise instead of meaning.

Flags:
  - Sycophantic comments (info): comments praising the code with words like
    "great", "awesome", "perfect", "amazing". A classic AI-slop tell — the
    model congratulates itself instead of explaining anything.
  - Comments that merely restate the code (info): e.g. ``# return the result``
    directly above ``return result``. Detected conservatively: at least two
    significant comment words must all appear as identifiers/words in the
    adjacent code line.
  - Commented-out code blocks (warn): runs of 3+ consecutive comment lines
    where the majority look like code (assignments, calls, defs, imports).

Limits:
  - Sycophancy matching is word-list based; a comment like "# a great
    tragedy" in a test fixture would still match. Severity is info for
    exactly this reason.
  - Restatement detection is a heuristic over the immediately adjacent line
    (next line for standalone comments, same line for trailing comments).
    Clever paraphrases are missed on purpose — a false positive here is
    worse than a miss.
  - Commented-out code needs 3+ consecutive comment lines with a majority
    looking code-ish; two-line leftovers are ignored.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from typing import List

from slopscan.findings import Finding

NAME = "comments"
DESCRIPTION = "Sycophantic, restating, or commented-out-code comments."

_SYCOPHANT_RE = re.compile(
    r"\b(great|awesome|perfect|amazing|excellent|beautiful|elegant|"
    r"fantastic|wonderful|brilliant|superb|incredible|flawless)\b",
    re.IGNORECASE,
)
_CODEISH_RE = re.compile(
    r"^\s*(def |class |import |from |return |if |elif |else:|for |while |"
    r"try:|except|with |print\(|[A-Za-z_][A-Za-z0-9_]*\s*=[^=]|[A-Za-z_][A-Za-z0-9_]*\()"
)
_STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "for", "with", "this",
    "that", "it", "is", "are", "be", "as", "in", "on", "by", "we",
}
_WORD_RE = re.compile(r"[A-Za-z]{3,}")


def _iter_comments(source: str):
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in tokens:
            if tok.type == tokenize.COMMENT:
                yield tok
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return


def _significant_words(text: str) -> List[str]:
    words = [w.lower() for w in _WORD_RE.findall(text)]
    return [w for w in words if w not in _STOPWORDS]


def _code_words(line: str) -> set:
    # Identifiers on the line, split on snake_case, lowercased.
    words = set()
    for ident in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", line):
        for part in ident.lower().split("_"):
            if len(part) >= 3:
                words.add(part)
    return words


def _restates(comment_text: str, code_line: str) -> bool:
    sig = _significant_words(comment_text)
    if len(sig) < 2:
        return False
    code = _code_words(code_line)
    return all(w in code for w in sig)


def detect(source: str, path: str, tree: ast.Module) -> List[Finding]:
    findings: List[Finding] = []
    lines = source.splitlines()
    comments = list(_iter_comments(source))

    for tok in comments:
        lineno, _col = tok.start
        text = tok.string.lstrip("#").strip()
        if not text:
            continue
        if _SYCOPHANT_RE.search(text):
            findings.append(
                Finding(NAME, "info", path, lineno,
                        f"sycophantic comment praises the code: {text[:60]!r}")
            )
            continue
        # Restatement: trailing comment -> the code on the same line before
        # the comment; standalone comment -> the next non-blank line.
        code_line = ""
        before = lines[lineno - 1][: tok.start[1]].strip()
        if before:
            code_line = before
        else:
            nxt = lineno
            while nxt < len(lines) and not lines[nxt].strip():
                nxt += 1
            if nxt < len(lines):
                code_line = lines[nxt].strip()
                if code_line.startswith("#"):
                    code_line = ""
        if code_line and _restates(text, code_line):
            findings.append(
                Finding(NAME, "info", path, lineno,
                        "comment merely restates the adjacent code")
            )

    # Commented-out code blocks: 3+ consecutive comment lines, majority code-ish.
    run: List = []
    for tok in comments:
        lineno = tok.start[0]
        text = tok.string.lstrip("#")
        if run and lineno == run[-1][0] + 1:
            run.append((lineno, text))
        else:
            if len(run) >= 3:
                _check_code_block(run, findings, path)
            run = [(lineno, text)]
    if len(run) >= 3:
        _check_code_block(run, findings, path)

    return findings


def _check_code_block(run, findings: List[Finding], path: str) -> None:
    codeish = sum(1 for _, text in run if _CODEISH_RE.search(text))
    if codeish >= 2 and codeish * 2 >= len(run):
        findings.append(
            Finding(NAME, "warn", path, run[0][0],
                    f"commented-out code block ({len(run)} lines)")
        )
