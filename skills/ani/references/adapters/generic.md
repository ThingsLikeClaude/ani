# Adapter: generic (any file-capable agent)

**If you can read and write files, you can participate.** ani has no server, no API, and no
runtime — it is a directory convention. This page is the whole convention.

## Store

```
<project>/.ani/
├── INDEX.md          # | id | status | scope | keywords | summary | updated |  (one row per pattern)
├── patterns/
│   ├── F-<YYYYMMDD>-<random8>.md   # failure pattern
│   └── S-<slug>.md                 # success pattern
└── config.md         # optional: extra trigger phrases, language, budget overrides
```

`INDEX.md` is a regenerable cache. The frontmatter inside each pattern file is the source of
truth: if they disagree, the frontmatter wins and you rebuild the index on the spot. Field
names and status values are English; the values you write may be in any language. The
normative schema is `skills/ani/references/schemas.md`.

## Protocol

Fires when a user message *means* "you misunderstood me" — decided semantically, not by
string match. `skills/ani/references/triggers.md` holds per-language phrase hints.

1. **RESTATE** — restate the user's real intent in one line before doing anything else; ask
   at most one clarifying question.
2. **SEARCH** — read `.ani/INDEX.md` (also before any non-trivial task, not only after a
   correction), open only candidate S files, and apply the best match: `active` first, then
   `provisional` — which must be disclosed as provisional. Cite the pattern id. Never apply
   `review-needed` or `retired`. Follow the S Action and execute its Verification items;
   evidence counts only if it is tool output produced in the current turn.
3. **FIX** — carry out the correction. Recording never blocks the work.
4. **CAPTURE** — write `.ani/patterns/F-<YYYYMMDD>-<random8>.md` (the random suffix is what
   keeps concurrent sessions from colliding), update `INDEX.md`, commit if git is present.
5. **TRIAGE** — assess context health and *recommend*, never force: continue, rewind to
   before the confusion, or restart in a clean session that reads only the new F file. The
   F file is the checkpoint, so the polluted context is now disposable.

Compile F into S with `situation / action / verification / counter-examples`. Automatic
compilation is capped at `provisional` (evidence score E >= 5); `active` requires explicit
human approval. Close the F as `compiled` and keep provenance in `compiled_from`.

## State machines

```
F:  captured ──compile (auto E>=5 | human approval)──▶ compiled          └──▶ archived (manual)
S:  provisional ──2 clean sessions + approval──▶ active ──counterexample──▶ review-needed ──▶ active | retired
                └──counterexample──▶ retired (immediate)                  (review-needed is excluded from search)
```
