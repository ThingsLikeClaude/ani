"""Regression tests for hooks/ani_trigger.py (stdlib unittest, no pytest).

Every case drives the real script through a subprocess with controlled stdin,
because the contract under test is a process contract: exact stdout bytes and
an exit code that is always 0.

Run from the repo root: python -m unittest discover -s tests
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO_ROOT, "hooks", "ani_trigger.py")

NUDGE_RE = re.compile(
    r"^\[ani-nudge v1\] session=(?P<session>\S+) prompt_sha=(?P<sha>[0-9a-f]{8}) "
    r"pattern=(?P<slug>[a-z0-9\-]+)$"
)
HINT_RE = re.compile(r"^\[ani-hint v1\] patterns=(?P<ids>\S+)$")

INDEX_FIXTURE = """# ani INDEX

Cache only — pattern frontmatter is canonical.

| id | status | scope | keywords | summary | updated |
| --- | --- | --- | --- | --- | --- |
| S-dark-mode-tokens | active | project | background, css, dark-mode | Use when changing themed colors | 2026-08-28 |
| S-korean-background | active | project | 배경색, 테마 | Use when a background color change is requested | 2026-08-28 |
| S-old-css-hack | retired | project | background, css | Use when ... (retired) | 2026-08-20 |
| S-needs-review | review-needed | project | background | Use when ... (under review) | 2026-08-21 |
| S-form-validation | provisional | project | forms, validation | Use when wiring form validation | 2026-08-27 |
| F-20260828-a1b2c3d4 | captured | project | background, css | Failure: changed text color | 2026-08-28 |
"""

CAP_INDEX_FIXTURE = """| id | status | scope | keywords | summary | updated |
| --- | --- | --- | --- | --- | --- |
| S-widget-one | active | project | widget | Use when one | 2026-08-28 |
| S-widget-two | active | project | widget | Use when two | 2026-08-28 |
| S-widget-three | active | project | widget | Use when three | 2026-08-28 |
| S-widget-four | active | project | widget | Use when four | 2026-08-28 |
| S-widget-prov | provisional | project | widget | Use when provisional | 2026-08-28 |
"""


def sha8(prompt):
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]


class HookTestCase(unittest.TestCase):
    """Base: every run happens inside an isolated dir with no ambient .ani."""

    def setUp(self):
        self.empty_dir = tempfile.mkdtemp(prefix="ani-empty-")
        self.addCleanup(shutil.rmtree, self.empty_dir, True)

    def make_project(self, index_text=INDEX_FIXTURE):
        project = tempfile.mkdtemp(prefix="ani-proj-")
        self.addCleanup(shutil.rmtree, project, True)
        store = os.path.join(project, ".ani")
        os.makedirs(store)
        with open(os.path.join(store, "INDEX.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(index_text)
        return project

    def run_hook(self, payload=None, raw=None, cwd=None, project_dir=None, io_encoding="utf-8"):
        env = os.environ.copy()
        env.pop("PYTHONIOENCODING", None)
        if io_encoding:
            env["PYTHONIOENCODING"] = io_encoding
        env.pop("CLAUDE_PROJECT_DIR", None)
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = project_dir
        data = raw if raw is not None else json.dumps(payload, ensure_ascii=False)
        proc = subprocess.run(
            [sys.executable, HOOK],
            input=data.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd or self.empty_dir,
            env=env,
        )
        return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")

    def context_of(self, stdout):
        """Assert the stdout contract and return additionalContext."""
        stripped = stdout.strip()
        self.assertTrue(stripped, "expected output, got nothing")
        self.assertNotIn("\n", stripped, "hook stdout must be a single line")
        payload = json.loads(stripped)
        self.assertEqual(list(payload.keys()), ["hookSpecificOutput"])
        block = payload["hookSpecificOutput"]
        self.assertEqual(block["hookEventName"], "UserPromptSubmit")
        return block["additionalContext"]

    def nudge_of(self, context):
        for line in context.splitlines():
            match = NUDGE_RE.match(line)
            if match:
                return match
        self.fail("no [ani-nudge v1] marker in context:\n" + context)

    def hint_ids_of(self, context):
        for line in context.splitlines():
            match = HINT_RE.match(line)
            if match:
                return match.group("ids").split(",")
        self.fail("no [ani-hint v1] marker in context:\n" + context)


class CorrectionDetectionTests(HookTestCase):
    def test_korean_correction_marker_format_and_sha(self):
        prompt = "아니 그게 아니라 배경색만 바꾸라고"
        code, out, _ = self.run_hook(
            {"prompt": prompt, "session_id": "sess-123", "cwd": self.empty_dir}
        )
        self.assertEqual(code, 0)
        context = self.context_of(out)
        match = self.nudge_of(context)
        self.assertEqual(match.group("session"), "sess-123")
        self.assertEqual(match.group("sha"), sha8(prompt))
        self.assertEqual(match.group("slug"), "ko-ani-geuge-anira")
        self.assertIn("Correction signal detected", context)
        self.assertIn("follow the ani skill protocol.", context)
        self.assertNotIn("[ani-hint", context)

    def test_english_correction(self):
        prompt = "No, that's not what I asked for - I meant the sidebar."
        code, out, _ = self.run_hook(
            {"prompt": prompt, "session_id": "s-en", "cwd": self.empty_dir}
        )
        self.assertEqual(code, 0)
        match = self.nudge_of(self.context_of(out))
        self.assertTrue(match.group("slug").startswith("en-"), match.group("slug"))
        self.assertEqual(match.group("sha"), sha8(prompt))

    def test_nae_mareun_variant(self):
        prompt = "내 말은 배경색만 바꾸라는 거였어"
        code, out, _ = self.run_hook(
            {"prompt": prompt, "session_id": "s-ko2", "cwd": self.empty_dir}
        )
        self.assertEqual(code, 0)
        match = self.nudge_of(self.context_of(out))
        self.assertEqual(match.group("slug"), "ko-nae-mareun")

    def test_mixed_utterance_still_nudges(self):
        # Praise + correction in one utterance. The hook does not filter;
        # separating the topic rounds is the skill's job (spec 3.3.1).
        prompt = "좋은데 근데 그게 아니라 이쪽이야"
        code, out, _ = self.run_hook(
            {"prompt": prompt, "session_id": "s-mix", "cwd": self.empty_dir}
        )
        self.assertEqual(code, 0)
        match = self.nudge_of(self.context_of(out))
        self.assertEqual(match.group("slug"), "ko-geuge-anira")

    def test_japanese_and_chinese_phrases(self):
        cases = {
            "いや、そうじゃなくて、左のカラムです": "ja-iya-sou-janakute",
            "不是这个意思，我说的是背景色": "zh-bushi-zhege-yisi",
        }
        for prompt, slug in cases.items():
            code, out, _ = self.run_hook(
                {"prompt": prompt, "session_id": "s-cjk", "cwd": self.empty_dir}
            )
            self.assertEqual(code, 0)
            self.assertEqual(self.nudge_of(self.context_of(out)).group("slug"), slug)

    def test_non_correction_prompt_is_silent(self):
        code, out, _ = self.run_hook(
            {
                "prompt": "Add a login button to the header, please.",
                "session_id": "s-quiet",
                "cwd": self.empty_dir,
            }
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")


class RobustnessTests(HookTestCase):
    def test_invalid_or_empty_stdin_is_silent(self):
        for raw in ("", "   ", "not json at all", "[]", "null", '{"prompt":', "\x00\x01"):
            code, out, _ = self.run_hook(raw=raw)
            self.assertEqual(code, 0, "raw=%r" % raw)
            self.assertEqual(out, "", "raw=%r" % raw)

    def test_missing_keys_do_not_crash(self):
        payloads = [
            {},
            {"session_id": "only-session"},
            {"prompt": None, "cwd": None, "session_id": None},
            {"prompt": ""},
            {"prompt": 42},
        ]
        for payload in payloads:
            code, out, _ = self.run_hook(payload)
            self.assertEqual(code, 0, repr(payload))
            self.assertEqual(out, "", repr(payload))

    def test_korean_survives_a_legacy_locale(self):
        # Claude Code does not set PYTHONIOENCODING. On a cp949 Windows box a
        # text-mode stdin read would die on the first Korean byte and the hook
        # would silently do nothing — exactly the case it exists for.
        prompt = "아니 그게 아니라 배경색만 바꾸라고"
        for encoding in (None, "cp949", "cp1252"):
            code, out, _ = self.run_hook(
                {"prompt": prompt, "session_id": "s-locale", "cwd": self.empty_dir},
                io_encoding=encoding,
            )
            self.assertEqual(code, 0, "encoding=%r" % encoding)
            match = self.nudge_of(self.context_of(out))
            self.assertEqual(match.group("sha"), sha8(prompt), "encoding=%r" % encoding)
            self.assertEqual(match.group("slug"), "ko-ani-geuge-anira")

    def test_utf8_bom_payload_is_accepted(self):
        prompt = "그거 말고 다른 거"
        raw = "﻿" + json.dumps(
            {"prompt": prompt, "session_id": "s-bom"}, ensure_ascii=False
        )
        code, out, _ = self.run_hook(raw=raw)
        self.assertEqual(code, 0)
        self.assertEqual(self.nudge_of(self.context_of(out)).group("slug"), "ko-geugeo-malgo")

    def test_missing_session_and_cwd_still_nudges(self):
        # No session_id, no cwd: the marker must still be well formed so the
        # skill can reject it deterministically.
        prompt = "그거 말고 다른 파일이라고"
        code, out, _ = self.run_hook({"prompt": prompt})
        self.assertEqual(code, 0)
        match = self.nudge_of(self.context_of(out))
        self.assertEqual(match.group("session"), "unknown")
        self.assertEqual(match.group("sha"), sha8(prompt))


class ProactiveHintTests(HookTestCase):
    def test_hint_from_index_keywords(self):
        project = self.make_project()
        code, out, _ = self.run_hook(
            {
                "prompt": "Update the dark-mode background for the settings panel",
                "session_id": "s-hint",
                "cwd": project,
            },
            cwd=project,
        )
        self.assertEqual(code, 0)
        context = self.context_of(out)
        self.assertEqual(self.hint_ids_of(context), ["S-dark-mode-tokens"])
        self.assertIn("consult them before acting.", context)
        self.assertNotIn("[ani-nudge", context)

    def test_korean_particle_stripping(self):
        # INDEX keyword "배경색" vs prompt token "배경색을".
        project = self.make_project()
        code, out, _ = self.run_hook(
            {"prompt": "배경색을 바꿔줘", "session_id": "s-particle", "cwd": project},
            cwd=project,
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            self.hint_ids_of(self.context_of(out)), ["S-korean-background"]
        )

    def test_correction_and_hint_combined(self):
        project = self.make_project()
        prompt = "아니 그게 아니라 배경색을 바꾸라고"
        code, out, _ = self.run_hook(
            {"prompt": prompt, "session_id": "s-both", "cwd": project}, cwd=project
        )
        self.assertEqual(code, 0)
        context = self.context_of(out)
        nudge = self.nudge_of(context)
        self.assertEqual(nudge.group("slug"), "ko-ani-geuge-anira")
        self.assertEqual(nudge.group("sha"), sha8(prompt))
        self.assertEqual(self.hint_ids_of(context), ["S-korean-background"])
        self.assertLess(context.index("[ani-nudge"), context.index("[ani-hint"))

    def test_retired_and_review_needed_are_excluded_and_cap_is_three(self):
        project = self.make_project(CAP_INDEX_FIXTURE)
        code, out, _ = self.run_hook(
            {"prompt": "the widget layout is off", "session_id": "s-cap", "cwd": project},
            cwd=project,
        )
        self.assertEqual(code, 0)
        ids = self.hint_ids_of(self.context_of(out))
        self.assertEqual(len(ids), 3)
        self.assertNotIn("S-widget-prov", ids)  # active outranks provisional

        blocked = self.make_project()
        code, out, _ = self.run_hook(
            {"prompt": "check the css please", "session_id": "s-blocked", "cwd": blocked},
            cwd=blocked,
        )
        self.assertEqual(code, 0)
        ids = self.hint_ids_of(self.context_of(out))
        self.assertEqual(ids, ["S-dark-mode-tokens"])
        self.assertNotIn("S-old-css-hack", ids)
        self.assertNotIn("S-needs-review", ids)

    def test_claude_project_dir_wins_over_cwd(self):
        project = self.make_project()
        code, out, _ = self.run_hook(
            {"prompt": "tweak the 배경색 tokens", "session_id": "s-env", "cwd": self.empty_dir},
            cwd=self.empty_dir,
            project_dir=project,
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.hint_ids_of(self.context_of(out)), ["S-korean-background"])

    def test_garbage_index_still_nudges(self):
        project = self.make_project()
        with open(os.path.join(project, ".ani", "INDEX.md"), "wb") as fh:
            fh.write(b"\xff\xfe not a table at all |||| \x00\x00")
        prompt = "아니 그게 아니라니까"
        code, out, _ = self.run_hook(
            {"prompt": prompt, "session_id": "s-garbage", "cwd": project}, cwd=project
        )
        self.assertEqual(code, 0)
        context = self.context_of(out)
        self.assertEqual(self.nudge_of(context).group("sha"), sha8(prompt))
        self.assertNotIn("[ani-hint", context)

    def test_no_index_means_no_hint(self):
        code, out, _ = self.run_hook(
            {"prompt": "dark-mode background css", "session_id": "s-none", "cwd": self.empty_dir}
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")


class OutputContractTests(HookTestCase):
    def test_output_is_single_line_valid_json(self):
        project = self.make_project()
        prompt = "아니 그게 아니라 dark-mode 배경색을 바꾸라고"
        code, out, err = self.run_hook(
            {"prompt": prompt, "session_id": "s-json", "cwd": project}, cwd=project
        )
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out.count("\n"), 1, repr(out))
        self.assertTrue(out.endswith("\n"))
        payload = json.loads(out)
        self.assertEqual(
            set(payload["hookSpecificOutput"]),
            {"hookEventName", "additionalContext"},
        )
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(self.nudge_of(context).group("sha"), sha8(prompt))
        self.assertTrue(self.hint_ids_of(context))


class ParticleUnitTests(unittest.TestCase):
    """White-box check of the Korean particle rule.

    The subprocess tests prove the observable behaviour; this one proves the
    particle path itself exists, since plain substring matching would hide it.
    """

    @classmethod
    def setUpClass(cls):
        import importlib.util

        sys.dont_write_bytecode = True  # keep hooks/ free of __pycache__
        spec = importlib.util.spec_from_file_location("ani_trigger", HOOK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.mod = module

    def test_particles_are_stripped_from_tokens(self):
        _, variants = self.mod.prompt_variants("배경색을 테마에서 폰트로 바꿔")
        for expected in ("배경색", "테마", "폰트"):
            self.assertIn(expected, variants, expected)

    def test_particle_is_not_stripped_from_a_bare_particle(self):
        _, variants = self.mod.prompt_variants("는 은 를")
        self.assertNotIn("", variants)

    def test_correction_slugs_are_ascii_and_unique(self):
        slugs = [slug for slug, _ in self.mod.CORRECTION_PHRASES]
        self.assertEqual(len(slugs), len(set(slugs)))
        for slug in slugs:
            self.assertRegex(slug, r"^[a-z]{2}-[a-z0-9\-]+$")


if __name__ == "__main__":
    unittest.main()
