#!/usr/bin/env python3
"""Tests for the ani skill's YAML frontmatter (stdlib unittest, no pytest).

Why this is its own file: the other two test modules exercise processes. The
hook is a subprocess with an exact stdout contract; the miner is a script with
an exact digest. `skills/ani/SKILL.md` is neither — it is a document, and the
only part of it a test can hold to account is the part a model reads before it
has read anything else.

That part matters more than it looks. The spec's second layer is the claim that
"the model loads the skill on any rephrasing, in any language", and that layer
is what is supposed to rescue the corrections the hook's regexes walk past. But
the nine example phrases in `description:` were all drawn from the same
`CORRECTION_PHRASES` table that measured 9% recall, so both layers were written
out of one vocabulary and share one blind spot. `프런트가 안되는데?` is not a
rephrasing of "no, that's not what I meant" — it is a symptom report, and
nothing in the description tells the model to read it as a correction.

The model's judgement is not unit-testable. Its input is. This file pins the
input.

Run from the repo root: python -m unittest discover -s tests
"""

import importlib.util
import io
import os
import re
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
SKILL = os.path.join(REPO_ROOT, "skills", "ani", "SKILL.md")
HOOK = os.path.join(REPO_ROOT, "hooks", "ani_trigger.py")

# The same five families the hook's table is measured against
# (docs/specs/2026-09-06-correction-detection-recall.md, C1).
FAMILY_SLUG_PREFIXES = {
    "A": "ko-ani-",       # sentence-initial 아니
    "B": "ko-recur-",     # stated recurrence
    "C": "ko-defect-",    # defect report
    "D": "ko-verdict-",   # negative verdict
    "E": "ko-reversal-",  # reversal
}

# Only double quotes. The description is English prose containing apostrophes
# ("that's not what I meant"), so a single quote is punctuation here, not a
# delimiter.
_QUOTED_RE = re.compile(u'"([^"]+)"|“([^”]+)”')


def load_trigger_module():
    """Import the hook so its table can say which family an example belongs to.

    The frontmatter is checked against the detector rather than against a list
    written out here, because a list written out here is a second vocabulary —
    the exact thing C2 exists to prevent — and it would let the description and
    the table drift apart while both tests stayed green.
    """
    sys.dont_write_bytecode = True  # keep hooks/ free of __pycache__
    spec = importlib.util.spec_from_file_location("ani_trigger_for_skill", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_frontmatter_description(path):
    """Return the `description:` value of the leading `---` block.

    Hand-rolled rather than PyYAML: the repo's runtime code is stdlib-only and
    its tests hold the same line, and this is a scalar off the top of a file.
    """
    with io.open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    if not lines or lines[0].strip() != "---":
        raise AssertionError("%s does not open with a --- frontmatter fence" % path)
    block = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        block.append(line)
    if not closed:
        raise AssertionError("%s never closes its frontmatter fence" % path)
    for position, line in enumerate(block):
        match = re.match(r"^description:\s*(.*)$", line)
        if not match:
            continue
        parts = [match.group(1)]
        for continuation in block[position + 1:]:
            if re.match(r"^\S+\s*:", continuation):
                break
            parts.append(continuation.strip())
        value = " ".join(part for part in parts if part).strip()
        if not value:
            raise AssertionError("%s has an empty description:" % path)
        return value
    raise AssertionError("%s has no description: key in its frontmatter" % path)


def quoted_examples(description):
    """The phrases the description offers the model as examples."""
    found = []
    for groups in _QUOTED_RE.findall(description):
        for group in groups:
            if group and group.strip():
                found.append(group.strip())
    return found


class SkillDescriptionExampleCoverageTests(unittest.TestCase):
    """The way in the hook does not own.

    A prompt the hook stayed silent on still reaches the model, and the
    description is the only thing standing between it and nothing at all. If
    the description's examples span the same families the table does, the
    second layer covers the first layer's misses. If they do not, a family the
    table gains is a family the model was never told about — the frontmatter is
    left behind, silently, by exactly the edit that was supposed to fix recall.
    """

    @classmethod
    def setUpClass(cls):
        cls.mod = load_trigger_module()

    def test_every_measured_family_has_an_example_in_the_skill_description(self):
        """Represented means: the detector attributes it to that family.

        Not a spelling check. An example counts for Family C when the hook's
        own table reads it as Family C, so the description cannot satisfy this
        with a phrase the table does not know, and the table cannot gain a
        family without the description gaining an example of it.
        """
        description = read_frontmatter_description(SKILL)
        examples = quoted_examples(description)
        self.assertTrue(
            examples, "the description offers the model no quoted examples at all"
        )

        attributed = {}
        for example in examples:
            slug = self.mod.detect_correction(example)
            if slug is not None:
                attributed.setdefault(slug, []).append(example)

        missing = [
            "%s (%s)" % (family, prefix)
            for family, prefix in sorted(FAMILY_SLUG_PREFIXES.items())
            if not any(slug.startswith(prefix) for slug in attributed)
        ]
        self.assertEqual(
            missing,
            [],
            "%d of 5 measured families have no example in the SKILL.md "
            "description: %s\n  examples found: %s\n  families they cover: %s"
            % (
                len(missing),
                ", ".join(missing),
                examples,
                sorted(attributed) or "(none)",
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
