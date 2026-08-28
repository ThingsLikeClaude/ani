# Contributing to ani

Thanks for being here. ani is a small protocol with a small surface, and the two most useful
things you can bring are: **an adapter for a harness you actually use**, and **a correction ani
got wrong**.

Everything below is about making those two easy.

## Contents

- [Contributing an adapter](#contributing-an-adapter)
- [The pairwise cross-review rule](#the-pairwise-cross-review-rule)
- [Code rules](#code-rules)
- [Changing SKILL.md wording](#changing-skillmd-wording)
- [Reporting a bug](#reporting-a-bug)

---

## Contributing an adapter

An adapter teaches ani to run on one more harness. It lives at
`skills/ani/references/adapters/<harness>.md` and describes, for that harness:

1. how a skill or instruction file is loaded (this is what makes Tier 0 work);
2. whether deterministic hooks exist, and if so how to register one;
3. where session transcripts live, if `bootstrap` can mine them;
4. what the platform's rewind / reset actions are called, for the TRIAGE step.

Items 2–4 are optional. Item 1 is not — without it there is no Tier 0, and Tier 0 is the whole
portability claim.

### The acceptance test

An adapter is accepted when it has been demonstrated, not when it looks plausible. The test is
one sentence:

> **In a clean session on that harness, send a correction like "아니 그게 아니라 …" (or its
> equivalent in your language), and an F file must actually appear in `.ani/patterns/`.**

Attach a real transcript of that run to the PR — the prompt you sent, the agent's reply, and the
resulting file. Redact freely; we need the shape of the exchange, not your code. A transcript
with the correction and the created file path is enough.

If the F file does not appear, that is a genuinely useful finding too — open an issue with the
transcript instead. It usually means the harness needs a different instruction-loading path, and
that is worth knowing before anyone writes the adapter.

### One verified harness at a time

We would rather ship three adapters that provably work than a support matrix of nine that
nobody has run. Please open one PR per harness. If you want to add a harness that already has a
stub, say so in the issue first so two people do not write it twice.

---

## The pairwise cross-review rule

**Any new adapter or core change must be reviewed against its adjacent documents.**

This rule exists because of our own build. All four defects we found before launch lived
*between* files, not inside any one of them: a hook emitted a marker the skill did not consume,
an adapter documented a command the core no longer used, a schema field was renamed in one place
and not the other. Each file was internally consistent and individually reviewable. The bugs
were in the seams.

So when you change something, read its neighbour:

| You changed | Read alongside it |
| --- | --- |
| an adapter | `skills/ani/SKILL.md` — does the core actually consume what this adapter produces? |
| `SKILL.md` | every file in `skills/ani/references/adapters/` — does any adapter now describe a step that no longer exists? |
| `references/schemas.md` | `templates/F-template.md`, `templates/S-template.md`, and any example in `README.md` |
| `hooks/ani_trigger.py` | `references/adapters/claude-code.md` — the marker format is a contract between them |
| `scripts/ani_bootstrap.py` | `references/adapters/bootstrap.md` |

Say in the PR description which neighbour you read. "Checked against SKILL.md, the nudge marker
format is unchanged" is a complete answer.

---

## Code rules

There is very little code here on purpose, and it stays that way.

- **Python standard library only.** No third-party dependencies, ever. If a task needs a
  package, it probably belongs in the agent's hands rather than in a script.
- **No network calls, ever.** ani reads and writes local files and nothing else. A PR that adds
  a socket, an HTTP client, telemetry, or a version check will be declined — this is a promise
  the README makes to users, not a preference.
- **Tests use stdlib `unittest`**, live in `tests/`, and run from the repo root with
  `python -m unittest discover -s tests`. New behaviour in a script needs a test; a fixture goes
  in `tests/fixtures/`.
- **Encoding: UTF-8 without BOM, LF newlines, one trailing newline.** For every file, including
  markdown. Hooks must never emit anything but their expected output on stdout.
- **Fail silently in hooks.** A hook that crashes must exit quietly rather than break the user's
  turn. The core protocol works without it, so a broken hook is a missing hint, not an error.

---

## Changing SKILL.md wording

`SKILL.md` is the protocol. Its wording is load-bearing, so a wording change needs a **rationale
in the PR: what correction or failure motivated it?**

Concretely: which instruction was ambiguous, what did an agent do because of that ambiguity, and
what does your wording make it do instead. "Clearer" is not a rationale; "an agent read step 4
as optional and skipped the excerpt, here is the transcript" is.

This is the same standard ani applies to its own patterns — a change with no failure behind it
is advice, and advice is what we are trying to replace.

---

## Reporting a bug

Issue templates are in [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE). The most valuable
bug report for this project is a **reproduction excerpt**: the exchange where ani did the wrong
thing, quoted. If you can paste the user turn, the agent turn, and what you expected instead,
that is a complete report.
