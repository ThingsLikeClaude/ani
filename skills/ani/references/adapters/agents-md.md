# Adapter: AGENTS.md / system prompt snippet

For harnesses with no skill system and no hooks (Codex and similar). This is Tier 0 in one
block — semantic detection only, no scripts.

**Install (5 steps).**
1. Create `.ani/` at your project root with an empty `patterns/` directory and an `INDEX.md`
   containing the title `# ani INDEX` and the header row plus separator:
   `| id | status | scope | keywords | summary | updated |` / `| --- | --- | --- | --- | --- | --- |`.
2. Copy `skills/ani/references/schemas.md` into the repo (or keep this repo as a submodule)
   so the agent can read the normative F/S schema.
3. Paste the block below into `AGENTS.md` at your project root — or into your agent's system
   prompt / custom-instructions field if it has no `AGENTS.md`.
4. Fix the two paths in the block if your copies live elsewhere (`.ani/` and `schemas.md`).
5. Test it: give the agent a small task, correct it with "no, that's not it — I meant …",
   and confirm a file appears under `.ani/patterns/`.

---

```markdown
## ani protocol (correction capture)

When a user message *means* "you misunderstood me" — a correction, not a new request —
run the steps below. Judge by meaning, not string match; these are only hints:
ko "아니 그게 아니라" / "그거 말고" / "내 말은" / "왜 자꾸", en "no, that's not it" /
"I meant" / "that's not what I asked", ja "そうじゃなくて", zh "不是这个意思".

1. RESTATE — say the user's real intent back in one line; ask at most one question if it is
   ambiguous. Do this before searching, fixing, or recording.
2. SEARCH — read `.ani/INDEX.md` (also read it before any non-trivial task, not only after a
   correction) and open only the candidate S files. Apply an `active` S by following its
   Action and executing its Verification, citing its id. A `provisional` S ranks below
   active and MUST be announced as provisional. Ignore `review-needed` and `retired`.
3. FIX — carry out the correction now. Recording never blocks the work.
4. CAPTURE — write `.ani/patterns/F-<YYYYMMDD>-<random8>.md` per the schema in
   `skills/ani/references/schemas.md`: frontmatter (id, status: captured, date, keywords,
   trigger_quote) plus sections Intent / Misreading / Correction / Excerpt (verbatim and
   self-contained) / Context. Update `.ani/INDEX.md` — one line per pattern; it is a
   regenerable cache, so on any conflict the file's frontmatter wins and you rebuild the
   index. Commit if the project uses git.
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
counts only when it is tool output produced in the current turn.
```
