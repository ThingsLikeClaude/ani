#!/usr/bin/env python3
"""ani publish miner — candidates for `/ani git`.

A DUMB MINER, like ani_bootstrap.py. It reads the global store and the repo,
prints a candidate digest, and decides nothing. Every write is the agent
acting on a per-row selection the user made: schemas.md §2 forbids relocation
inferred from a bulk approval.

Usage:
    python ani_publish.py [--repo PATH] [--global-store PATH] [--out FILE]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

__version__ = "1.0.0"

_REMOTE_RE = re.compile(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?\Z")


def _git(args, cwd):
    """Run a read-only git command; empty string when git cannot answer."""
    try:
        out = subprocess.run(
            ["git"] + args, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError):
        return ""
    if out.returncode != 0:
        return ""
    return out.stdout.decode("utf-8", errors="replace").strip()


def repo_slug(repo_root: str):
    """``owner/repo`` from the origin remote, else the directory name.

    The remote is preferred because two checkouts can share a directory name
    and mean different projects.
    """
    if not repo_root or not os.path.isdir(repo_root):
        return None
    remote = _git(["remote", "get-url", "origin"], repo_root)
    if remote:
        match = _REMOTE_RE.search(remote)
        if match:
            return "%s/%s" % (match.group(1), match.group(2))
    return os.path.basename(os.path.abspath(repo_root)) or None


def slug_matches(recorded, current) -> bool:
    """Equal slugs, or equal last segments — F files predate the slug rule."""
    if not recorded or not current:
        return False
    if recorded == current:
        return True
    return recorded.rsplit("/", 1)[-1] == current.rsplit("/", 1)[-1]


MAX_PATTERN_BYTES = 64 * 1024
MAX_PATTERNS = 200


def read_front_matter(path: str) -> dict:
    """Every ``key: value`` in the leading ``---`` block. Values stay raw."""
    front = {}
    try:
        if os.path.getsize(path) > MAX_PATTERN_BYTES:
            return front
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read(MAX_PATTERN_BYTES)
    except OSError:
        return front
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if inside:
                break
            inside = True
            continue
        if not inside:
            if not stripped:
                continue
            break
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            front[key.strip()] = value.strip()
    return front


def parse_list(raw) -> list:
    if not raw:
        return []
    return [item.strip() for item in raw.strip("[]").split(",") if item.strip()]


def global_patterns(store: str) -> list:
    """Every ``S-*.md`` in a store, in filename order, capped."""
    directory = os.path.join(store, "patterns")
    try:
        names = sorted(n for n in os.listdir(directory)
                       if n.startswith("S-") and n.endswith(".md"))
    except OSError:
        return []
    out = []
    for name in names[:MAX_PATTERNS]:
        path = os.path.join(directory, name)
        front = read_front_matter(path)
        if not front.get("id"):
            continue
        out.append({
            "id": front["id"],
            "path": path,
            "summary": front.get("summary", ""),
            "status": front.get("status", ""),
            "keywords": parse_list(front.get("keywords")),
            "compiled_from": parse_list(front.get("compiled_from")),
        })
    return out


def group_a(patterns: list, store: str, slug) -> list:
    """Patterns whose source failures name this repo."""
    if not slug:
        return []
    out = []
    for pattern in patterns:
        for failure_id in pattern["compiled_from"]:
            path = os.path.join(store, "patterns", failure_id + ".md")
            recorded = read_front_matter(path).get("project")
            if slug_matches(recorded, slug):
                out.append(pattern)
                break
    return out
