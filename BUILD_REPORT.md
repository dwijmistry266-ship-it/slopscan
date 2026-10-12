# slopscan — Build Report

Built 2026-10-12. Local path: `~/workspace/github-work/slopscan`
Status: complete, tested, dogfooded. **Not pushed — no GitHub repo created** (parent handles that).

## What was built

**slopscan 0.1.0** — "AI slop detector for your codebase." A stdlib-only
Python CLI (3.9+) that statically scans Python files for low-quality
patterns typical of AI-generated code and reports a 0–100 slop score per
file plus a repo summary.

### Package layout

```
slopscan/
  __init__.py        # __version__ = "0.1.0"
  __main__.py        # python -m slopscan
  cli.py             # argparse: path, --format term|json|md,
                     #   --min-severity, --fail-under N, --ignore, --no-color
  registry.py        # detector registry + single-parse runner
  findings.py        # Finding dataclass (split out to avoid a
                     #   detectors.py / detectors/ package name collision)
  scoring.py         # weights info=1/warn=3/bad=10; density-normalized 0–100
  reporters.py       # term (colored, ✖/⚠/ℹ), json, md
  skill.md           # agent skill definition (38 lines)
  detectors/
    placeholders.py  # TODO/FIXME/XXX/HACK, "implement later", .../pass-only/
                     #   NotImplementedError-only bodies
    deadcode.py      # unreachable code, unused imports, unused local constants
    comments.py      # sycophantic comments, restating comments,
                     #   commented-out code blocks
    overengineering.py  # >60-line functions, nesting >4, single-use
                     #   _private helpers, __init__-plus-one-method classes
    hallucinations.py   # called/used-but-never-defined names (bad);
                     #   skips star-imports, builtins, string annotations
    duplication.py      # near-duplicate ≥6-line blocks via normalized
                     #   token hashing; ≥15 lines rated bad
tests/               # 8 files, 84 tests, tmp_path fixtures,
                     #   positive AND negative cases per detector
examples/sloppy_sample.py  # deliberately sloppy demo file (README output
                           #   is generated from it, verified byte-for-byte)
README.md, LICENSE (MIT, Dwij Mistry), pyproject.toml (setuptools,
  console script slopscan=slopscan.cli:main), .gitignore,
  .github/workflows/ci.yml (pytest 3.9–3.12 + self-scan dogfood gate),
  assets/banner.svg (neon cyberpunk SVG)
```

### Design decisions worth noting

- **Conservative detectors**: every detector documents its limits in its
  docstring; a false positive is treated as worse than a miss.
- **`--fail-under N`** gates on *cleanliness* (100 − slop): `--fail-under 80`
  fails CI when cleanliness drops below 80. Documented in README + `--help`.
- **Scoring is density-normalized**: `min(100, 100 × weight / LOC)`, so long
  files aren't punished for length; repo score is LOC-weighted mean.
- **Bug found by dogfooding**: `from __future__ import annotations` was
  flagged as an unused import — fixed the detector to skip `__future__`
  imports, with a regression test.

## Test results

- **84 passed, 0 failed** (`pytest tests/ -q`, Python 3.12; CI matrix covers
  3.9–3.12).
- Every detector has positive and negative cases (code that must NOT be
  flagged: abstractmethod stubs, `__all__` re-exports, `# noqa` imports,
  `TYPE_CHECKING` blocks, star imports, builtins, recursive helpers,
  exception subclasses, short idioms).

## Self-scan (dogfood)

`python -m slopscan slopscan --fail-under 90` →
**31 findings (✖0 bad, ⚠5 warn, ℹ26 info) · repo slop 3/100 ·
cleanliness 97/100 · exit 0.**

The 5 remaining warns are honest complexity flags inside the detector
implementations themselves (AST visitors nest; the duplication matcher is
75 lines) — no `bad` findings, gate passes.

## Demo

`slopscan examples/sloppy_sample.py` → 19 findings (✖3 ⚠9 ℹ7),
slop 44/100. Output pasted verbatim into README (verified byte-for-byte).

## Notes for the parent (repo creation)

- Do NOT publish anything mentioning GTU/BBIT/diploma/DDCET — verified
  absent from the entire tree (grep check clean).
- Suggested repo name: `slopscan`; description: "AI slop detector for your
  codebase — static analysis that flags low-quality patterns typical of
  AI-generated Python."
- `dist/` contains a locally built sdist + wheel (gitignored).
