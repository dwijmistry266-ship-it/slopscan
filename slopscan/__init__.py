"""slopscan — AI slop detector for your codebase.

Static analysis that scans Python files for low-quality patterns typical of
AI-generated code ("slop") and reports a slop score per file plus a repo
summary.
"""

__version__ = "0.1.0"
__author__ = "Dwij Mistry"

from slopscan.findings import Finding  # noqa: F401  (re-exported API)
from slopscan.registry import run_detectors  # noqa: F401
from slopscan.scoring import file_score, repo_score  # noqa: F401
