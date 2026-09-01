#!/usr/bin/env python3
"""Tests for scripts/ani_publish.py.

Stdlib unittest only (no pytest), loaded via importlib exactly like
tests/test_bootstrap.py.

These tests never touch the real `~/.ani` or `~/.claude`: every repo is built
under a temp directory nested past the hook's five-level parent walk; see
tests/test_knowledge.py.

Run:  python -m unittest discover -s tests -v
"""

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


if __name__ == "__main__":
    unittest.main()
