# Store boundary flows — publishing outward, disclosing inward

Status: design, approved 2026-09-01. Implements nothing yet.

## Why

ani keeps knowledge in two tiers (P7): a personal global store that follows the
user, and an opt-in project overlay that travels with the repo and is read by
whoever clones it. Today knowledge only ever *enters* a tier — capture routing
decides at birth, and `schemas.md` §2 forbids relocation as a side effect of
anything else:

> Moving an existing pattern between stores — in either direction — is a
> separate decision the user states explicitly. Approval (`/ani ok`) and
> automatic promotion change `status` only; neither ever relocates a pattern or
> rewrites its `scope`, and neither does a bulk approval.

That rule bans relocation-by-accident. It does not ban relocation. What is
missing is the deliberate act it describes, and the reciprocal act on the way
in: knowing that a pattern arriving from a teammate is a teammate's.

Two flows, one boundary:

| | Outbound | Inbound |
| --- | --- | --- |
| Trigger | the user types `/ani git` | a project pattern is about to be applied |
| Subject | the user's own global patterns | patterns the repo carries |
| Failure it prevents | sharing something the user did not choose to share | adopting someone else's rule without knowing it |
| Result | files written to the overlay | one line of disclosure |

Both depend on a fix that already landed: an id shadowed by the overlay is now
named at session start, so a collision is visible to both flows instead of
being silently resolved.

## Invariants

1. **Relocation is per-pattern and explicit.** A digest table may group and sort
   candidates; it may never carry a single approval that moves more than one.
2. **`scope` mirrors the store the file lives in.** A copy written into the
   overlay is `scope: project`; the global original keeps `scope: global`.
3. **Outbound copies, never moves.** Publishing is teaching. The user does not
   lose a pattern by sharing it.
4. **Nothing outside a store is written.** No commits, no branches, no git
   config — the boundary the first-capture self-check already draws. Reading
   outside a store is fine and Flow B depends on it.
5. **Disclosure never blocks.** ani's guarantee is that no automatic step beats
   a user veto, not that every step asks permission first. `provisional` is
   disclosed on application rather than gated behind consent, and inbound
   follows it.

## Flow A — outbound: `/ani git`

### A1. Overlay check

If `<repo>/.ani/` does not exist, ask before creating it, saying plainly that
the directory is committed and read by everyone who clones the repo. A refusal
ends the command with nothing written. Creating the overlay is opt-in (P7) and
this flow does not get to assume it.

### A2. Candidate set

Global `S` patterns whose `compiled_from` F files carry this repo's slug in
their `project` field.

**Repo slug.** `owner/repo` parsed from the `origin` remote when there is one,
otherwise the repo root's directory name. The remote is preferred because two
checkouts can share a directory name and mean different projects. F files
written before this rule existed may carry either form, so the comparison
matches on the full slug *or* on its last path segment — a stale `ani` still
matches `ThingsLikeClaude/ani`. Whatever writes `project` at capture time must
use this same rule; that is the first task of the implementation plan.

`project` is optional and the schema says "omit rather than guess", so it is
often absent. Presenting only slug matches would show an empty table for a
store full of relevant patterns. Candidates are therefore offered in two
labelled groups:

- **(a) captured in this repo** — the `project` slug matches.
- **(b) keyword overlap with this repo** — provenance unknown, but the
  pattern's `keywords` intersect this repo's vocabulary, defined concretely as
  the token set of the top two path levels of `git ls-files`, run through the
  tokenizer `ani_trigger.tokenize` already uses for matching. That works on a
  repo whose overlay is still empty, which is exactly the first-publish case.

Group (b) is labelled as a guess and never merged into (a). A guess presented
as provenance is the failure mode this project exists to prevent.

### A3. The table

One table, columns: `id | summary | compiled from | already in overlay | group`.

Rows are sorted so related subjects sit together — keyword Jaccard, the same
lexical clustering the bootstrap miner already uses. That clustering is the
"recommend related patterns" behaviour: it groups what the user *reads*, and
stops there.

The `already in overlay` column is what the shadowed-id fix bought. Without it
a user can publish a pattern that overwrites a teammate's without ever seeing
that it happened.

### A4. Selection

The user selects rows individually. There is no "approve all" control, because
invariant 1 forbids one approval from relocating several patterns.

### A5. Write

For each selected pattern: copy the file to `<repo>/.ani/patterns/`, set
`scope: project` in the copy, leave the global original untouched, and
regenerate the overlay's `INDEX.md` from the frontmatter of what is now there,
respecting the 60-row / 6KB budget.

An id already present in the overlay is **skipped, not overwritten**, and
reported as skipped. Overwriting is a second explicit instruction, never a
default: the existing file is someone else's work.

### A6. Stop

Report the files written and the ids skipped. Do not commit, branch, or push.
Say that committing is the user's to do.

## Flow B — inbound: disclosure on application

### B1. Trigger

Path A, at the moment a project-overlay `S` is applied.

### B2. Condition

Disclose when either holds:

- the pattern **shadowed** a global pattern of the same id — already computed
  and named in the session-start injection, so this costs nothing; or
- the file's last author is **not the user** —
  `git log -1 --format=%ae -- <path>`, compared to `git config user.email`.

Neither requires a schema change. Authorship is already recorded, by git,
because the overlay lives in the repo. An `author` field would duplicate that
and go stale.

### B3. Form

The `provisional` disclosure idiom, in the same place and register:

> Applying `S-commit-style` from the project overlay (written by a teammate;
> your global store has a pattern under the same id) — tell me if it is wrong.

Whichever half of the condition is false is omitted from the sentence.

### B4. Frequency

Once per id per session, following the handshake notice's existing rule — say
it once, then never again that session. `provisional` discloses on *every*
application because a trust rung is a live claim that can be withdrawn;
provenance is a fact that does not change mid-session, and repeating it is
noise.

### B5. Degradation

No git, no `user.email`, or a file git does not track: skip the authorship half
and evaluate the shadowing half alone. Never guess at authorship, and never
suppress the whole disclosure because one input was unavailable.

## Out of scope

- **Consent gates.** Inbound discloses; it does not stop and ask. Gating needs
  somewhere to record "I already accepted this", and `config.md` holds settings,
  not per-pattern decisions — a new artifact, a new schema, and a new question
  about which store owns it. Deferred until disclosure proves insufficient.
- **Committing or opening PRs** on the user's behalf (invariant 4).
- **The hint path.** `ani_trigger.py`'s `exclude` shadows ids the same way the
  injection did. The marker format differs enough to need its own judgement,
  and the session-start injection is where the agent's resident candidates come
  from, so it carries most of the value.
- **Moving a pattern from the overlay back to global.** The reverse relocation
  is a third flow with its own consent question, since removing a pattern from
  a repo affects the team. Neither flow here needs it.

## Testing

Both flows are agent behaviour specified in `SKILL.md` rather than new hook
code, with one exception: the authorship lookup in B2 is a shell call whose
failure modes need coverage. Testable propositions:

- A2: with `project` slugs present, group (a) is exactly the matching set; with
  all slugs absent, group (a) is empty and group (b) still populates.
- A5: a selected pattern appears in the overlay as `scope: project`; the global
  original is byte-identical afterwards; a colliding id is skipped and named.
- A6: no commit is created.
- B2/B5: each degradation path yields disclosure-without-authorship rather than
  silence.

## Known limits

- Group (b) is lexical, so a pattern phrased in vocabulary unlike the repo's
  will not surface. The same limitation the bootstrap miner documents.
- Group (a) is only as good as the `project` field. Every F captured before the
  slug rule in A2 exists carries whatever the agent chose at the time, or nothing
  at all; the last-segment fallback recovers some of those and not others.
