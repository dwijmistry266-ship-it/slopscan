"""Tests for the CLI: collection, formats, filters, exit codes."""

import json
import os

from slopscan.cli import collect_files, main


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return str(path)


def test_collect_single_file(tmp_path):
    f = _write(tmp_path / "a.py", "x = 1\n")
    assert collect_files(f, []) == [f]


def test_collect_recursive_skips_hidden_and_caches(tmp_path):
    _write(tmp_path / "a.py", "x = 1\n")
    _write(tmp_path / ".hidden" / "b.py", "x = 1\n")
    _write(tmp_path / "__pycache__" / "c.py", "x = 1\n")
    _write(tmp_path / "notes.txt", "hi\n")
    found = collect_files(str(tmp_path), [])
    assert found == [str(tmp_path / "a.py")]


def test_collect_honors_ignore(tmp_path):
    _write(tmp_path / "a.py", "x = 1\n")
    _write(tmp_path / "gen_b.py", "x = 1\n")
    found = collect_files(str(tmp_path), ["gen_*"])
    assert found == [str(tmp_path / "a.py")]


def test_term_output(capsys, tmp_path):
    _write(tmp_path / "a.py", "# TODO: fix\nx = 1\n")
    assert main([str(tmp_path), "--no-color"]) == 0
    out = capsys.readouterr().out
    assert "slop" in out and "TODO" in out


def test_json_format_is_valid(capsys, tmp_path):
    _write(tmp_path / "a.py", "x = 1\n")
    assert main([str(tmp_path), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["files_scanned"] == 1
    assert "files" in data


def test_md_format(capsys, tmp_path):
    _write(tmp_path / "a.py", "# TODO: fix\nx = 1\n")
    assert main([str(tmp_path), "--format", "md"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Slopscan report")


def test_min_severity_filters(capsys, tmp_path):
    _write(tmp_path / "a.py", "# TODO: fix\nx = 1\n")
    assert main([str(tmp_path), "--format", "json",
                 "--min-severity", "bad"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["files"][0]["findings"] == []


def test_fail_under_passes_on_clean_repo(tmp_path):
    _write(tmp_path / "a.py", "x = 1\n")
    assert main([str(tmp_path), "--fail-under", "90"]) == 0


def test_fail_under_fails_on_sloppy_repo(tmp_path):
    _write(tmp_path / "a.py", "# TODO: fix\nimport os\nx = frobnicate()\n")
    assert main([str(tmp_path), "--fail-under", "90",
                 "--no-color"]) == 1


def test_missing_path_errors(tmp_path):
    try:
        main([str(tmp_path / "nope")])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("expected SystemExit")


def test_no_python_files_ok(capsys, tmp_path):
    assert main([str(tmp_path)]) == 0
    assert "no Python files" in capsys.readouterr().err


def test_unparseable_file_skipped(tmp_path):
    _write(tmp_path / "a.py", "def broken(:\n")
    assert main([str(tmp_path), "--format", "json"]) == 0
