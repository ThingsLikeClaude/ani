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


MAX_TRACKED_FILES = 5000


def repo_vocabulary(repo_root: str) -> set:
    """Tokens from the top two path levels of the tracked files.

    Two levels because `hooks/`, `scripts/`, `docs/specs/` name what a repo is
    about, while a fourth-level filename names one detail of it. Works on a repo
    whose overlay is still empty, which is the first-publish case.
    """
    listing = _git(["ls-files"], repo_root)
    vocabulary = set()
    if not listing:
        return vocabulary
    for line in listing.splitlines()[:MAX_TRACKED_FILES]:
        for part in line.replace("\\", "/").split("/")[:2]:
            token = os.path.splitext(part)[0].strip().lower()
            if len(token) >= 2:
                vocabulary.add(token)
    return vocabulary


def group_b(patterns: list, vocabulary: set, exclude_ids: set) -> list:
    """Keyword overlap. A guess, and labelled as one wherever it is shown."""
    if not vocabulary:
        return []
    return [
        pattern for pattern in patterns
        if pattern["id"] not in exclude_ids
        and vocabulary & {k.lower() for k in pattern["keywords"]}
    ]


def overlay_ids(repo_root: str) -> set:
    directory = os.path.join(repo_root, ".ani", "patterns")
    try:
        names = os.listdir(directory)
    except OSError:
        return set()
    return {os.path.splitext(n)[0] for n in names
            if n.startswith("S-") and n.endswith(".md")}


def _rows(patterns, taken, label):
    lines = []
    for pattern in patterns:
        collision = "yes — will be skipped" if pattern["id"] in taken else "no"
        lines.append("| `%s` | %s | %s | %s | %s |" % (
            pattern["id"], pattern["summary"] or "(no summary)",
            ", ".join(pattern["compiled_from"]) or "(none)", collision, label))
    return lines


def render_digest(a_rows, b_rows, taken, slug, store) -> str:
    out = ["# ani publish candidates", "",
           "Advisory only — **nothing was written to any store.** The agent running",
           "`/ani git` presents these rows and writes only the ones you select, one by",
           "one. A row is never published as a side effect of selecting another.", "",
           "- Repo slug: `%s`" % (slug or "(unknown)"),
           "- Global store: `%s`" % store,
           "- Captured in this repo: %d" % len(a_rows),
           "- Keyword overlap: %d" % len(b_rows), ""]
    if not a_rows and not b_rows:
        out += ["No candidates. Nothing in the global store points at this repo.", ""]
        return "\n".join(out)
    out += ["| id | summary | compiled from | already in overlay | group |",
            "| --- | --- | --- | --- | --- |"]
    out += _rows(a_rows, taken, "captured in this repo")
    out += _rows(b_rows, taken, "keyword overlap")
    out += ["",
            "Rows marked **keyword overlap** are *a guess*: their source failures never",
            "recorded which repo they came from, so the miner matched vocabulary instead.",
            "Read them before selecting. Rows marked *captured in this repo* carry a",
            "recorded `project` slug.", ""]
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ani_publish.py",
        description=("List global patterns worth publishing into this repo's .ani/ "
                     "overlay. Read-only: never writes into any store."))
    parser.add_argument("--repo", default=os.getcwd(),
                        help="Repo root (default: the working directory)")
    parser.add_argument("--global-store", default=os.path.expanduser("~/.ani"),
                        help="Global store directory (default: ~/.ani)")
    parser.add_argument("--out", default="",
                        help="Write the digest to FILE (UTF-8, LF) instead of stdout")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    repo = os.path.abspath(os.path.expanduser(args.repo))
    store = os.path.abspath(os.path.expanduser(args.global_store))
    slug = repo_slug(repo)
    patterns = global_patterns(store)
    a_rows = group_a(patterns, store, slug)
    b_rows = group_b(patterns, repo_vocabulary(repo), {p["id"] for p in a_rows})
    digest = render_digest(a_rows, b_rows, overlay_ids(repo), slug, store)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(digest)
    else:
        sys.stdout.buffer.write(digest.encode("utf-8"))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
