# Adapter: generic (any file-capable agent)

**If you can read and write files, you can participate.** ani has no server, no API, and no
runtime — it is a directory convention. This page is the whole convention.

## Stores — two tiers, identical layout

```
~/.ani/               # GLOBAL, the default. Always available; created on first capture.
├── INDEX.md          # | id | status | scope | keywords | summary | updated |  (one row per pattern)
├── patterns/
│   ├── F-<YYYYMMDD>-<random8>.md   # failure pattern
│   └── S-<slug>.md                 # success pattern
└── config.md         # optional: global_store path, extra trigger phrases, language, budgets

<project>/.ani/       # PROJECT overlay, opt-in. Same layout. Repo-local, shared through git.
```

Write repo-specific corrections to the project overlay when it exists, the user's general
working style to the global store, and **anything ambiguous to the global store**. Read both,
project first. `global_store` in the first `config.md` you read moves the global tier
elsewhere (e.g. `~/.claude/ani`); `~` is expanded and nothing else is.

`INDEX.md` is a regenerable cache. The frontmatter inside each pattern file is the source of
truth: if they disagree, the frontmatter wins and you rebuild the index on the spot. Field
names and status values are English; the values you write may be in any language. The
normative schema is `skills/ani/references/schemas.md`.

## Protocol

Fires when a user message *means* "you misunderstood me" — decided semantically, not by
string match. `skills/ani/references/triggers.md` holds per-language phrase hints.

1. **RESTATE** — restate the user's real intent in one line before doing anything else; ask
   at most one clarifying question.
2. **SEARCH** — read the `INDEX.md` of both stores (also before any non-trivial task, not
   only after a correction), open only candidate S files, and apply the best match: project
   store before global, `active` before `provisional` — which must be disclosed as
   provisional. Cite the pattern id. Never apply `review-needed` or `retired`. Follow the S
   Action and execute its Verification items; evidence counts only if it is tool output
   produced in the current turn.
3. **FIX** — carry out the correction. Recording never blocks the work.
4. **CAPTURE** — pick the store by the routing rule above, write
   `<store>/patterns/F-<YYYYMMDD>-<random8>.md` (the random suffix is what keeps concurrent
   sessions from colliding), update that store's `INDEX.md`, commit if git is present. If
   the correction repeats a class already captured, increment that F's advisory
   `recurrence` instead of writing a duplicate.
5. **TRIAGE** — assess context health and *recommend*, never force: continue, rewind to
   before the confusion, or restart in a clean session that reads only the new F file. The
   F file is the checkpoint, so the polluted context is now disposable.

Compile F into S with `situation / action / verification / counter-examples`, in the F's own
store. Automatic compilation is capped at `provisional` (evidence score E >= 5); `active`
requires explicit human approval. Close the F as `compiled` and keep provenance in
`compiled_from`. Compilation rides the success run FIX already performed — never re-run a
past failure offline to manufacture evidence unless the user explicitly asks
(`/ani resolve <F-id>`). Captured INDEX rows are kept sorted by `recurrence`, descending:
that ordering is the queue of unresolved failure classes, and one that never recurs is
meant to stay `captured`.

## State machines

```
F:  captured ──compile (auto E>=5 | human approval)──▶ compiled          └──▶ archived (manual)
S:  provisional ──2 clean sessions + approval──▶ active ──counterexample──▶ review-needed ──▶ active | retired
                └──counterexample──▶ retired (immediate)                  (review-needed is excluded from search)
```
