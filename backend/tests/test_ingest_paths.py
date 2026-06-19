"""Tests for canonical.ingest.paths.to_repo_relative_posix - the path-emit seam."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from yen_gov.canonical.ingest.paths import to_repo_relative_posix


def test_relativises_absolute_under_root(tmp_path: Path):
    repo_root = tmp_path
    p = repo_root / "datasets" / "data" / "x.csv"
    assert to_repo_relative_posix(p, repo_root=repo_root) == "datasets/data/x.csv"


def test_result_is_posix_no_backslash(tmp_path: Path):
    repo_root = tmp_path
    p = repo_root / "a" / "b" / "c.htm"
    rel = to_repo_relative_posix(p, repo_root=repo_root)
    assert rel == "a/b/c.htm"
    assert "\\" not in rel


def test_relative_input_is_repo_root_relative(tmp_path: Path):
    # An already-relative input is interpreted as repo-root-relative, not rejected.
    assert to_repo_relative_posix(Path("datasets/x.csv"), repo_root=tmp_path) == "datasets/x.csv"


def test_root_itself_is_dot(tmp_path: Path):
    assert to_repo_relative_posix(tmp_path, repo_root=tmp_path) == "."


def test_fails_fast_on_escape(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    outside = tmp_path / "outside.csv"
    with pytest.raises(ValueError, match="escapes repo_root"):
        to_repo_relative_posix(outside, repo_root=repo_root)


def test_fails_fast_on_parent_escape(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    with pytest.raises(ValueError):
        to_repo_relative_posix(Path("../escape.csv"), repo_root=repo_root)


@pytest.mark.skipif(os.name != "nt", reason="drive letters are a Windows-only concept")
def test_fails_fast_on_other_drive(tmp_path: Path):
    # A path on a different drive cannot be made relative to repo_root and must
    # never leak its drive-qualified form into a log line.
    with pytest.raises(ValueError):
        to_repo_relative_posix(Path("Z:/somewhere/x.csv"), repo_root=tmp_path)
