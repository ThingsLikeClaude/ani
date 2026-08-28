# Adapter: AGENTS.md / system prompt snippet

For harnesses with no skill system and no hooks (Codex and similar). This is Tier 0 in one
block — semantic detection only, no scripts.

**Install (5 steps).**
1. Create the **global** store at `~/.ani/` with an empty `patterns/` directory and an
   `INDEX.md` containing the title `# ani INDEX` and the header row plus separator:
   `| id | status | scope | keywords | summary | updated |` / `| --- | --- | --- | --- | --- | --- |`.
   Add the **project overlay** `<repo>/.ani/`, same layout, only if you want repo-local
   patterns shared with your team.
2. Copy `skills/ani/references/schemas.md` into the repo (or keep this repo as a submodule)
   so the agent can read the normative F/S schema.
3. Paste the block below into `AGENTS.md` at your project root — or into your agent's system
   prompt / custom-instructions field if it has no `AGENTS.md`.
4. Fix the paths in the block if your copies live elsewhere (the stores and `schemas.md`).
5. Test it: give the agent a small task, correct it with "no, that's not it — I meant …",
   and confirm a file appears under `~/.ani/patterns/` (or the overlay's `patterns/`).

---

```markdown
## ani protocol (correction capture)

When a user message *means* "you misunderstood me" — a correction, not a new request —
run the steps below. Judge by meaning, not string match; these are only hints:
ko "아니 그게 아니라" / "그거 말고" / "내 말은" / "왜 자꾸", en "no, that's not it" /
"I meant" / "that's not what I asked", ja "そうじゃなくて", zh "不是这个意思".

Two stores, identical layout: the GLOBAL `~/.ani/` (default, always there — personal
knowledge that follows the user) and the opt-in PROJECT overlay `<repo>/.ani/` (repo-local,
shared with the team). Read both; write repo-specific facts to the overlay when it exists,
general working style to the global store, and anything ambiguous to the global store.

1. RESTATE — say the user's real intent back in one line; ask at most one question if it is
   ambiguous. Do this before searching, fixing, or recording.
2. SEARCH — read the `INDEX.md` of both stores (also before any non-trivial task, not only
   after a correction) and open only the candidate S files. Priority: project store before
   global; inside a store, `active` before `provisional`. Apply an S by following its Action
   and executing its Verification, citing its id. A `provisional` S MUST be announced as
   provisional. Ignore `review-needed` and `retired`.
3. FIX — carry out the correction now. Recording never blocks the work.
4. CAPTURE — write `<store>/patterns/F-<YYYYMMDD>-<random8>.md` per the schema in
   `skills/ani/references/schemas.md`: frontmatter (id, status: captured, date, keywords,
   trigger_quote) plus sections Intent / Misreading / Correction / Excerpt (verbatim and
   self-contained) / Context. If this repeats an already-captured class, increment that F's
   advisory `recurrence` instead of duplicating it. Update that store's `INDEX.md` — one
   line per pattern, captured rows sorted by `recurrence` descending; it is a regenerable
   cache, so on any conflict the file's frontmatter wins and you rebuild the index. Commit
   if the store is in a git repo.
5. TRIAGE — recommend, never force: first simple misread → continue here; second correction
   on the same item → suggest rewinding to before the confusion; repeated failure or a long
   polluted session → suggest a new session that reads only the F file just written.

Compiling F into S. Automatic compilation is capped at `provisional` and fires when the
evidence score E >= 5: +2 explicit positive acknowledgement, +2 verification actually
executed and passed, +1 no re-correction on the topic through end of session, +2 recurrence
of the same pattern class. Every required S field being concrete is a prerequisite gate, not
points; any re-correction on the same topic disqualifies the round (in "good, but change X"
the softener scores 0 when the change targets the same topic). `active` requires explicit
user approval. A re-correction after applying a provisional S retires it immediately; after
an active S it drops to `review-needed` and is excluded from search. Every S must carry
Verification items stating method / target / expected / evidence / on_failure, and evidence
counts only when it is tool output produced in the current turn. That evidence comes from
the success run FIX already performed for the user — never re-run a past failure offline to
manufacture it unless the user explicitly asks.
```
