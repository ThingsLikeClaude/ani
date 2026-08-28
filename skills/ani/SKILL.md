---
name: ani
description: Use when the user signals you misread their intent — "아니 그게 아니라", "그게 아니라", "그거 말고", "내 말은", "no, that's not what I meant", "not what I asked", "you misunderstood", "いや、そうじゃなくて", "不是这个意思" — or any rephrasing, in any language, that means "no, that's not it". Also use proactively before any non-trivial task in a repo that has a .ani/ directory, so recorded correction patterns are consulted before acting, and when the user types /ani, /ani ok <id>, or /ani bootstrap.
---

# ani — the "no, that's not it" protocol

## Overview

A user correction is a bug report delivered at the crime scene with the right
answer attached. ani never throws it away: it records each correction as a
failure pattern (**F**) file, compiles proven ones into success patterns (**S**)
carrying executable verification, and consults them before the same mistake
repeats.

Two entry paths. **Path A (proactive)** runs before non-trivial work and is the
one that prevents corrections. **Path B (the correction loop)** runs the moment
a correction lands.

## Store — files are the protocol

```
<project>/.ani/
├── INDEX.md                       # cache: one row per pattern (budget 60 rows / 6KB)
├── patterns/
│   ├── F-20260828-a1b2c3d4.md     # F-<YYYYMMDD>-<rand8>
│   └── S-dark-mode-tokens.md      # S-<slug>
└── config.md                      # optional overrides
```

Pattern frontmatter is the **source of truth**; INDEX.md is a regenerable cache.
On mismatch the frontmatter wins — regenerate the affected INDEX row on the spot.

No `.ani/` yet? Create it on the first capture (Step 4). Never write outside
`.ani/`. Field-by-field spec: `references/schemas.md`. Phrase hints:
`references/triggers.md`.

## Path A — consult before you act

1. If the repo has `.ani/`, read `.ani/INDEX.md` once at session start, and
   again before any non-trivial task (multi-file edit, new feature, refactor —
   anything you would plan before doing).
2. Match the request against INDEX `summary` fields. They are written in
   **use-when** form and are matched the way you pick a skill: semantically, not
   by keyword equality.
3. Open only the candidate pattern files. Never read the whole store.
4. Apply in this priority order — higher always wins:

| Rank | Source |
| --- | --- |
| 1 | The current user request |
| 2 | Safety and permission constraints |
| 3 | `scope: project` S patterns |
| 4 | `scope: global` S patterns |

5. Skip any S whose status is `review-needed` or `retired` — they are excluded
   from search so a wrong manual cannot be re-applied.
6. `provisional` S patterns rank below `active` and **must be disclosed on every
   application**, with the ID: "Applying provisional pattern
   `S-dark-mode-tokens` (auto-compiled, not yet human-approved) — tell me if it
   is wrong." The user can veto at any time.
7. Whenever a pattern shaped your action, cite its ID in your reply.

### Hook markers (optional Tier 1 adapters)

An adapter may prepend a marker to the user prompt. The core works without them.

| Marker | Meaning | How to consume |
| --- | --- | --- |
| `[ani-nudge v1] session=<id> prompt_sha=<8hex> pattern=<slug>` | deterministic correction detection | Consume **only** if `session` matches the current session and `prompt_sha` matches this turn's prompt. Otherwise ignore silently — it is a stale marker from another turn. |
| `[ani-hint v1] patterns=<S-id,...>` | keyword overlap between the prompt and INDEX | Treat as search hints. Still verify semantic fit; drop the ones that do not fit. |

Never echo markers back to the user. Absence of a marker never means "no
correction happened" — **you are the detector**, the markers are reinforcement.

## Path B — the correction loop

Runs whenever the user's turn *means* "you misread me", regardless of wording or
language. The phrase lists in `references/triggers.md` are hints; semantic
recognition is the detector.

### Step 1 — RESTATE (before anything else)

Restate the user's actual intent in one line, before fixing, searching, or
apologizing.

- Ask **at most one** question, and only if the intent is genuinely ambiguous.
- If the restatement reveals this was not a correction (a quotation, a joke, a
  new request), end the loop silently — no F file, no ceremony.

### Step 2 — SEARCH

- Read INDEX (if not already in context) and open candidate S files: `active`
  first, `provisional` allowed but disclosed, `review-needed`/`retired`
  excluded.
- **If a pattern you applied this session is what just got corrected**, that is a
  counterexample:
  - Write the F file (Step 4) with the S id in `keywords` and in `Misreading`,
    and add it to that S's `## Counter-examples` section.
  - Demote immediately: `active` → `review-needed` (excluded from search until
    re-approved); `provisional` → `retired` (immediately, no review — nobody
    ever approved it).
  - A demotion edits the S frontmatter **and** its INDEX row.

### Step 3 — FIX

Do the actual correction now. **Recording never blocks the fix.** If you can only
do one thing, fix.

### Step 4 — CAPTURE

- Get today's date from the `date` command (or the platform equivalent). **Never
  from memory or from context.**
- Create `.ani/patterns/F-<YYYYMMDD>-<rand8>.md` from `templates/F-template.md`.
  The random 8-char suffix is what makes concurrent sessions collision-free.
- `## Excerpt` is REQUIRED and must be a **self-contained verbatim** exchange:
  someone reading the F file alone, with no transcript access, must be able to
  reconstruct the failure.
- Add or refresh the INDEX row. Over budget (60 rows / 6KB)? Drop `archived` F
  rows and `retired` S rows first, then merge near-duplicate S patterns.
- If the project uses git and the user's conventions allow commits, commit the
  `.ani/` change on its own — never bundled with code changes.

### Step 5 — TRIAGE (context health)

Repeated corrections usually mean the context is polluted. The F file lives
outside the context window, so the context is now **disposable** — and several
fresh attempts can branch from the same F.

| Signal | Recommendation |
| --- | --- |
| First correction, simple misread | Continue in this session (default) |
| Second correction on the same topic, loop signs ("왜 자꾸", repeated failed attempts, your own self-contradiction) | Recommend rewinding to before the pollution point |
| Repeated failure, long session, heavy pollution | Recommend a fresh session that reads **only** `.ani/patterns/F-<id>.md` as its checkpoint |

These are **recommendations only** — the user decides. Never rewind, clear, or
restart on your own. Platform commands live in the adapters; name the action, not
the keystroke, unless an adapter document is loaded.

## Compiling F → S

Two paths. Human approval raises the trust grade; it does not gate use.

| Path | Trigger | Resulting S status |
| --- | --- | --- |
| Automatic | evidence score E ≥ T (default 5; `evidence_threshold` in config.md) | `provisional` |
| Manual | `/ani ok <F-id>`, or equivalent explicit approval in natural language | `active` |

Write the S file from `templates/S-template.md`, set
`compiled_from: [<F-id>]`, then set the F's `status: compiled`. Never delete the
F — it is the provenance and the anchor for counterexamples.

### Evidence score E

| Signal (observed in this session) | Score |
| --- | --- |
| Explicit positive acknowledgement ("좋아", "됐다", "that's it") | +2 |
| Objective verification passed (the draft verification actually executed and passed) | +2 |
| No re-correction on the same topic until session end | +1 |
| Same pattern class observed ≥2 times (keyword overlap, per session) | +2 |
| Structural lint: every required S field is concrete | precondition gate, not points |
| Re-correction on the same topic | disqualifies this round |

The structural lint is a gate, not a score: if any required field would come out
vague ("check that it works"), do not compile no matter how high E is.

### Cushion rule — mixed praise and correction

The scoring unit is the **per-topic round**, not the utterance. Decompose the
utterance semantically:

- Correction targets the **same** topic ("좋은데 아직 글자색이 바뀌었잖아,
  배경색이라고"): re-correction → the round is disqualified, and the praise is a
  politeness softener worth **0**. Behavior beats sentiment.
- Correction targets a **different** aspect ("배경색 좋네. 근데 폰트도 바꿔줘"):
  the original topic keeps its +2, and the new request opens its own round —
  RESTATE decides whether it is even a correction.
- Ambiguous? **Rule for the correction side.** A wrong compile (a polluted
  store) costs more than a delayed one.

### provisional discipline

- Disclosed as provisional, with its ID, on every single application.
- Ranks below `active` in matching.
- One counterexample → `retired` immediately, no review.
- Survives 2 applications in **different sessions** with no re-correction →
  promotion candidate: surface it and let the user promote with
  `/ani ok <S-id>` in one click. `auto_promote: true` in config.md permits
  unattended promotion (default `false`; in team repos, PR review is the
  natural gate).
- **Promotion raises the trust rung, never the scope.** `/ani ok` changes
  `status` only; `scope` stays as written. `project` → `global` is a separate,
  deliberate, per-pattern decision the user states explicitly — never a side
  effect of approval, and never inferred from a bulk approval.

### States

```
F: captured ──compile (auto E≥T | manual /ani ok)──▶ compiled
        └──manual cleanup──▶ archived

S: (born) ──auto-compile, E≥T──▶ provisional
   (born) ──human approval at write time──▶ active

   provisional ──2 survivals + approval──▶ active
        └──1 counterexample──▶ retired (immediate, no review)

   active ──counterexample F──▶ review-needed ──re-approval──▶ active
                                       └──discard──▶ retired
```

`active` has two entrances: promotion from `provisional`, and birth — an S the
user approved as it was written (`/ani ok <F-id>`, or a bulk-approved bootstrap
cluster) is written `active` once and never walks the provisional rung. Both
entrances leave `scope` untouched.

Every status change edits the pattern frontmatter **and** the INDEX row.

## Verification discipline — four layers

A pattern without checks is advice, and agents ignore advice.

1. **Externalize.** Every `## Verification` item carries
   `method / target / expected / evidence / on_failure`. That converts "looks
   right" into "ran X against Y, observed Z, left this artifact".
2. **Evidence = fresh tool-execution artifacts from THIS turn only.** Command
   output, a file path with a timestamp, a test result rendered by the harness.
   A textual claim ("I confirmed it") is not evidence. Output reused from an
   earlier turn is not evidence.
3. **The correction detector is the outermost loop.** If verification is fooled,
   the failure returns as the user's next correction, which ani catches and
   records as a counterexample F → demotion. The loop does not need to be
   perfect; it needs to be **inescapable**.
4. **Verification items are born from the failure.** At compile time always ask:
   *"what check would have caught this misreading?"* The answer becomes the
   verification item — a regression test for this specific accident, not a
   generic checklist.

Skipping an item (`n/a`) requires a stated reason and the user's approval. Never
declare done before the checks pass.

## Boundary with host memory

ani is the **single owner of procedural correction knowledge** (situation →
action → verification). Host memory (CLAUDE.md, AGENTS.md, auto-memory) keeps
declarative facts only and points at patterns by ID: `ani:S-dark-mode-tokens`.
Never copy a pattern body into host memory — copies drift, and demotion cannot
reach them.

## Subcommands

| Command | Action |
| --- | --- |
| `/ani` | Run the correction loop on the current exchange (also used to capture a correction after the fact) |
| `/ani ok <F-id>` | Compile that F into an `active` S |
| `/ani ok <S-id>` | Promote a `provisional` S to `active` |
| `/ani bootstrap [--days N]` | Mine past sessions for corrections, cluster them, and present a digest for bulk approval — see `references/adapters/bootstrap.md` |

## Red flags — stop and correct course

- Wrote the F file before doing the fix → wrong order; the fix comes first.
- Applied a pattern without citing its ID, or applied a provisional one without
  disclosing it.
- Took today's date from memory instead of the `date` command.
- Wrote a verification item like "check that it looks right" → not a check; do
  not compile.
- Rewound, cleared, or restarted the session yourself → TRIAGE only recommends.
- Edited INDEX without editing the pattern frontmatter, or the reverse.
- Copied a pattern body into CLAUDE.md / AGENTS.md.
- Treated a missing hook marker as proof that no correction occurred.

## References

- `references/schemas.md` — canonical F/S/INDEX/config field spec, with a full
  worked example.
- `references/triggers.md` — multilingual correction phrase hints and how to
  extend them per project.
- `templates/F-template.md`, `templates/S-template.md` — ready-to-copy files.
- `references/adapters/` — platform specifics (hooks, transcript mining,
  rewind/clear commands). Optional; the core is complete without them.
