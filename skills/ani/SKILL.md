---
name: ani
description: Use when the user signals you misread their intent — "아니 그게 아니라", "그게 아니라", "그거 말고", "내 말은", "no, that's not what I meant", "not what I asked", "you misunderstood", "いや、そうじゃなくて", "不是这个意思" — or any rephrasing, in any language, that means "no, that's not it". Also use proactively before any non-trivial task when an ani store exists — the user's global ~/.ani or a project .ani/ overlay — so recorded correction patterns are consulted before acting, and when the user types /ani, /ani ok <id>, /ani resolve <F-id>, /ani bootstrap, or /ani git.
---

# ani — the "no, that's not it" protocol

## Overview

A user correction is a bug report delivered at the crime scene with the right
answer attached. ani never throws it away: it records each correction as a
failure pattern (**F**) file, compiles proven ones into success patterns (**S**)
carrying executable verification, and consults them before the same mistake
repeats. Two entry paths: **Path A (proactive)** runs before non-trivial work and
is the one that prevents corrections; **Path B (the correction loop)** runs the
moment a correction lands.

## Stores — two tiers, files are the protocol

| Tier | Path | Role |
| --- | --- | --- |
| **global** (default) | `~/.ani/`, or the `global_store` path set in config.md (e.g. `~/.claude/ani`) | Always available. Personal correction knowledge that follows the user from repo to repo. |
| **project** (overlay) | `<repo>/.ani/` — **opt-in**: it exists only if someone created it | Repo-local patterns, shared with the team through git, promoted under PR review. |

Both tiers have the identical layout:

```
<store>/
├── INDEX.md                       # cache: one row per pattern (budget 60 rows / 6KB)
├── patterns/
│   ├── F-20260828-a1b2c3d4.md     # F-<YYYYMMDD>-<rand8>
│   └── S-dark-mode-tokens.md      # S-<slug>
└── config.md                      # optional overrides
```

**Capture routing.** A correction about *this repo's* files or conventions goes to
the project store **when the overlay exists**; a correction about the user's general
working style goes to the global store. **Ambiguous → global** — personal knowledge
leaking into a team repo is the more expensive mistake, and most "왜 자꾸" is about
this user rather than this repo, which is why global is the default sink.

**Search reads both**, project rows first (priority table below). Pattern
frontmatter is the **source of truth**; INDEX.md is a regenerable cache — on
mismatch the frontmatter wins, so regenerate the affected row on the spot.

No store yet? Create the global one on the first capture (Step 4); create a project
overlay only when the user asks for it. Never write outside a store. Fields:
`references/schemas.md`. Phrase hints: `references/triggers.md`.

## Path A — consult before you act

1. Read `INDEX.md` from every store that exists — the global one always, the
   project overlay when the repo has `.ani/` — once at session start, and again
   before any non-trivial task (multi-file edit, new feature, refactor — anything
   you would plan before doing).
2. Match the request against INDEX `summary` fields. They are written in
   **use-when** form and are matched the way you pick a skill: semantically, not
   by keyword equality.
3. Open only the candidate pattern files. Never read the whole store.
4. Apply in this priority order — higher always wins:

| Rank | Source |
| --- | --- |
| 1 | The current user request |
| 2 | Safety and permission constraints |
| 3 | Project store S patterns (repo-local) |
| 4 | Global store S patterns (personal) |
| 5 | Knowledge claims (`K-` ids), only when a knowledge source is configured |

Store rank dominates; inside a store, `active` outranks `provisional`. One id in
both stores is one pattern: the project copy wins and the global one is ignored.
An S id is a slug, so two people who learn the same lesson land on the same id —
the override is common, not exotic. The session-start injection therefore **names**
the ids it shadowed; step 6b covers what to say when you apply one.

5. Skip any S whose status is `review-needed` or `retired` — they are excluded
   from search so a wrong manual cannot be re-applied.
6. A `provisional` S **must be disclosed on every application**, with its ID:
   "Applying provisional pattern `S-dark-mode-tokens` (auto-compiled, not yet
   human-approved) — tell me if it is wrong." The user can veto at any time.
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
7. Whenever a pattern shaped your action, cite its ID in your reply.

**Knowledge sources (optional).** With `knowledge_sources` set in config.md, a
hint may also carry `K-` ids. Resolve one by reading that file's matching row: it
is a one-line claim pointing into the user's own wiki ("… see note 0010"). Open
the note rather than re-derive it, cite the id, never rank a claim above a
pattern. Contract: `references/adapters/knowledge-source.md`.

### Hook markers (optional Tier 1 adapters)

An adapter may prepend a marker to the prompt. The core works without them.

| Marker | Meaning | How to consume |
| --- | --- | --- |
| `[ani-nudge v1] session=<id> prompt_sha=<8hex> pattern=<slug>` | deterministic correction detection | Consume **only** if `session` matches the current session and `prompt_sha` matches this turn's prompt. Otherwise ignore silently — it is a stale marker from another turn. |
| `[ani-hint v1] patterns=<S-id,…[,K-id,…]>` | keyword overlap between the prompt and the INDEXes, plus any configured knowledge source | Treat as search hints. Still verify semantic fit; drop the ones that do not fit. `K-` ids always come last. |
| `[ani-index v1]` + rows | session-start injection of both stores' INDEX rows | Use as resident candidates. Its **absence** is the handshake failure below. |

**Handshake — the missing heartbeat.** `[ani-index v1]` is the hooks' proof of
life. If a session never shows one, treat the hooks as not firing: switch to
**manual mode** — read each store's `INDEX.md` yourself (Path A step 1) and run
every step of the protocol unchanged. If a store does turn out to exist, say so
**once**, plainly ("ani hooks look inactive — running manual mode; try
`/ani doctor`"), and never mention it again that session. **Hooks are
accelerators; the protocol is the guarantee.**

Never echo markers back to the user. Absence of a marker never means "no
correction happened" — **you are the detector**, the markers are reinforcement.

## Path B — the correction loop

Runs whenever the user's turn *means* "you misread me", in any wording or
language. The phrase lists in `references/triggers.md` are hints; semantic
recognition is the detector.

### Step 1 — RESTATE (before anything else)

Restate the user's actual intent in one line, before fixing, searching, or
apologizing.

- Ask **at most one** question, and only if the intent is genuinely ambiguous.
- If the restatement reveals this was not a correction (a quotation, a joke, a
  new request), end the loop silently — no F file, no ceremony.

### Step 2 — SEARCH

- Read both INDEXes (if not already in context) and open candidate S files:
  project before global, `active` before `provisional` (allowed, but disclosed),
  `review-needed`/`retired` excluded.
- **If a pattern you applied this session is what just got corrected**, that is a
  counterexample: write the F file (Step 4) with the S id in `keywords` and in
  `Misreading`, add it to that S's `## Counter-examples`, and demote immediately —
  `active` → `review-needed` (excluded from search until re-approved),
  `provisional` → `retired` (no review; nobody ever approved it). A demotion edits
  the S frontmatter **and** its INDEX row.

### Step 3 — FIX

Do the actual correction now. **Recording never blocks the fix.** If you can only
do one thing, fix.

### Step 4 — CAPTURE

- **First capture only — when the store does not exist yet, check once before
  creating it.** This is the first moment python, the install root and write
  access are actually required rather than assumed, so it is the honest place
  to look. Run the doctor at the **install root** by **absolute path**
  (References). No `scripts/` present (skill-directory install) → skip this
  entirely; the protocol does not depend on it. Act on what it reports by
  **where the fault lives** — the same boundary that governs every write:
  - **Inside the store** (absent directory, unwritable path, unparsable
    `INDEX.md`) — fix it yourself, then say so in one line.
  - **Outside the store** (no python, plugin or hooks not installed) — fix
    **nothing**. Give the user the one command to run and why it matters.
    Never change the user's environment on their behalf.
  - **Whether hooks fire** is not the doctor's to report and not yours to
    infer: only `[ani-index v1]` in a fresh session shows that. Say the check
    could not cover it rather than implying it passed.

  **This check never blocks the capture.** A correction that arrived is
  captured even if every check fails — in manual mode if it must be. The
  report goes *beside* the capture, never in front of it, and it happens once:
  the store exists after this, so later captures skip it.
- Get today's date from the `date` command (or the platform equivalent). **Never
  from memory or from context.**
- Pick the store by the routing rule above, then create
  `<store>/patterns/F-<YYYYMMDD>-<rand8>.md` from `templates/F-template.md` at
  the install root (see References; no templates present → build the file from
  `references/schemas.md`) — the random 8-char suffix is what makes concurrent
  sessions collision-free.
- Capturing inside a repo? Fill `project` by the slug rule: `owner/repo` from the
  `origin` remote when there is one, else the repo root's directory name; omit
  rather than guess. This is the field `/ani git` later reads as provenance, and
  it never repairs retroactively — whatever is written now is what that F carries.
- Does this correction match an already-captured F class (INDEX keywords)?
  Increment that F's `recurrence` instead of opening a duplicate class.
- `## Excerpt` is REQUIRED and must be a **self-contained verbatim** exchange:
  someone reading the F file alone, with no transcript access, must be able to
  reconstruct the failure.
- Add or refresh that store's INDEX row, keeping captured rows sorted by
  `recurrence` descending. Over budget (60 rows / 6KB)? Drop `archived` F rows
  and `retired` S rows first, then merge near-duplicate S patterns.
- If the store is inside a git repo and the user's conventions allow commits,
  commit the store change on its own — never bundled with code changes.

### Step 5 — TRIAGE (context health)

Repeated corrections usually mean the context is polluted. The F file lives
outside the window, so the context is now **disposable** — and several fresh
attempts can branch from the same F.

| Signal | Recommendation |
| --- | --- |
| First correction, simple misread | Continue in this session (default) |
| Second correction on the same topic, loop signs ("왜 자꾸", repeated failed attempts, your own self-contradiction) | Recommend rewinding to before the pollution point |
| Repeated failure, long session, heavy pollution | Recommend a fresh session that reads **only** `<store>/patterns/F-<id>.md` as its checkpoint |

These are **recommendations only** — the user decides. Never rewind, clear, or
restart on your own. Platform commands live in the adapters: name the action, not
the keystroke, unless an adapter document is loaded.

## Compiling F → S

Two paths. Human approval raises the trust grade; it does not gate use.

| Path | Trigger | Resulting S status |
| --- | --- | --- |
| Automatic | evidence score E ≥ T (default 5; `evidence_threshold` in config.md) | `provisional` |
| Manual | `/ani ok <F-id>`, or equivalent explicit approval in natural language | `active` |

Write the S file from `templates/S-template.md` (install root, as in CAPTURE)
into the F's own store, set
`compiled_from: [<F-id>]`, then set the F's `status: compiled`. Never delete the
F — it is the provenance and the anchor for counterexamples.

### Compilation is parasitic — never a dedicated run

The "this actually works" evidence comes from the success run **Step 3 FIX
already performed** on the user's real request. Those tokens were spent anyway;
`+2 objective verification passed` is exactly that evidence, and compilation
rides it for free. **Never re-run a past failure offline to manufacture a
success**: reproduction costs real tokens, the repo has drifted since, and the
user gets nothing back for it.

### The unresolved queue — the INDEX *is* the queue

Some F files never reach a success in-session: the user gave up, the context was
reset, or `bootstrap` dug the failure out of an old transcript.

- F frontmatter carries an advisory `recurrence: N`, incremented at capture time
  when a new correction matches an existing captured F class by INDEX keywords.
- Captured INDEX rows are sorted by `recurrence` descending. That ordering **is**
  the queue — no backlog file, no scheduler, no extra tokens.
- An F sitting at `recurrence: 0` forever is a **correct outcome**, not a
  failure: a class that never recurred has negative compile ROI, so `captured` is
  where it belongs. Priority = expected saving — one avoided correction loop is
  worth thousands of tokens.
- **Resolution piggybacks too.** Attempt the top of the queue during the next
  *related* live work. A dedicated offline resolve run happens only when the user
  types `/ani resolve <F-id>` — spending tokens on it is their call, not yours.

### Evidence score E

| Signal (observed in this session) | Score |
| --- | --- |
| Explicit positive acknowledgement ("좋아", "됐다", "that's it") | +2 |
| Objective verification passed (the draft verification actually executed and passed) | +2 |
| No re-correction on the same topic until session end | +1 |
| Same pattern class observed ≥2 times, cumulative across sessions (keyword overlap) | +2 |
| Structural lint: every required S field is concrete | precondition gate, not points |
| Re-correction on the same topic | disqualifies this round |

The structural lint is a gate, not a score: if any required field would come out
vague ("check that it works"), do not compile no matter how high E is.

### Cushion rule — mixed praise and correction

The scoring unit is the **per-topic round**, not the utterance — decompose it
semantically:

- **Same** topic ("좋은데 아직 글자색이 바뀌었잖아, 배경색이라고"): re-correction,
  round disqualified, and the praise is a politeness softener worth **0**.
  Behavior beats sentiment.
- **Different** aspect ("배경색 좋네. 근데 폰트도 바꿔줘"): the original topic keeps
  its +2 and the new request opens its own round — RESTATE decides whether it is
  even a correction.
- Ambiguous? **Rule for the correction side.** A polluted store costs more than a
  delayed compile.

### provisional discipline

- Disclosed as provisional, with its ID, on every single application.
- Ranks below `active` in matching.
- One counterexample → `retired` immediately, no review.
- Survives 2 applications in **different sessions** with no re-correction →
  promotion candidate: surface it for one-click `/ani ok <S-id>`.
  `auto_promote: true` in config.md permits unattended promotion (default
  `false`; in team repos PR review is the natural gate).
- **Promotion raises the trust rung, never the reach.** `/ani ok` changes
  `status` only. Moving a pattern between the stores (and with it `scope`, which
  mirrors the store) is a separate, deliberate decision the user states
  explicitly — never a side effect of approval or of a bulk approval.

### States

```
F: captured ──compile (auto E≥T | /ani ok)──▶ compiled · ──cleanup──▶ archived
S: born ──E≥T──▶ provisional          born ──human approval──▶ active
   provisional ──2 survivals + approval──▶ active · ──1 counterexample──▶ retired
   active ──counterexample F──▶ review-needed ──re-approval──▶ active | ──▶ retired
```

`active` has two entrances: promotion from `provisional`, and birth — an S the
user approved as written (`/ani ok <F-id>`, or a bulk-approved bootstrap cluster)
is `active` at once and never walks the provisional rung. Neither entrance
touches `scope` or moves a pattern between stores. Every status change edits the
pattern frontmatter **and** its INDEX row.

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
declarative facts only and points at patterns by ID (`ani:S-dark-mode-tokens`).
Never copy a pattern body there — copies drift, and demotion cannot reach them.

## Subcommands

Written here as `/ani`, the protocol's short form. A plugin install namespaces
the skill, so the typed command is `/ani:ani …`; a skill-directory install keeps
plain `/ani`.

| Command | Action |
| --- | --- |
| `/ani` | Run the correction loop on the current exchange (also used to capture a correction after the fact) |
| `/ani ok <F-id>` | Compile that F into an `active` S |
| `/ani ok <S-id>` | Promote a `provisional` S to `active` |
| `/ani resolve <F-id>` | Spend a dedicated run on one unresolved F: reproduce, resolve, verify, compile. The **only** licence to work a failure outside live work |
| `/ani bootstrap [--days N]` | Mine past sessions for corrections, cluster them, and present a digest for bulk approval — see `references/adapters/bootstrap.md` |
| `/ani git` | List global patterns worth sharing with this repo's team, and copy the ones the user selects into the project overlay — see `references/adapters/publish.md` |
| `/ani doctor` | Run `scripts/ani_doctor.py` at the **install root** by **absolute path** (Bash; resolve the root first — References, "Resolving the install root"): python, store resolution and write probe, INDEX parse counts, knowledge sources, plugin install. Prints `OK`/`WARN`/`FAIL` per check; exit `0` clean, `1` warnings, `2` failures. It cannot see whether hooks fire — only `[ani-index v1]` in a fresh session shows that |

## Red flags — stop and correct course

- Wrote the F file before doing the fix → wrong order; the fix comes first.
- Applied a pattern without citing its ID, or applied a provisional one without
  disclosing it.
- Took today's date from memory instead of the `date` command.
- Wrote a verification item like "check that it looks right" → not a check; do
  not compile.
- Rewound, cleared, or restarted the session yourself → TRIAGE only recommends.
- Re-ran a past failure offline to manufacture compile evidence → only
  `/ani resolve` licenses that.
- Wrote a correction about the user's general working style into a team repo's
  project store → ambiguous routing goes global.
- Edited INDEX without editing the pattern frontmatter, or the reverse.
- Copied a pattern body into CLAUDE.md / AGENTS.md.
- Treated a missing hook marker as proof that no correction occurred.

## References

Everything under `references/` sits beside this SKILL.md. `scripts/` and
`templates/` do **not**: they live at the **install root**, two directories
above this file — the plugin root in a plugin install (the cached plugin
directory), the repo root in a checkout.

**Resolving the install root** — resolve it, never guess it, and never run a
bare relative `python scripts/ani_doctor.py` from the working directory (that
is the known `[Errno 2] No such file` failure). The harness prints
`Base directory for this skill: <path>` when this skill loads; strip the
trailing `skills/ani` and what remains is the install root. In a plugin
install it looks like `~/.claude/plugins/cache/<marketplace>/ani/<version>/`
— the same directory the hooks receive as `${CLAUDE_PLUGIN_ROOT}` — so the
doctor is always the absolute
`python <install root>/scripts/ani_doctor.py`.

A skill-directory-only install carries neither `scripts/` nor `templates/`:
build F/S files from `references/schemas.md` and skip `/ani doctor` — the
protocol is complete without them.

- `references/schemas.md` — canonical F/S/INDEX/config field spec + worked example.
- `references/triggers.md` — multilingual phrase hints, extendable per project.
- `templates/F-template.md`, `templates/S-template.md` (install root) — ready-to-copy files.
- `references/adapters/` — platform specifics (hooks, transcript mining,
  rewind/clear commands) and `knowledge-source.md`, the wiki bridge. Optional;
  the core is complete without them.
