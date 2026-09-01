# Store Boundary Flows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user publish selected global patterns into a repo's `.ani/` overlay with `/ani git`, and make an applied overlay pattern say when it shadowed the user's own or was written by someone else.

**Architecture:** Flow A follows the bootstrap precedent — a dumb stdlib miner (`scripts/ani_publish.py`) emits a candidate digest, and the agent presents it, takes per-row selections, and writes the files. The miner decides nothing. Flow B is agent behaviour only: two facts it already has (the shadowed-id line from the session-start injection, and `git log`) turned into one disclosure sentence in `SKILL.md`.

**Tech Stack:** Python 3.8+, standard library only. No pytest — `unittest` driven through `subprocess`, matching `tests/test_bootstrap.py`.

**Spec:** `docs/specs/2026-09-01-store-boundary-flows.md`

## Global Constraints

- **Stdlib only.** No third-party imports in `scripts/` or `hooks/`. Scripts may import from `hooks/` — `scripts/ani_doctor.py` already imports `ani_trigger`.
- **The miner decides nothing.** It emits advisory candidates; every write is the agent acting on an explicit per-row selection. `schemas.md` §2: relocation is never inferred from a bulk approval.
- **Copy, never move.** The global original is byte-identical after a publish.
- **`scope` mirrors the store.** A file written into the overlay is `scope: project`.
- **Nothing outside a store is written.** No commits, branches, or git config. Reading git is fine.
- **Tests never touch the real `~/.ani` or `~/.claude`.** Point `--claude-dir` / `ANI_GLOBAL_STORE` at temp dirs, and nest temp working directories six levels (`a/b/c/d/e/f`) so the hook's five-level parent walk cannot reach the developer's home. Copy `make_deep_dir` from `tests/test_knowledge.py`.
- **Console encoding.** This project's tests set `PYTHONIOENCODING=utf-8`; the miner writes its digest with `sys.stdout.buffer.write(...encode("utf-8"))`, as `ani_bootstrap.py` does.
- **Exit code 0 whenever the script ran**, including "found nothing" and "no such directory".

---

### Task 1: Repo slug

**Files:**
- Create: `scripts/ani_publish.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Produces: `repo_slug(repo_root: str) -> str | None` — `"owner/repo"` from the `origin` remote, else the basename of `repo_root`, else `None` when `repo_root` is not a directory.
- Produces: `slug_matches(recorded: str, current: str) -> bool` — true when equal, or when the last `/`-segments are equal.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_publish.py
import os, shutil, subprocess, sys, tempfile, unittest, importlib.util
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_DIR = TESTS_DIR.parent
SCRIPT = REPO_DIR / "scripts" / "ani_publish.py"


def load_script():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("ani_publish_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublishTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_script()

    def make_deep_dir(self, prefix):
        """Below the hook's five-level parent walk; see tests/test_knowledge.py."""
        root = tempfile.mkdtemp(prefix=prefix)
        self.addCleanup(shutil.rmtree, root, True)
        deep = os.path.join(root, "a", "b", "c", "d", "e", "f")
        os.makedirs(deep)
        return deep

    def make_repo(self, remote=None, name="myrepo"):
        parent = self.make_deep_dir("ani-pub-")
        root = os.path.join(parent, name)
        os.makedirs(root)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        if remote:
            subprocess.run(["git", "remote", "add", "origin", remote],
                           cwd=root, check=True)
        return root


class RepoSlugTests(PublishTestCase):

    def test_slug_comes_from_the_origin_remote(self):
        root = self.make_repo("https://github.com/acme/widgets.git")
        self.assertEqual(self.mod.repo_slug(root), "acme/widgets")

    def test_ssh_remote_is_parsed_too(self):
        root = self.make_repo("git@github.com:acme/widgets.git")
        self.assertEqual(self.mod.repo_slug(root), "acme/widgets")

    def test_without_a_remote_the_directory_name_is_the_slug(self):
        root = self.make_repo(None, name="lonely")
        self.assertEqual(self.mod.repo_slug(root), "lonely")

    def test_a_missing_directory_has_no_slug(self):
        self.assertIsNone(self.mod.repo_slug(os.path.join(self.make_deep_dir("x-"), "nope")))

    def test_a_bare_name_matches_a_full_slug(self):
        """F files written before the slug rule carry whatever was chosen then."""
        self.assertTrue(self.mod.slug_matches("widgets", "acme/widgets"))
        self.assertTrue(self.mod.slug_matches("acme/widgets", "acme/widgets"))
        self.assertFalse(self.mod.slug_matches("other", "acme/widgets"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_publish -v`
Expected: FAIL — `ani_publish.py` does not exist, so `load_script()` raises `FileNotFoundError`.

- [ ] **Step 3: Write the minimal implementation**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_publish -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/ani_publish.py tests/test_publish.py
git commit -m "feat(publish): derive the repo slug from the origin remote"
```

---

### Task 2: Group (a) — patterns captured in this repo

**Files:**
- Modify: `scripts/ani_publish.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `repo_slug`, `slug_matches` from Task 1.
- Produces: `read_front_matter(path: str) -> dict` — every `key: value` line in the leading `---` block, values as raw strings.
- Produces: `parse_list(raw: str) -> list[str]` — `"[a, b]"` and `"a, b"` both to `["a", "b"]`.
- Produces: `global_patterns(store: str) -> list[dict]` — one dict per `patterns/S-*.md` with keys `id`, `path`, `summary`, `keywords` (list), `compiled_from` (list), `status`.
- Produces: `group_a(patterns, store, slug) -> list[dict]` — the subset whose `compiled_from` F files carry a matching `project`.

- [ ] **Step 1: Write the failing tests**

```python
S_TEMPLATE = """---
id: {id}
compiled_from: [{froms}]
date_compiled: 2026-08-28
keywords: [{keywords}]
scope: global
status: active
summary: {summary}
---

## Situation
When it happens.
"""

F_TEMPLATE = """---
id: {id}
status: compiled
date: 2026-08-28
{project_line}trigger_quote: "no, not that"
keywords: [widget]
---

## Intent
Something.
"""


class CandidateTestCase(PublishTestCase):

    def make_store(self):
        store = self.make_deep_dir("ani-pub-store-")
        os.makedirs(os.path.join(store, "patterns"))
        return store

    def write_pattern(self, store, name, text):
        path = os.path.join(store, "patterns", name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        return path

    def write_s(self, store, pattern_id, froms="F-20260828-aaaaaaaa",
                keywords="widget", summary="Use when widgets misbehave"):
        return self.write_pattern(store, pattern_id + ".md", S_TEMPLATE.format(
            id=pattern_id, froms=froms, keywords=keywords, summary=summary))

    def write_f(self, store, pattern_id, project=None):
        line = "project: %s\n" % project if project else ""
        return self.write_pattern(store, pattern_id + ".md",
                                  F_TEMPLATE.format(id=pattern_id, project_line=line))


class GroupATests(CandidateTestCase):

    def test_front_matter_stops_at_the_closing_fence(self):
        store = self.make_store()
        path = self.write_s(store, "S-alpha")
        front = self.mod.read_front_matter(path)
        self.assertEqual(front["id"], "S-alpha")
        self.assertEqual(front["scope"], "global")
        self.assertNotIn("## Situation", front)

    def test_a_list_parses_with_or_without_brackets(self):
        self.assertEqual(self.mod.parse_list("[a, b]"), ["a", "b"])
        self.assertEqual(self.mod.parse_list("a, b"), ["a", "b"])
        self.assertEqual(self.mod.parse_list(""), [])

    def test_a_pattern_whose_failure_names_this_repo_is_in_group_a(self):
        store = self.make_store()
        self.write_f(store, "F-20260828-aaaaaaaa", project="acme/widgets")
        self.write_s(store, "S-alpha")
        found = self.mod.group_a(self.mod.global_patterns(store), store, "acme/widgets")
        self.assertEqual([p["id"] for p in found], ["S-alpha"])

    def test_a_pattern_from_another_repo_is_not(self):
        store = self.make_store()
        self.write_f(store, "F-20260828-aaaaaaaa", project="other/thing")
        self.write_s(store, "S-alpha")
        self.assertEqual(self.mod.group_a(self.mod.global_patterns(store), store,
                                          "acme/widgets"), [])

    def test_a_failure_with_no_project_field_is_not_guessed_into_group_a(self):
        """The schema says omit rather than guess; the miner honours that."""
        store = self.make_store()
        self.write_f(store, "F-20260828-aaaaaaaa", project=None)
        self.write_s(store, "S-alpha")
        self.assertEqual(self.mod.group_a(self.mod.global_patterns(store), store,
                                          "acme/widgets"), [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_publish.GroupATests -v`
Expected: FAIL with `AttributeError: module has no attribute 'read_front_matter'`.

- [ ] **Step 3: Write the minimal implementation**

```python
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
    """Every ``S-*.md`` in a store, newest filename first, capped."""
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_publish -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/ani_publish.py tests/test_publish.py
git commit -m "feat(publish): group candidates captured in this repo"
```

---

### Task 3: Group (b) — keyword overlap with this repo

**Files:**
- Modify: `scripts/ani_publish.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: `global_patterns`, `group_a` from Task 2.
- Produces: `repo_vocabulary(repo_root: str) -> set[str]` — tokens from the top two path levels of `git ls-files`.
- Produces: `group_b(patterns, vocabulary, exclude_ids) -> list[dict]` — patterns whose `keywords` intersect the vocabulary and are not already in group (a).

- [ ] **Step 1: Write the failing tests**

```python
class GroupBTests(CandidateTestCase):

    def make_repo_with_files(self, *paths):
        root = self.make_repo("https://github.com/acme/widgets.git")
        for rel in paths:
            full = os.path.join(root, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write("x\n")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        return root

    def test_vocabulary_covers_the_top_two_path_levels(self):
        root = self.make_repo_with_files("hooks/trigger.py", "docs/deep/nested/note.md")
        vocab = self.mod.repo_vocabulary(root)
        self.assertIn("hooks", vocab)
        self.assertIn("docs", vocab)
        self.assertIn("deep", vocab)
        self.assertNotIn("nested", vocab)

    def test_a_keyword_hit_puts_a_pattern_in_group_b(self):
        store = self.make_store()
        self.write_s(store, "S-hooky", keywords="hooks, python")
        patterns = self.mod.global_patterns(store)
        found = self.mod.group_b(patterns, {"hooks"}, exclude_ids=set())
        self.assertEqual([p["id"] for p in found], ["S-hooky"])

    def test_group_a_members_are_not_repeated_in_group_b(self):
        store = self.make_store()
        self.write_s(store, "S-hooky", keywords="hooks")
        patterns = self.mod.global_patterns(store)
        self.assertEqual(self.mod.group_b(patterns, {"hooks"}, {"S-hooky"}), [])

    def test_no_overlap_means_no_candidates(self):
        store = self.make_store()
        self.write_s(store, "S-hooky", keywords="unrelated")
        patterns = self.mod.global_patterns(store)
        self.assertEqual(self.mod.group_b(patterns, {"hooks"}, set()), [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_publish.GroupBTests -v`
Expected: FAIL with `AttributeError: module has no attribute 'repo_vocabulary'`.

- [ ] **Step 3: Write the minimal implementation**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_publish -v`
Expected: PASS, 15 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/ani_publish.py tests/test_publish.py
git commit -m "feat(publish): offer keyword-overlap candidates as a labelled guess"
```

---

### Task 4: The digest — collision column and CLI

**Files:**
- Modify: `scripts/ani_publish.py`
- Test: `tests/test_publish.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3.
- Produces: `overlay_ids(repo_root: str) -> set[str]` — ids already in `<repo>/.ani/patterns/`.
- Produces: `render_digest(group_a_rows, group_b_rows, taken, slug, store) -> str`.
- Produces: `main(argv=None) -> int` for `--repo`, `--global-store`, `--out`.

- [ ] **Step 1: Write the failing tests**

```python
class DigestTests(CandidateTestCase):

    def run_script(self, *args):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT)] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return (completed.returncode,
                completed.stdout.decode("utf-8"),
                completed.stderr.decode("utf-8"))

    def test_an_id_already_in_the_overlay_is_flagged(self):
        root = self.make_repo("https://github.com/acme/widgets.git")
        overlay = os.path.join(root, ".ani", "patterns")
        os.makedirs(overlay)
        with open(os.path.join(overlay, "S-alpha.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nid: S-alpha\n---\n")
        self.assertEqual(self.mod.overlay_ids(root), {"S-alpha"})

    def test_the_digest_names_both_groups_and_says_group_b_is_a_guess(self):
        store = self.make_store()
        self.write_f(store, "F-20260828-aaaaaaaa", project="acme/widgets")
        self.write_s(store, "S-alpha")
        self.write_s(store, "S-beta", froms="F-20260828-bbbbbbbb", keywords="hooks")
        root = self.make_repo("https://github.com/acme/widgets.git")
        code, out, err = self.run_script("--repo", root, "--global-store", store)
        self.assertEqual(code, 0, err)
        self.assertIn("captured in this repo", out)
        self.assertIn("keyword overlap", out)
        self.assertIn("a guess", out)
        self.assertIn("S-alpha", out)

    def test_the_digest_says_nothing_was_written(self):
        store = self.make_store()
        root = self.make_repo("https://github.com/acme/widgets.git")
        code, out, _ = self.run_script("--repo", root, "--global-store", store)
        self.assertEqual(code, 0)
        self.assertIn("nothing was written", out.lower())

    def test_a_missing_store_exits_zero(self):
        root = self.make_repo("https://github.com/acme/widgets.git")
        code, out, err = self.run_script("--repo", root,
                                         "--global-store", os.path.join(root, "nope"))
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_publish.DigestTests -v`
Expected: FAIL with `AttributeError: module has no attribute 'overlay_ids'`.

- [ ] **Step 3: Write the minimal implementation**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest discover -s tests -v`
Expected: PASS. Whole suite green — 224 existing plus 19 new.

- [ ] **Step 5: Commit**

```bash
git add scripts/ani_publish.py tests/test_publish.py
git commit -m "feat(publish): render the candidate digest with a collision column"
```

---

### Task 5: `/ani git` in the protocol

**Files:**
- Modify: `skills/ani/SKILL.md` (Subcommands table)
- Create: `skills/ani/references/adapters/publish.md`

**Interfaces:**
- Consumes: `scripts/ani_publish.py` from Tasks 1–4.
- Produces: the agent-facing procedure for A1, A4, A5, A6.

- [ ] **Step 1: Add the subcommand row**

In `skills/ani/SKILL.md`, in the Subcommands table, after the `/ani bootstrap` row:

```markdown
| `/ani git` | List global patterns worth sharing with this repo's team, and copy the ones the user selects into the project overlay — see `references/adapters/publish.md` |
```

- [ ] **Step 2: Write the adapter**

Create `skills/ani/references/adapters/publish.md` with these sections, in order:

1. **What this is** — publishing, not sorting. The global original is never moved or deleted; a copy is written. The user does not lose a pattern by teaching it.
2. **Overlay check (A1)** — if `<repo>/.ani/` is absent, ask before creating it, saying the directory is committed and read by everyone who clones the repo. A refusal ends the command with nothing written.
3. **Run the miner** — by absolute path from the install root, as `/ani doctor` is run (SKILL.md References): `python <install root>/scripts/ani_publish.py --repo <repo> --out <tmp>`. No `scripts/` present → say the subcommand is unavailable in a skill-directory-only install and stop.
4. **Present the digest** — the table as emitted, both groups, with the keyword-overlap group's "this is a guess" caveat intact. Never merge the groups.
5. **Selection (A4)** — the user picks rows individually. **Never offer an "all" option**; `schemas.md` §2 forbids relocation inferred from a bulk approval. Selecting one row says nothing about any other.
6. **Write (A5)** — for each selected id: copy `<global>/patterns/<id>.md` to `<repo>/.ani/patterns/<id>.md`, change `scope: global` to `scope: project` in the copy and nothing else, leave the original untouched, then regenerate the overlay `INDEX.md` from the frontmatter of what is now in it, respecting 60 rows / 6KB. An id already in the overlay is **skipped and named**, never overwritten — that file is someone else's work, and overwriting is a second instruction the user has to give.
7. **Stop (A6)** — report the files written and the ids skipped. Do not commit, branch, or push; say committing is the user's to do.

- [ ] **Step 3: Verify the docs stay consistent**

Run: `python -m unittest discover -s tests -v`
Expected: PASS — no test reads these files, so this confirms nothing regressed.

Then confirm by hand that `references/adapters/publish.md` never uses the words "approve all" or "bulk", and that step 6 says `scope: project`.

- [ ] **Step 4: Commit**

```bash
git add skills/ani/SKILL.md skills/ani/references/adapters/publish.md
git commit -m "docs(skill): specify /ani git, the outbound publish flow"
```

---

### Task 6: Inbound disclosure

**Files:**
- Modify: `skills/ani/SKILL.md` (Path A, after the `provisional` disclosure step)

**Interfaces:**
- Consumes: the shadowed-id line already emitted by `hooks/ani_session_start.py`.

- [ ] **Step 1: Add the rule to Path A**

Insert after the existing step 6 (the `provisional` disclosure) in `skills/ani/SKILL.md`:

```markdown
6b. An S from the **project overlay** is disclosed once per id per session when
   either is true: the session-start injection named it as shadowing a global
   pattern of the same id, or its file was last written by someone else
   (`git log -1 --format=%ae -- <path>` against `git config user.email`).
   "Applying `S-commit-style` from the project overlay (written by a teammate;
   your global store has a pattern under the same id) — tell me if it is wrong."
   Drop whichever half is false. This **does not block**: say it and carry on,
   the same way the handshake notice is said once and then never again that
   session. No git, no configured email, or an untracked file → evaluate the
   shadowing half alone and never guess at authorship.
```

- [ ] **Step 2: Verify nothing regressed**

Run: `python -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add skills/ani/SKILL.md
git commit -m "docs(skill): disclose a project pattern's provenance on application"
```

---

### Task 7: Changelog and cross-links

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `skills/ani/references/adapters/bootstrap.md` (see-also line)

- [ ] **Step 1: Add the changelog entries**

Under `## [Unreleased]`, add an `### Added` section:

```markdown
### Added

- **`/ani git` publishes selected patterns into the repo overlay.** A stdlib miner
  (`scripts/ani_publish.py`) lists global patterns worth sharing with this repo — those
  whose source failures recorded this repo's slug, plus a second, separately labelled group
  matched only on keyword overlap with the repo's own vocabulary. The user selects rows one
  at a time; there is no "approve all", because `schemas.md` §2 forbids relocation inferred
  from a bulk approval. Selected patterns are **copied**, not moved: publishing is teaching,
  and the global original is untouched. An id already in the overlay is skipped and named,
  never overwritten. Nothing is committed — that stays the user's to do.
- **A project pattern says where it came from.** An overlay `S` is disclosed once per id per
  session when it shadowed a global pattern of the same id, or when git shows someone else
  wrote it. It never blocks: ani's guarantee is that no automatic step beats a user veto, not
  that every step asks first.
```

- [ ] **Step 2: Cross-link the adapters**

In `skills/ani/references/adapters/bootstrap.md`, under "Known limits", add:

```markdown
- **Bootstrap fills the global store, never a repo's.** Publishing a pattern to a repo
  overlay is `/ani git` (`adapters/publish.md`), a separate decision the user makes per
  pattern.
```

- [ ] **Step 3: Run the whole suite**

Run: `python -m unittest discover -s tests -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md skills/ani/references/adapters/bootstrap.md
git commit -m "docs: record the store-boundary flows"
```

---

## Spec coverage

| Spec section | Task |
| --- | --- |
| A1 overlay check | 5 (step 2, section 2) |
| A2 repo slug | 1 |
| A2 group (a) | 2 |
| A2 group (b) | 3 |
| A3 table, collision column, clustering | 4 |
| A4 per-row selection | 5 (section 5) |
| A5 copy, `scope: project`, skip collisions, INDEX | 5 (section 6) |
| A6 stop, no commit | 4 (digest wording) + 5 (section 7) |
| B1–B5 inbound disclosure and degradation | 6 |
| Invariant 3 (copy never moves) | 5 (section 6), asserted by hand |
| Out of scope: consent gates, PRs, hint path, reverse move | not implemented, by design |

**Known deviation:** A3 specifies keyword-Jaccard sorting so related subjects sit together. Tasks 1–4 group and label but list rows in filename order. Sorting is presentation-only, adds a scoring function and its tests, and the two labelled groups already carry most of the grouping value. It is deliberately deferred rather than silently dropped — if the first real run reads as an unsorted pile, add it as Task 8.
