# slopscan

Detect AI-generated slop in a codebase before it ships.

## When to use

Run slopscan after writing or generating Python code and before committing —
especially code drafted with AI assistance. It catches placeholders,
dead code, sycophantic comments, over-engineering, hallucinated names,
and copy-pasted blocks.

## How to run

```bash
slopscan [path]                 # terminal report
slopscan --format md src/       # markdown report for review
slopscan --fail-under 80 .      # CI gate: fail if cleanliness < 80
```

## Interpreting scores

- Each file gets a **slop score 0–100** (0 = clean). The repo score is a
  lines-of-code-weighted mean.
- Findings come in three severities:
  - **bad** (✖) — fix these. Hallucinated names, big duplicated blocks,
    blatant "implement later" placeholders.
  - **warn** (⚠) — consider fixing. TODOs, dead code, long functions,
    commented-out code.
  - **info** (ℹ) — style nits. Sycophantic comments, single-use helpers.
- A detector is conservative by design: a miss beats a false positive.
  If a finding looks wrong, ignore that instance — don't distrust the tool.

## CI usage

```yaml
- run: pip install slopscan
- run: slopscan --fail-under 80 --format md src/ >> $GITHUB_STEP_SUMMARY
```
