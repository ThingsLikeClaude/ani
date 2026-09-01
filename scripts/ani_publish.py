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
