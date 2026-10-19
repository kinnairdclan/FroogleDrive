import os

import pytest
from werkzeug.exceptions import NotFound

from app import fs


def test_resolve_inside(data_root):
    assert fs.resolve(data_root, "sub/b.txt") == str(data_root / "sub" / "b.txt")
    assert fs.resolve(data_root, "") == str(data_root)


@pytest.mark.parametrize("rel", ["..", "../outside/secret.txt", "sub/../../outside",
                                 "/etc/passwd", "escape", "escape/secret.txt",
                                 "sub/escape.txt", "missing", "a\x00.txt"])
def test_resolve_rejects(data_root, rel):
    with pytest.raises(NotFound):
        fs.resolve(data_root, rel)


def test_list_dir_hides_escaping_symlinks(data_root):
    names = [e["name"] for e in fs.list_dir(data_root, str(data_root))]
    assert names == ["sub", "a.txt", "inner-link.txt"]  # dirs first, no "escape"
    sub = [e["name"] for e in fs.list_dir(data_root, str(data_root / "sub"))]
    assert sub == ["deep", "b.txt"]


def test_walk_files(data_root):
    names = sorted(arc for _, arc in fs.walk_files(data_root / "sub"))
    assert names == ["b.txt", "deep/c.txt"]


def test_list_dir_skips_broken_symlink(data_root):
    os.symlink(data_root / "gone.txt", data_root / "broken.txt")
    assert "broken.txt" not in [e["name"] for e in fs.list_dir(data_root, str(data_root))]


def test_list_dir_unreadable(data_root, monkeypatch):
    def denied(path):
        raise PermissionError(path)
    monkeypatch.setattr(fs.os, "scandir", denied)
    assert fs.list_dir(data_root, str(data_root)) == []


def test_breadcrumbs():
    assert fs.breadcrumbs("") == []
    assert fs.breadcrumbs("a/b/c") == [("a", "a"), ("b", "a/b"), ("c", "a/b/c")]
