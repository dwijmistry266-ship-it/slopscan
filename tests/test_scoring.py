"""Tests for scoring: weights, file scores, repo aggregation."""

from slopscan.findings import Finding
from slopscan.scoring import (cleanliness, file_score, repo_score,
                              severity_counts, weight)


def _f(sev):
    return Finding("d", sev, "x.py", 1, "m")


def test_weights():
    assert weight(_f("info")) == 1
    assert weight(_f("warn")) == 3
    assert weight(_f("bad")) == 10


def test_clean_file_scores_zero():
    assert file_score([], 100) == 0


def test_empty_file_scores_zero():
    assert file_score([_f("bad")], 0) == 0


def test_score_scales_with_density():
    # One bad (10) in 100 lines -> 10.
    assert file_score([_f("bad")], 100) == 10
    # Same finding in 20 lines -> 50. Density matters, not count.
    assert file_score([_f("bad")], 20) == 50


def test_score_caps_at_100():
    many = [_f("bad")] * 50
    assert file_score(many, 10) == 100


def test_mixed_severities():
    # info(1) + warn(3) + bad(10) = 14 in 100 lines -> 14.
    findings = [_f("info"), _f("warn"), _f("bad")]
    assert file_score(findings, 100) == 14


def test_cleanliness_is_inverse():
    assert cleanliness(0) == 100
    assert cleanliness(100) == 0
    assert cleanliness(30) == 70


def test_severity_counts():
    findings = [_f("info"), _f("info"), _f("warn"), _f("bad")]
    assert severity_counts(findings) == {"info": 2, "warn": 1, "bad": 1}


def test_repo_score_loc_weighted():
    # Clean big file dominates a sloppy stub.
    assert repo_score([(0, 1000), (100, 10)]) == 1


def test_repo_score_empty():
    assert repo_score([]) == 0
    assert repo_score([(50, 0)]) == 0
