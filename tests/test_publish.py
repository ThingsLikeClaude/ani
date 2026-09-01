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


if __name__ == "__main__":
    unittest.main()
