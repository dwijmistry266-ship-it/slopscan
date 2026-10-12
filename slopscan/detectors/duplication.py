"""Duplication detector: near-duplicate code blocks.

Approach: tokenize each file, drop comments and blank lines, then normalize
every remaining line by replacing identifiers with ``N`` and numbers/strings
with ``V`` (keywords, operators and punctuation are kept). A sliding window
of ``WINDOW`` (6) normalized lines is hashed; any hash seen twice with
non-overlapping ranges is a duplicate candidate. Each candidate is extended
greedily while the normalized lines keep matching, and the maximal block is
reported once.

Flags:
  - 6–14 duplicated lines (warn)
  - 15+ duplicated lines (bad) — a whole copied function is not a
    coincidence.

Limits:
  - Normalization is deliberately aggressive: two blocks that differ only
    in variable names and literals are considered duplicates. Blocks that
    differ structurally (different keywords/operators) are not.
  - Only pairs within a single file are reported; cross-file duplication
    is out of scope for v0.1.0.
  - Reports are capped at 10 per file to avoid noise on generated files.
  - Windows shorter than 6 lines are never reported — small idioms repeat
    legitimately.
"""

from __future__ import annotations

import ast
import hashlib
import io
import keyword
import tokenize
from typing import List

from slopscan.findings import Finding

NAME = "duplication"
DESCRIPTION = "Near-duplicate code blocks (>=6 normalized lines)."
WINDOW = 6
MAX_REPORTS_PER_FILE = 10
_BAD_THRESHOLD = 15


def _normalized_lines(source: str) -> List[tuple]:
    """Return [(lineno, normalized_line), ...] for significant lines."""
    out: List[tuple] = []
    # Map physical line -> list of normalized tokens.
    buckets: dict = {}
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    for tok in tokens:
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                        tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER,
                        tokenize.ENCODING):
            continue
        lineno = tok.start[0]
        if tok.type == tokenize.NAME:
            norm = tok.string if keyword.iskeyword(tok.string) else "N"
        elif tok.type in (tokenize.NUMBER, tokenize.STRING):
            norm = "V"
        else:
            norm = tok.string
        buckets.setdefault(lineno, []).append(norm)
    for lineno in sorted(buckets):
        text = " ".join(buckets[lineno]).strip()
        if text:
            # Drop lines that are only punctuation (e.g. lone brackets).
            if any(c.isalnum() for c in text):
                out.append((lineno, text))
    return out


def _window_hash(norm_lines: List[str]) -> str:
    return hashlib.sha256("\n".join(norm_lines).encode()).hexdigest()[:16]


def detect(source: str, path: str, tree: ast.Module) -> List[Finding]:
    sig_lines = _normalized_lines(source)
    if len(sig_lines) < WINDOW * 2:
        return []
    norms = [n for _, n in sig_lines]
    linenos = [ln for ln, _ in sig_lines]

    # Hash every window; remember where each hash occurs.
    occurrences: dict = {}
    for i in range(len(norms) - WINDOW + 1):
        h = _window_hash(norms[i:i + WINDOW])
        occurrences.setdefault(h, []).append(i)

    reported = set()
    candidates: List[tuple] = []  # (length, line1, line2, end2)

    for h, idxs in occurrences.items():
        if len(idxs) < 2:
            continue
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                # Require non-overlapping windows.
                if j < i + WINDOW:
                    continue
                # Extend greedily while normalized lines match.
                length = WINDOW
                while (i + length < len(norms) and j + length < len(norms)
                       and norms[i + length] == norms[j + length]):
                    length += 1
                key = (i, j)
                if key in reported:
                    continue
                reported.add(key)
                candidates.append(
                    (length, linenos[i], linenos[j],
                     linenos[j] + length - 1))
                if len(candidates) >= MAX_REPORTS_PER_FILE * 4:
                    break
            if len(candidates) >= MAX_REPORTS_PER_FILE * 4:
                break

    # Deduplicate: longest first, keep a candidate only if it does not
    # overlap an already-kept block pair by WINDOW+ lines on both sides.
    def _overlap(a1, a2, b1, b2):
        return max(0, min(a2, b2) - max(a1, b1) + 1)

    candidates.sort(key=lambda c: -c[0])
    kept: List[tuple] = []
    findings: List[Finding] = []
    for length, line1, line2, end2 in candidates:
        end1 = line1 + length - 1
        dup = False
        for klen, k1, k2, ke2 in kept:
            ke1 = k1 + klen - 1
            if (_overlap(line1, end1, k1, ke1) >= WINDOW
                    and _overlap(line2, end2, k2, ke2) >= WINDOW):
                dup = True
                break
        if dup:
            continue
        kept.append((length, line1, line2, end2))
        severity = "bad" if length >= _BAD_THRESHOLD else "warn"
        findings.append(
            Finding(
                NAME, severity, path, line1,
                f"duplicated block: {length} lines at L{line1} "
                f"mirror L{line2}–L{end2}",
            )
        )
        if len(findings) >= MAX_REPORTS_PER_FILE:
            break

    findings.sort(key=lambda f: f.line)
    return findings
