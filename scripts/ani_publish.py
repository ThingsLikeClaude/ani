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
import shutil
import subprocess
import sys

__version__ = "1.1.0"

_REMOTE_RE = re.compile(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?\Z")


def _resolve_git() -> str:
    """Absolute ``git``, resolved once against PATH — never the working directory.

    Windows' CreateProcess searches the calling process's current directory
    ahead of PATH, and `/ani git` typically runs from a repo root that may be
    freshly cloned third-party code: a `git.exe` sitting there would be the one
    executed. `shutil.which` prefers the current directory on Windows for the
    same reason (and does so whatever ``path`` is passed), so a hit there is
    discarded and PATH is walked directly instead. Falls back to the bare name
    when nothing is found — no worse than before.
    """
    here = os.path.abspath(os.curdir)
    found = shutil.which("git")
    if found:
        found = os.path.abspath(found)
        if os.path.dirname(found) != here:
            return found
    exts = [""]
    if os.name == "nt":
        exts = [e for e in os.environ.get("PATHEXT", ".EXE").split(os.pathsep) if e]
    for entry in os.environ.get("PATH", os.defpath).split(os.pathsep):
        entry = entry.strip().strip('"')
        if not entry or os.path.abspath(entry) == here:
            continue
        for ext in exts:
            candidate = os.path.join(entry, "git" + ext)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return os.path.abspath(candidate)
    return "git"


GIT = _resolve_git()


def _git(args, cwd):
    """Run a read-only git command; empty string when git cannot answer."""
    try:
        out = subprocess.run(
            [GIT] + args, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, ValueError):
        return ""
    if out.returncode != 0:
        return ""
    return out.stdout.decode("utf-8", errors="replace").strip()


def is_git_repo(repo_root: str) -> bool:
    """Reading git is fine; nothing outside a store is ever written."""
    return _git(["rev-parse", "--is-inside-work-tree"], repo_root) == "true"


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
    """Equal slugs, or a bare recorded name equal to the current last segment.

    Asymmetric on purpose. The last-segment fallback exists only for F files
    written before the slug rule, which carry a bare ``ani`` that should still
    match ``ThingsLikeClaude/ani``. Two full slugs must match in full: group (a)
    is labelled provenance, and ``evilcorp/widgets`` is not ``acme/widgets``.
    """
    if not recorded or not current:
        return False
    if recorded == current:
        return True
    if "/" not in recorded:
        return recorded == current.rsplit("/", 1)[-1]
    return False


MAX_PATTERN_BYTES = 64 * 1024
MAX_PATTERNS = 200

QUARANTINED = ("review-needed", "retired")


def new_scan() -> dict:
    """The counts behind the digest's verdict, like ani_bootstrap.py's ``## Scan``."""
    return {"store_found": False, "is_git_repo": False, "patterns_seen": 0,
            "scanned": 0, "quarantined": 0, "oversized": 0, "unreadable": 0,
            "over_cap": 0}


def _bump(scan, key, amount=1):
    if scan is not None:
        scan[key] = scan.get(key, 0) + amount


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


def global_patterns(store: str, scan: dict = None) -> list:
    """Every publishable ``S-*.md`` in a store, in filename order, capped.

    Quarantined patterns (`review-needed`, `retired`) are held back. They are
    excluded from search because a wrong manual cannot be re-applied
    (`schemas.md` §2), so they are not publishable candidates either. The count
    goes into ``scan`` and the digest prints it: the miner may narrow what it
    offers, never invisibly.
    """
    directory = os.path.join(store, "patterns")
    try:
        names = sorted(n for n in os.listdir(directory)
                       if n.startswith("S-") and n.endswith(".md"))
    except OSError:
        return []
    if scan is not None:
        scan["store_found"] = True
        scan["patterns_seen"] = len(names)
        scan["over_cap"] = max(len(names) - MAX_PATTERNS, 0)
    out = []
    for name in names[:MAX_PATTERNS]:
        path = os.path.join(directory, name)
        _bump(scan, "scanned")
        front = read_front_matter(path)
        if not front.get("id"):
            try:
                oversized = os.path.getsize(path) > MAX_PATTERN_BYTES
            except OSError:
                oversized = False
            _bump(scan, "oversized" if oversized else "unreadable")
            continue
        if front.get("status", "").strip().lower() in QUARANTINED:
            _bump(scan, "quarantined")
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


def _cell(text: str) -> str:
    """One pipe in a summary shifts every cell after it — including `group`."""
    return text.replace("|", "\\|")


def _rows(patterns, taken, label):
    lines = []
    for pattern in patterns:
        collision = "yes — will be skipped" if pattern["id"] in taken else "no"
        lines.append("| `%s` | %s | %s | %s | %s | %s |" % (
            _cell(pattern["id"]), _cell(pattern["summary"] or "(no summary)"),
            _cell(pattern["status"] or "(unknown)"),
            _cell(", ".join(pattern["compiled_from"]) or "(none)"),
            collision, label))
    return lines


def _scan_block(a_rows, b_rows, slug, store, scan) -> list:
    """The counts behind the verdict, so a thin digest can be read for why."""
    git_note = ("yes" if scan["is_git_repo"] else
                "no (group (b) matches against `git ls-files`, so it cannot populate)")
    return [
        "## Scan", "",
        "- Miner version: %s" % __version__,
        "- Repo slug: `%s`" % (slug or "(unknown)"),
        "- Git repo: %s" % git_note,
        "- Global store: `%s`" % store,
        "- Store directory found: %s" % ("yes" if scan["store_found"] else "no"),
        "- Patterns found: %d" % scan["patterns_seen"],
        "- Patterns scanned: %d" % scan["scanned"],
        "- Quarantined patterns held back: %d (`review-needed` / `retired` — "
        "excluded from search, so not publishable)" % scan["quarantined"],
        "- Provisional candidates offered: %d (auto-compiled, never human-approved "
        "— offered, but not vouched for)"
        % sum(1 for row in a_rows + b_rows if row["status"] == "provisional"),
        "- Patterns skipped over the size cap: %d (cap %d bytes per file)"
        % (scan["oversized"], MAX_PATTERN_BYTES),
        "- Patterns skipped over the count cap: %d (cap %d per run, filename order)"
        % (scan["over_cap"], MAX_PATTERNS),
        "- Unreadable patterns skipped: %d (no `id` in the front matter)"
        % scan["unreadable"],
        "- Captured in this repo: %d" % len(a_rows),
        "- Keyword overlap: %d" % len(b_rows),
        "",
    ]


def _empty_note(store, scan) -> list:
    """Never a confident false negative: say which of the two this was."""
    if not scan["store_found"]:
        out = ["No candidates — **the global store directory was not found.**",
               "`%s` does not exist or could not be read, so nothing was scanned at"
               % os.path.join(store, "patterns"),
               "all. That is not the same as having nothing to publish.",
               ""]
    else:
        out = ["No candidates. Nothing the miner could read in this store points at",
               "this repo.", ""]
    return out + [
        "Check the inputs before concluding there is nothing to share:",
        "`--global-store` must name the store you actually use (`config.md` can move",
        "it and this script does not read `config.md`), and `--repo` must point at a",
        "git repo — without one there is no vocabulary for group (b) to match, and no",
        "`origin` remote for the repo slug.",
        "",
    ]


def render_digest(a_rows, b_rows, taken, slug, store, scan) -> str:
    out = ["# ani publish candidates", "",
           "Advisory only — **nothing was written to any store.** The agent running",
           "`/ani git` presents these rows and writes only the ones you select, one by",
           "one. A row is never published as a side effect of selecting another.", ""]
    out += _scan_block(a_rows, b_rows, slug, store, scan)
    if scan["over_cap"] or scan["oversized"]:
        out += ["**A resource cap fired during this scan.** Some patterns were skipped,",
                "so the candidates below are not a complete reading of the store: the",
                "count cap truncates in filename order and a pattern over the size cap is",
                "skipped whole. Trim or split the store before treating this digest as",
                "exhaustive.", ""]
    if not a_rows and not b_rows:
        out += _empty_note(store, scan)
        return "\n".join(out)
    out += ["| id | summary | status | compiled from | already in overlay | group |",
            "| --- | --- | --- | --- | --- | --- |"]
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
    scan = new_scan()
    scan["is_git_repo"] = is_git_repo(repo)
    slug = repo_slug(repo)
    patterns = global_patterns(store, scan)
    a_rows = group_a(patterns, store, slug)
    b_rows = group_b(patterns, repo_vocabulary(repo), {p["id"] for p in a_rows})
    digest = render_digest(a_rows, b_rows, overlay_ids(repo), slug, store, scan)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(digest)
    else:
        sys.stdout.buffer.write(digest.encode("utf-8"))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
