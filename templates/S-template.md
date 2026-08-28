---
# Copy to .ani/patterns/S-<slug>.md, then fill in and delete every comment line.
# Field spec: skills/ani/references/schemas.md
id: S-<kebab-case-slug>       # must equal the filename without .md
status: provisional           # provisional (auto, E>=T) | active (human-approved)
                              # later: review-needed | retired
compiled_from: [F-YYYYMMDD-rand8er]   # never empty — a pattern needs a failure behind it
date_compiled: YYYY-MM-DD     # from the `date` command
keywords: [<domain>, <artifact>, <situation>]   # reuse the source F's vocabulary
scope: project                # project | global  (global = manual promotion only)
summary: Use when <situation, in use-when form — this is the INDEX row a future
  agent matches against; name the situation, not the fix>
---

## Situation

<!-- When this pattern fires. Observable preconditions (what is in the request,
     what is in the repo), not intentions. -->

## Action

<!-- The procedure, as numbered steps. Steps are reusable; the current request's
     parameters are re-interpreted each time, never copy-pasted from the
     original incident. -->

1. <step>
2. <step>
3. <step>

## Verification

<!-- Every item MUST carry all five fields. "Looks right" is not a check.
     Ask at compile time: "what check would have caught this misreading?" —
     that answer is the item below. -->

- method: <the command / tool call / observation to execute>
  target: <what it runs against>
  expected: <the pass condition, judgeable by a third party>
  evidence: <the artifact left behind, produced by an actual tool run THIS turn>
  on_failure: <what to do when it fails>

- method: <…>
  target: <…>
  expected: <…>
  evidence: <…>
  on_failure: <…>

<!-- Skipping an item (n/a) requires a stated reason AND the user's approval. -->

## Counter-examples

<!-- When NOT to apply this pattern. Append a bullet every time a counterexample
     F is recorded against it. -->

- <situation where this procedure would be wrong>
- <adjacent-but-different request this must not swallow>
