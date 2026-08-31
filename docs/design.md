# ani — design

English · **[한국어](design.ko.md)**

This is the reasoning behind the protocol. [README.md](../README.md) shows what ani does and
what it writes; this document explains why each rule is the way it is, for a reader who has
never seen the project before.

The normative field spec — exact frontmatter keys, section headings, allowed values — lives in
[`skills/ani/references/schemas.md`](../skills/ani/references/schemas.md). Where this document
and the schema disagree about a field, the schema wins.

## Contents

- [The eight pillars](#the-eight-pillars)
- [The trust ladder and the state machines](#the-trust-ladder-and-the-state-machines)
- [The evidence score E](#the-evidence-score-e)
- [The cushion rule](#the-cushion-rule)
- [Closing the verification loop](#closing-the-verification-loop)
- [The store: four conventions instead of a database](#the-store-four-conventions-instead-of-a-database)
- [Token economy](#token-economy)
- [Boundary with host memory](#boundary-with-host-memory)

---

## The eight pillars

### P1 — Corrections are bug reports, not noise

An annoyed "no, that's not it" contains the misread intent, the real intent, and the repair in
one packet. Letting it evaporate with the session is the root cause of repeated corrections.
ani's first job is simply not to throw it away.

### P2 — Compile, don't just remember. The human is an auditor, not a gatekeeper

A pile of failure logs is search noise; like a wiki promoting a draft to an article, `F` must be
compiled before it becomes `S`. But per-item approval that *blocks usage* becomes the bottleneck
that quietly kills the system — the inbox-zero failure mode, where a queue of pending approvals
grows until nobody looks at it and the whole mechanism dies without anyone deciding to kill it.

So evidence auto-compiles to *provisional*, usable right away, and approval raises trust rather
than unlocking use. No automatic step ever beats a user veto, and anything auto-promoted is
retired by a single counterexample.

### P3 — Verification is first-class

Every `S` must carry executable verification conditions: what to run or observe, what counts as
passing, what evidence gets left behind. **"Done" cannot be declared before the verification
passes.** A pattern without a check is advice, and agents ignore advice.

### P4 — Files are the protocol

No server, no API, no vendor. The entire system is markdown + YAML frontmatter + naming
conventions in a directory. Anything that reads and writes files — Claude Code, Codex, Cursor, a
human with an editor — can participate. Where there is git, revision history, blame, review, and
team sharing come free.

### P5 — The model is the matcher

Neither correction detection nor pattern lookup is regex at its core. **Semantic recognition of
a correction is the agent's job; phrase lists and hooks are hints and reinforcement.** This is
what makes ani language-independent — Korean, English, Japanese: it fires on meaning, not on a
string.

### P6 — Progressive enhancement

*Tier 0* is pure markdown: zero scripts, zero hooks, works in any agent that reads a skill or
instruction file. *Tier 1* adds optional platform adapters (deterministic hooks, slash commands)
where the platform allows. The core is complete without them — the moment an adapter becomes a
prerequisite, portability is dead.

### P7 — Knowledge lives in two tiers

**Personal knowledge follows the user; team knowledge travels with the repo.**

The default store is **global**: `~/.ani/`, always present, overridable through the
`global_store` key (a Claude Code user may point it at `~/.claude/ani`). It is the default sink
for capture because most of what makes a user say "왜 자꾸" is not a property of one repo but of
how *this person* works. A project-only default fragments the same recurring correction across
every repo they touch — the same lesson re-learned n times, never accumulating anywhere.

The **project overlay**, `.ani/` at the repo root, is opt-in and unchanged in spirit: create it
and repo-specific patterns live there, so cloning the repo teaches your teammates' agents too and
adding or promoting a pattern becomes a PR review — **learning becomes an object of code review.**

Routing follows the same asymmetry as everything else here: repo-specific facts go to the
overlay when it exists, general working style goes global, and **ambiguity resolves to global**,
because personal knowledge leaking into a team repo is more expensive than a personal pattern
that could have been shared. Search and injection read both, project first; concurrency is
handled by the same two conventions in both tiers (`rand8` filenames, INDEX as a regenerable
cache), so a global store written by several sessions at once still needs no lock.

The default is `~/.ani` rather than `~/.claude/ani` because of P4: a Codex or Cursor user should
not have to keep their corrections inside another vendor's directory.

### P8 — Capture makes context disposable

Sessions with repeated corrections usually have polluted context, yet most users keep patching
on top of it out of sunk cost — "I don't want to lose everything so far." Often the real fix is
to throw the context away. ani breaks the dilemma: the essence of the failure is already saved
in an F file, so the context is now a consumable. After capture, ani evaluates context health
and recommends rewinding or restarting — and a single F file can seed several independent fresh
attempts.

---

## The trust ladder and the state machines

Two objects, two machines. `F` records what happened; `S` records what to do about it.

### F — failure pattern

```
F: captured ──compile (auto E ≥ T | manual /ani ok)──▶ compiled
        └──manual cleanup──▶ archived
```

`captured` is where every F starts. `compiled` means an `S` now exists and names this F in its
`compiled_from`. `archived` is for tidying: an F that will never be compiled, kept as history.
An F is never deleted — it is the provenance of its `S` and the anchor for counterexamples.

### S — success pattern

```
S: (born) ──auto-compile, E ≥ T──▶ provisional
   (born) ──human approval at write time──▶ active

   provisional ──2 survivals + approval──▶ active
        └──1 counterexample──▶ retired (immediate, no review)

   active ──counterexample F──▶ review-needed ──re-approval──▶ active
                                       └──discard──▶ retired
```

**`active` has two entrances.** One is promotion from `provisional`. The other is birth: an S
the user approved as it was written (`/ani ok <F-id>`, or a bulk-approved bootstrap cluster) is
written `active` once and never walks the provisional rung. Both entrances leave the pattern
where it lives — approval changes `status`, never the store or the `scope` that mirrors it.
Moving a pattern from the project overlay to the global store, or the other way, is a separate,
deliberate, per-pattern decision the user states explicitly; it is never a side effect of
approval and never inferred from a bulk approval.

### The rungs

| Rung | Entered by | How it is used | Left by |
| --- | --- | --- | --- |
| **provisional** | automatically, when evidence score `E ≥ T` | usable immediately; ranked below active; **must be disclosed** as provisional and cited by ID on every application | one counterexample → retired, immediately, no deliberation (no human ever vouched for it) |
| **active** | explicit human approval, or promotion of a provisional that survived 2 separate sessions | applied first, cited by ID | a counterexample → review-needed |
| **review-needed** | a counterexample F was recorded against an active pattern | **excluded from search** — a wrong manual must not be re-applied | re-approval → active, or discard → retired |
| **retired** | demotion or discard | never applied | terminal; stays as history |

Every state has an exit. There are no dead states, and no state where a pattern is both
unusable and un-fixable.

### provisional discipline

- Disclosed as provisional, with its ID, on **every single application**. The user can veto at
  any time, which is the whole reason automatic compilation is safe.
- Ranks below `active` in matching.
- One counterexample retires it immediately, with no review — nobody ever approved it, so there
  is nothing to deliberate about.
- Surviving 2 applications in **different sessions** with no re-correction makes it a promotion
  candidate, surfaced for one-click approval. `auto_promote: true` in `config.md` permits
  unattended promotion (default `false`; in team repos, PR review is the natural gate).

---

## The evidence score E

Automatic compilation needs a number, and the number must come from signals a third party could
check. Only the signals below are counted. The threshold `T` defaults to 5 and is set by
`evidence_threshold` in the store's `config.md`.

| Signal, observed in-session | Score | Kind |
| --- | --- | --- |
| Explicit positive acknowledgement ("that's it", "좋아", "됐다") | +2 | sentiment — politeness can be a false positive, never sufficient alone |
| Objective verification passed (the draft check was actually run) | +2 | behavioral |
| No re-correction on the same topic through end of session | +1 | behavioral — silence is weak evidence |
| Recurrence: the same class of pattern seen again (keyword overlap, ≥2 times) | +2 | repetition |
| Structural lint: every required field of the S draft is concrete | prerequisite | an eligibility gate, not points |
| A re-correction on the same topic | instant disqualification | this round is void |

The structural lint is a **gate, not a score**: if any required field would come out vague
("check that it works"), do not compile no matter how high E is.

These signals are approximations, and ani says so. Silence is not satisfaction; "thanks" may be
manners. That is exactly why behavioral signals outweigh sentiment ones, and why **automation is
capped at the provisional rung**. Free-form vibes — "the user seemed happy" — score nothing,
because a score that can be produced by introspection is not evidence.

---

## The cushion rule

Real utterances mix praise and correction: *"좋은데, 여기는 이렇게 바꿔"*, *"nice, but change
X"*. The scoring unit is therefore the **per-topic round**, not the utterance. The model
decomposes the utterance semantically (P5) and scores each topic separately.

- **Correction targets the same topic** — *"좋은데 아직 글자색이 바뀌었잖아, 배경색이라고"*:
  this is a re-correction, so the round is disqualified, and the "좋은데" is a politeness
  softener worth **0**. Behavior beats sentiment.
- **Correction targets a different aspect** — *"배경색 좋네. 근데 폰트도 바꿔줘"*: the original
  topic keeps its +2, and the new demand opens its own round. RESTATE decides whether that new
  demand is even a correction, or simply a new request.
- **Ambiguous** — rule it a correction.

The asymmetry is deliberate. A wrong compile pollutes the store: a bad pattern gets applied,
costs a real failure, and has to be caught and demoted. A delayed compile costs one more round
of the same correction. **A wrong compile is more expensive than a late one**, so every
ambiguous case resolves toward not compiling.

---

## Closing the verification loop

The obvious objection to any self-learning system is *who verifies the verifier* — a wrong
pattern that verifies itself would silently propagate. ani's answer has four layers, and the
fourth is the one that actually closes the loop.

**1. Verification is externalized.** It is not the model's self-assessment. Every check names
`method / target / expected / evidence / on_failure`, which forcibly converts "looks right to
me" into "I ran X against Y, observed Z, and left this artifact behind". `expected` in
particular must be stated so a third party could judge it: "0 matches outside `tokens.css`", not
"looks right".

**2. Evidence must be fresh tool output.** Only outputs, file paths, and timestamps from tool
calls actually made *this turn* count. Saying "I checked" in prose is not evidence, and output
reused from an earlier turn is not evidence. Tool output is rendered by the harness, so it is an
anchor the model cannot forge. Skipping an item (`n/a`) requires a stated reason **and** the
user's approval.

**3. The correction detector itself is the outermost regression loop.** If verification is
bypassed and a wrong result ships, that failure surfaces as the user's next correction — and
detecting corrections is precisely what ani does. The result is a counterexample F and a
demotion. **The verification loop does not need to be perfect; it only needs to be inescapable.**
A failure cannot structurally slip past the detector, which is why a wrong pattern cannot fail
silently. This is what licenses automatic compilation at all.

**4. Checks are born from failures.** Compilation always asks: *"which check would have caught
this misreading?"* The answer becomes the verification condition. These are not generic
checklists but regression tests derived from a real incident — the TDD principle of one test per
bug, applied to intent.

---

## The store: four conventions instead of a database

An early draft of ani had a serialization daemon to arbitrate concurrent writes. It is gone, and
four file conventions do its work:

- **Frontmatter is the source of truth; `INDEX.md` is a regenerable cache.** If a row disagrees
  with its pattern file, the pattern file wins and the row is rewritten on the spot — never the
  reverse. Concurrent sessions therefore self-heal without any locking, and a corrupted INDEX is
  repaired by rescanning `patterns/*.md`.
- **Filenames avoid collisions structurally.** The `rand8` suffix on `F-<YYYYMMDD>-<rand8>.md`
  means two sessions writing at the same moment cannot land on the same path.
- **git history is the wiki revision history.** Blame, diff, and revert come free; teams share
  by cloning, and adding or promoting a pattern in the project overlay is reviewed as a PR.
  Without git everything still works — you just lose the history, an explicit trade-off.
- **The INDEX has a budget** — 60 rows / 6KB per store by default. This is a hard ceiling, not a
  suggestion: it is what makes the whole catalog affordable to keep in context for an entire
  session, which in turn is what makes proactive matching free. Over budget, drop `archived` F
  rows and `retired` S rows first, then `compiled` F rows whose S is active, then merge
  near-duplicate S patterns.

The same four conventions serve both tiers, which is why a second store costs one path
resolution and no new machinery.

Matching priority, when several sources disagree: **the current user request > safety and
permission constraints > project store patterns > global store patterns > knowledge claims**
(the last rung only when the optional bridge below is configured). Store rank dominates;
inside a store, `active` outranks `provisional`; an id present in both stores is one pattern and
the project copy wins. "Apply as written" refers to the procedure and the verification, never to
the parameters of the original incident — those are re-interpreted for the request at hand.

### Knowledge sources: the same architecture, one layer out

An optional bridge lets the hint engine also match rows from an external knowledge index — claims
compiled out of a wiki the user already keeps. It is worth saying why that is not a new subsystem.

The correction store and a wiki export are **two instances of one architecture**: a compiled index
of one-line summaries, deterministic matching against it, a budgeted hint naming ids, and the body
pulled only once an id has earned it. `INDEX.md` is that shape over the pattern files; a knowledge
file is that shape over someone's notes. Nothing had to be invented to add the second one — same
six columns, same id validation, same hint line.

It is also P2 held consistently. *Compile, don't just remember* says a raw log is search noise
until it is compiled; a wiki is precisely a pile that someone **already** compiled. The waste
being attacked is an agent re-deriving, badly, a conclusion its user wrote down months ago. So a
claim points — "see note 0010" — and never carries the body. Compile once, reference many times.

Two asymmetries keep the bridge honest. A claim ranks **below** every verified pattern, because a
pattern carries verification conditions and a counterexample history while a claim carries an
assertion. And claims are matched only at prompt time, never injected at session start: the
standing 6KB belongs to the store that earned it by being small and verified, and an unmatched
prompt should cost nothing. Users without a wiki configure nothing and see nothing change — their
correction store *is* their knowledge store, which was the point from the beginning.

---

## Token economy

A learning protocol that costs more tokens than the mistakes it prevents is a net loss, so the
budget is part of the design rather than an afterthought.

### Three tiers of cost

| Tier | When it is paid | Size |
| --- | --- | --- |
| The skill **description** (plus, with the adapter, the session-start injection) | always resident | a few lines + one combined 6KB |
| **SKILL.md** | only when a correction fires or a store is consulted | ~300 lines, once |
| **references/** (schemas, triggers, adapters) | on demand, when writing or debugging a pattern | read a file at a time |

The always-on tier is the one that must stay small, which is why the dual store shares a
**single** 6KB session-start injection instead of one per store: two tiers of knowledge, one
standing bill. The INDEX budget exists for the same reason — a catalog that no longer fits in
context stops being free to consult, and proactive matching is the mechanism that prevents
corrections rather than merely recording them.

### Parasitic compilation

Compiling `F` into `S` needs evidence that something actually worked. That evidence is **not**
manufactured by a dedicated run: in the normal flow, Step 3 FIX has already carried out the
user's real request and passed the draft check, and those tokens were spent on work the user
wanted anyway. `+2 objective verification passed` *is* that evidence, and compilation rides it.

Re-running a past failure offline to prove a fix is the alternative, and it is a bad trade:
reproduction costs real tokens, the repo has drifted since the incident, and the user receives
nothing in return. So it is not the default path — it happens only when the user explicitly
asks for it with `/ani resolve <F-id>`, because spending tokens that way is their decision.

### The unresolved queue, and why `recurrence: 0` is a success

Some failures never reach a success inside the session: the user gave up, the context was reset,
or `bootstrap` unearthed the failure from an old transcript. Nobody drives those to a verified
fix, so they need an ordering rather than a pile.

An advisory `recurrence: N` on the F frontmatter counts how often the same class came back, the
model incrementing it at capture time by comparing against INDEX keywords — no new
infrastructure, no extra model call. Captured INDEX rows are then sorted by `recurrence`
descending, and **that ordering is the queue**: one file convention absorbs what would otherwise
be a backlog file and a scheduler.

The ranking is by expected saving. Each recurrence of a failure costs a full correction loop —
thousands of tokens of misdirected work plus the correction itself — so the classes that keep
coming back are worth resolving first. It follows that **an F sitting at `recurrence: 0` forever
is a correct outcome, not a backlog failure**: a class that never recurred has negative compile
ROI, and `captured` is its proper end state. A queue whose bottom never empties is working as
designed.

Resolution attempts are parasitic too. The session-start injection surfaces at most one line for
the highest-recurrence unresolved class, and the attempt itself happens during the next related
piece of live work — where the context is loaded and the tokens are being spent anyway.

## Boundary with host memory

Any harness may have its own memory: `CLAUDE.md`, `AGENTS.md`, auto-memory, a notes file. The
boundary is ownership, not storage:

- **ani is the single owner of procedural correction knowledge** — situation → action →
  verification.
- **Host memory keeps declarative facts** and refers to patterns by ID only, e.g.
  `ani:S-dark-mode-tokens`.
- **Never copy a pattern body into host memory.** Copies drift, and a demotion cannot reach
  them: retiring an S does nothing about a paragraph someone pasted into `CLAUDE.md` six weeks
  ago. That stale copy is exactly the "wrong manual re-applied" failure the `review-needed`
  state exists to prevent.
