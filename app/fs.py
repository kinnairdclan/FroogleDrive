"""Filesystem access confined to a root directory.

Only plain os calls are used, so this works on any filesystem the OS can mount.
"""
import os

from flask import abort


def is_within(root, path):
    """True if `path` is `root` or lies beneath it. Both must be real paths."""
    return os.path.commonpath([root, path]) == root


def resolve(root, rel):
    """Resolve `rel` under `root`, following symlinks, or abort with 404.

    Rejects `..` traversal, absolute paths and symlinks that escape `root`.
    """
    real_root = os.path.realpath(root)
    try:
        target = os.path.realpath(os.path.join(real_root, rel or ""))
    except ValueError:  # e.g. embedded NUL byte
        abort(404)
    if not is_within(real_root, target) or not os.path.exists(target):
        abort(404)
    return target


def relative(root, path):
    """Path of `path` relative to `root`, with "" for the root itself."""
    rel = os.path.relpath(path, os.path.realpath(root))
    return "" if rel == "." else rel


def breadcrumbs(rel):
    """[(name, rel_path), ...] for each component of `rel`."""
    crumbs, parts = [], []
    for part in rel.split(os.sep) if rel else []:
        parts.append(part)
        crumbs.append((part, os.path.join(*parts)))
    return crumbs


def list_dir(root, path):
    """Entries of directory `path`, directories first, then by name.

    Each entry: name, rel (relative to `root`), is_dir, size, mtime.
    Symlinks pointing outside `root` and unreadable entries are skipped.
    """
    real_root = os.path.realpath(root)
    entries = []
    try:
        it = os.scandir(path)
    except OSError:
        return entries
    with it:
        for entry in it:
            try:
                if entry.is_symlink():
                    target = os.path.realpath(entry.path)
                    if not is_within(real_root, target):
                        continue
                st = entry.stat()
                is_dir = entry.is_dir()
            except OSError:
                continue
            entries.append({
                "name": entry.name,
                "rel": relative(real_root, os.path.join(path, entry.name)),
                "is_dir": is_dir,
                "size": st.st_size,
                "mtime": st.st_mtime,
            })
    entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
    return entries


def walk_files(root):
    """Yield (absolute_path, archive_name) for every file under `root`.

    Symlinked directories are not descended into; symlinked files are only
    included when they resolve inside `root`.
    """
    real_root = os.path.realpath(root)
    for dirpath, _dirnames, filenames in os.walk(real_root, followlinks=False):
        for name in filenames:
            full = os.path.join(dirpath, name)
            target = os.path.realpath(full)
            if is_within(real_root, target) and os.path.isfile(target):
                yield target, os.path.relpath(full, real_root)
