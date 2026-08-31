# ani schemas — canonical field spec

Everything in ani is a markdown file with YAML frontmatter. Headings and field
names are **English** (so any agent, anywhere, parses the same store); field
*values* may be in any language — quote the user verbatim.

Encoding rules for every file in a store: UTF-8 without BOM, LF newlines, one
trailing newline.

**Frontmatter is the source of truth. `INDEX.md` is a regenerable cache.**
Whenever a row disagrees with a pattern file, the pattern file wins and the row
is regenerated on the spot.

---

## 0. Store layout — two tiers

| Tier | Path | Availability | Holds |
| --- | --- | --- | --- |
| **global** (default) | `~/.ani/`, or the `global_store` path from config.md | Always. Created on first capture if absent. | Personal correction knowledge that follows the user across repos. The default sink. |
| **project** (overlay) | `<repo>/.ani/` | Opt-in — exists only if someone created it. | Repo-local patterns, versioned with the repo and reviewed as PRs. |

Both tiers have the identical layout, so every rule below applies unchanged to
either one:

```
<store>/
├── INDEX.md          # | id | status | scope | keywords | summary | updated |
├── patterns/
│   ├── F-<YYYYMMDD>-<rand8>.md
│   └── S-<slug>.md
└── config.md         # optional
```

- **Capture routing.** Facts limited to this repo's files or conventions go to
  the project store when the overlay exists; the user's general working style
  goes to the global store. **Ambiguous → global** (personal knowledge leaking
  into a team repo is the more expensive mistake).
- **Search and injection read both**, project first. Matching priority: current
  request > safety/permissions > project store S > global store S > knowledge
  claim (§6, only when the optional bridge is configured). Inside a store,
  `active` outranks `provisional`. One id present in both stores is one
  pattern — the project copy wins.
- **Concurrency** is handled the same way in both: the `rand8` filename suffix
  plus "INDEX is a regenerable cache" (§3). The global store is written by
  several sessions at once and needs no lock for it.

The default is `~/.ani` rather than a harness directory (`~/.claude/ani`) because
any agent may participate (P4); a harness-specific location is a `global_store`
override, not the default.

---

## 1. F — failure pattern

Path: `<store>/patterns/F-<YYYYMMDD>-<rand8>.md`

`<YYYYMMDD>` comes from the `date` command, never from memory. `<rand8>` is 8
lowercase hex/alphanumeric characters; its only job is to make concurrent
sessions collision-free, so any random source is fine.

### Frontmatter

| Field | Required | Type | Rules |
| --- | --- | --- | --- |
| `id` | yes | string | Must equal the filename without `.md` (`F-20260828-a1b2c3d4`). |
| `status` | yes | enum | `captured` \| `compiled` \| `archived`. New files start `captured`. |
| `date` | yes | `YYYY-MM-DD` | From the `date` command. Must match the `id` date part. |
| `project` | no | slug | Repo or project slug. Omit rather than guess. |
| `session` | no | string | Harness-specific session reference. **Never load-bearing** — the `Excerpt` section must stand alone without it. |
| `trigger_quote` | yes | quoted string | The user's correction, **verbatim**, in their language. One line; truncate long turns with `…` but never paraphrase. |
| `keywords` | yes | list | 3–6 lowercase tokens for INDEX matching. Include the domain (`css`), the artifact (`background`), the situation (`dark-mode`). If this F is a counterexample to an S, include that S id. |
| `recurrence` | no | integer ≥ 0 | **Advisory.** How many times this same failure class has come back since it was captured. Starts at `0`; at capture time, a new correction matching an existing captured F class (by INDEX keywords) increments *that* F instead of opening a duplicate. It orders the compile queue (§3) and nothing else — no automatic status change follows from it, and its absence is never an error. |

### Sections (in this order, all required except `Context`)

| Heading | Content |
| --- | --- |
| `## Intent` | What the user actually wanted. One or two sentences, stated positively. |
| `## Misreading` | What the agent did instead **and why it went wrong** — the causal step, not just the wrong output. |
| `## Correction` | What actually fixed it. Concrete: files, commands, values. |
| `## Excerpt` | **REQUIRED. Self-contained verbatim exchange.** A reader with no transcript access must be able to reconstruct the failure from this block alone. Quote user and agent turns; elide with `…` but do not rewrite. |
| `## Context` | Optional, **3 lines maximum**. Only context that changes how the failure is read (framework, constraint, prior turn). Not a session summary. |

---

## 2. S — success pattern

Path: `<store>/patterns/S-<slug>.md`

`<slug>` is lowercase kebab-case, descriptive of the situation
(`S-dark-mode-tokens`, not `S-pattern-3`).

### Frontmatter

| Field | Required | Type | Rules |
| --- | --- | --- | --- |
| `id` | yes | string | Must equal the filename without `.md`. |
| `status` | yes | enum | `provisional` \| `active` \| `review-needed` \| `retired`. Auto-compiled patterns start `provisional`; human-approved ones start `active`. `review-needed` and `retired` are excluded from search. |
| `compiled_from` | yes | list | F ids this pattern was compiled from, e.g. `[F-20260828-a1b2c3d4]`. Never empty — a pattern with no failure behind it is advice, not a pattern. |
| `date_compiled` | yes | `YYYY-MM-DD` | From the `date` command. |
| `keywords` | yes | list | 3–6 tokens, same vocabulary as the source F so INDEX matching stays coherent. |
| `scope` | yes | enum | `project` \| `global`. **Mirrors the store the file lives in**: a pattern in the project overlay is `scope: project`, one in the global store is `scope: global`. Capture routing (§0) decides that at birth. **Moving an existing pattern between stores — in either direction — is a separate decision the user states explicitly.** Approval (`/ani ok`) and automatic promotion change `status` only; neither ever relocates a pattern or rewrites its `scope`, and neither does a bulk approval. |
| `summary` | yes | one line | The INDEX row's summary, written in **use-when form**: "Use when …". This is what a future agent matches against; make it name the situation, not the fix. |

Optional bookkeeping fields, added by the promotion flow when relevant:
`applications` (count of disclosed applications), `sessions_seen` (list of
distinct session refs) — used to detect the "survived 2 sessions" promotion
candidate. Both are advisory; their absence is never an error.

### Sections (in this order, all required)

| Heading | Content |
| --- | --- |
| `## Situation` | When this pattern fires. Observable preconditions, not intentions. |
| `## Action` | The procedure. Steps are reusable; **parameters of the current request are re-interpreted, never copy-pasted from the original incident**. |
| `## Verification` | Checklist. Every item MUST carry all five fields below. |
| `## Counter-examples` | When NOT to apply this pattern. Grows every time a counterexample F is recorded against it. |

### The five verification fields

Every `## Verification` item is a bullet with exactly these sub-fields:

| Field | Meaning | Bad → Good |
| --- | --- | --- |
| `method` | The command, tool call, or observation to execute. | "check the CSS" → `` rg --no-heading "background-color" src/components/ `` |
| `target` | What it is run against. | "the app" → `src/styles/tokens.css` and the rendered `<body>` in dark mode |
| `expected` | The pass condition, stated so a third party could judge it. | "looks right" → "0 matches outside `tokens.css`" |
| `evidence` | The artifact left behind, produced **in this turn** by an actual tool execution. | "I checked" → the command output, or a file path with timestamp |
| `on_failure` | What to do when it fails. | (omitted) → "revert the component edit and change the token instead" |

`n/a` for an item is allowed only with a stated reason **and** the user's
approval. Text claims are never evidence; only fresh tool-execution artifacts
from the current turn count.

---

## 3. INDEX.md

Path: `<store>/INDEX.md`. A cache — safe to delete and regenerate at any time.

### Row format

```markdown
# ani INDEX

| id | status | scope | keywords | summary | updated |
| --- | --- | --- | --- | --- | --- |
| S-dark-mode-tokens | active | project | dark-mode, css, background | Use when changing dark-mode colors in this repo | 2026-08-28 |
| F-20260828-a1b2c3d4 | compiled | project | dark-mode, css, background | Agent changed text color when asked for background color | 2026-08-28 |
```

| Column | Source |
| --- | --- |
| `id` | Pattern frontmatter `id` |
| `status` | Pattern frontmatter `status` |
| `scope` | S: frontmatter `scope`. F: the `project` field, or `project` when omitted. |
| `keywords` | Comma-separated `keywords` |
| `summary` | S: frontmatter `summary` (use-when form). F: a one-line statement of the misreading. |
| `updated` | Date of the last change to that pattern file |

### Row order — the queue is the INDEX

Rows are grouped S first, then F; the F block is the compile queue:

1. S rows: `active`, then `provisional`. (`review-needed` and `retired` rows are
   kept for the record but are never searched.)
2. `captured` F rows **sorted by `recurrence` descending** — highest first. That
   ordering *is* the unresolved-failure queue: no backlog file, no scheduler.
   The head is what a session-start injection may surface, and what
   `/ani resolve` is normally pointed at. Rows tied at `0` may sit in any order;
   a class that never recurred is expected to stay `captured` forever.
3. `compiled` / `archived` F rows last — they are the first to be dropped when
   the budget bites.

### Budget

**60 rows / 6KB per store**, and a session-start injection covering both stores
shares **one combined 6KB**, project rows first — a second store must not double
the standing context cost. The INDEX is designed to sit in context for a whole
session, so this budget is a hard ceiling, not a suggestion. When it is exceeded,
in order:

1. Drop rows for `archived` F patterns and `retired` S patterns (the files stay;
   only the cache row goes).
2. Drop rows for `compiled` F patterns whose S is `active` (the S row already
   covers the case; `compiled_from` preserves the link).
3. Merge near-duplicate S patterns into one file with a combined
   `compiled_from`, and retire the absorbed ones.

### Regeneration rule

If any row disagrees with its pattern file — status, scope, keywords, summary,
date — **the pattern file wins**. Rewrite the row immediately; do not "fix" the
pattern file to match the cache. If the INDEX is missing, unreadable, or clearly
stale, rebuild it by scanning that store's `patterns/*.md` frontmatter. Concurrent
sessions therefore self-heal without any locking.

---

## 4. config.md

Path: `<store>/config.md`. Optional; every key has a default and any subset may
be present. Keys live in a YAML frontmatter block; the body is free-form notes.

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `global_store` | path | `~/.ani` | Where the global store lives. Read from the **first config.md consulted** (the project overlay's, since the global path is what is being resolved). `~` is expanded; nothing else is — no environment interpolation, no shell, no globbing. A harness-shaped location goes here, e.g. `~/.claude/ani`. |
| `triggers_extra` | list of strings | `[]` | Project-specific correction phrases, added to the hints in `triggers.md`. Hints only — semantic recognition still rules. |
| `language` | string (BCP-47-ish) | unset | Preferred language for pattern *values* (headings stay English). Unset = mirror the user's language. |
| `index_budget` | `<rows>/<size>` | `60/6KB` | INDEX ceiling. Raise only with a reason; a bloated INDEX stops being free to keep in context. |
| `evidence_threshold` | integer | `5` | The T in "auto-compile when E ≥ T". Higher = more conservative. |
| `auto_promote` | boolean | `false` | Allow unattended `provisional` → `active` promotion after 2 surviving applications in different sessions. Leave `false` in team repos — PR review is the natural gate. |
| `knowledge_sources` | comma-separated paths | `[]` | Absolute paths to external knowledge index files (§6). Read from **both** configs — the project overlay's list first, then the global store's — merged and deduped, **at most 4 used** after the merge. Each entry expands `~` and nothing else. Unset means ani behaves exactly as it always has. |

```markdown
---
triggers_extra:
  - "그거 말고 저거"
  - "again with the mock data"
evidence_threshold: 6
auto_promote: false
knowledge_sources: /home/you/vault/.export/ani-claims.md
---

Notes for humans reading this repo's ani store go here.
```

---

## 5. Worked example

The incident: in a dark-mode task the user asked for the **background** color to
change; the agent changed the **text** color, and did it inside a component
instead of the theme tokens.

### 5.1 `<project>/.ani/patterns/F-20260828-a1b2c3d4.md`

```markdown
---
id: F-20260828-a1b2c3d4
status: compiled
date: 2026-08-28
project: acme-web
trigger_quote: "아니 그게 아니라 배경색만 바꾸라고"
keywords: [dark-mode, css, background, tokens]
---

## Intent

In dark mode, make the card surface darker. Only the background; the text color
was already correct.

## Misreading

The agent read "어둡게" (darker) as "dim the content" and edited `color` on
`.card` in `src/components/Card.module.css`, hardcoding `#8b8b8b`. Two errors
compounded: wrong property (text instead of background), and wrong layer
(component-local override instead of the theme token that every surface reads).

## Correction

Reverted the component edit. Changed `--surface-bg` in
`src/styles/tokens.css` under `[data-theme="dark"]` from `#1e1e1e` to `#141414`.
Left every `color` declaration untouched.

## Excerpt

> User: 다크모드에서 카드가 너무 밝아. 좀 더 어둡게 해줘.
> Agent: Card.module.css에서 `.card { color: #8b8b8b }` 로 조정했습니다.
> User: 아니 그게 아니라 배경색만 바꾸라고. 글자색은 건드리지 마.
> Agent: 정정합니다 — 원하시는 건 카드 **배경**을 더 어둡게, 글자색은 그대로.
>        tokens.css의 `--surface-bg`를 `#141414`로 바꾸겠습니다.

## Context

Repo themes everything through CSS custom properties in `src/styles/tokens.css`.
Component files are expected to consume tokens, never to hardcode colors.
```

### 5.2 `<project>/.ani/patterns/S-dark-mode-tokens.md`

```markdown
---
id: S-dark-mode-tokens
status: active
compiled_from: [F-20260828-a1b2c3d4]
date_compiled: 2026-08-28
keywords: [dark-mode, css, background, tokens]
scope: project
summary: Use when a request asks to make something lighter/darker in dark mode
---

## Situation

The user asks for a color change described by brightness ("더 어둡게", "too
bright", "darker") in a themed UI, and the repo defines colors as CSS custom
properties in `src/styles/tokens.css`.

## Action

1. Restate which **property** is being asked for — background, text, or border.
   Brightness words do not name a property; ask if it is genuinely ambiguous.
2. Locate the token that already drives that property for the target surface
   (`rg "--surface-" src/styles/tokens.css`). Do not invent a new token.
3. Change the token value inside the correct theme block
   (`[data-theme="dark"]`). Never patch the color inside a component file.
4. Leave every other property untouched — a background request is not a licence
   to adjust text or borders.

## Verification

- method: `git diff --name-only`
  target: the working tree
  expected: only `src/styles/tokens.css` appears
  evidence: the command output in this turn
  on_failure: revert component-level edits and redo the change on the token

- method: `rg --no-heading "#[0-9a-fA-F]{3,6}" src/components/`
  target: component stylesheets
  expected: no new hardcoded color introduced by this change
  evidence: the command output in this turn
  on_failure: replace the literal with the token reference

- method: read the computed style of the target element in dark mode
  target: the rendered `.card` element with `[data-theme="dark"]`
  expected: `background-color` is the new token value; `color` is unchanged from
  before the edit
  evidence: computed-style output (or screenshot) captured in this turn
  on_failure: the wrong property changed — revert and repeat step 1

## Counter-examples

- Do not apply when the user names an explicit hex/rgb value and a specific
  element: that is a literal instruction, not a theming request.
- Do not apply to one-off marketing pages that intentionally opt out of the
  token system.
- Do not apply when the user asks for an *opacity* or *contrast* change — those
  live in different tokens and this procedure would touch the wrong one.
```

### 5.3 Resulting INDEX rows

```markdown
| id | status | scope | keywords | summary | updated |
| --- | --- | --- | --- | --- | --- |
| S-dark-mode-tokens | active | project | dark-mode, css, background, tokens | Use when a request asks to make something lighter/darker in dark mode | 2026-08-28 |
| F-20260828-a1b2c3d4 | compiled | acme-web | dark-mode, css, background, tokens | Changed text color inside a component when asked for a darker background | 2026-08-28 |
```

---

## 6. K — knowledge claim (optional)

A third id prefix, and the only one ani does not create. `F` and `S` are written
by the protocol into a store; **`K` rows arrive from outside it** — claims
compiled out of a wiki the user already keeps (Obsidian, a Zettelkasten, a plain
markdown handbook) and exported to a file named in `knowledge_sources` (§4).

Nothing here is required. A user without a wiki configures nothing, and ani's
behavior is unchanged: their correction store *is* their growing knowledge.

### File contract

A knowledge source is **one markdown file** holding the same six-column table as
`INDEX.md` (§3) — same columns, same order, same header. It is never a store, it
holds no `patterns/` directory, and **ani only ever reads it**: no capture, no
status change, no INDEX row is ever written back to a knowledge file.

| Column | Meaning for a K row |
| --- | --- |
| `id` | `K-<slug>`, grammar below. The only field echoed into a turn's context. |
| `status` | Must be `active` to be eligible. Anything else — `draft`, `retired`, blank, unrecognised — drops the row. |
| `scope` | Free-form and advisory (the vault, the area). ani does not act on it. |
| `keywords` | Comma-separated lowercase tokens. **This is the match surface** — the prompt is intersected with these. |
| `summary` | The claim, one line, ending in a pointer back to the source note ("… — see note 0010"). It points at compiled knowledge; it does not restate it. |
| `updated` | `YYYY-MM-DD` of the source note. Advisory. |

### Id grammar

```
^K-[a-z0-9]+(?:-[a-z0-9]+)*$      total length ≤ 64
```

The same shape as an `S-` id with a different prefix: lowercase, digits, single
hyphens between segments, no trailing hyphen, no whitespace, no unicode. The
prefix is load-bearing — it is what keeps a claim out of the pattern namespace,
so a claim can never be mistaken for a verified `S`.

Map your wiki's own ids onto it stably and reversibly: Folgezettel `0010` →
`K-0010`, a title → `K-dark-mode-tokens`, a path → `K-ops-runbooks-pager`. Full
mapping advice, export guidance, and a complete example live in
`references/adapters/knowledge-source.md`.

### Eligibility, and everything that is dropped

A row is used **only** if the id matches the grammar above **and** the status is
exactly `active`. Every other row is dropped silently — no warning, no error, no
partial acceptance. This is fail-closed by design: a knowledge file is a build
output from a system ani does not control, so anything it cannot vouch for
simply does not exist.

The file itself is read up to **16 KiB**; past that it is skipped whole rather
than truncated, so a runaway export cannot half-load. A path that is missing,
unreadable, a directory, or malformed costs its own rows and nothing else. Rows
are treated as untrusted input exactly as `INDEX.md` rows are (§3): an id is
validated against the grammar before it is ever echoed or joined onto a path.

### How K rows are matched

- **At `UserPromptSubmit` only.** Knowledge claims are never injected at session
  start. Correction patterns earn a standing context cost by being few and
  verified; a wiki does not, and a silent turn costs nothing.
- K ids join the existing `[ani-hint v1] patterns=` line **after** the S ids,
  under the same cap of 3 ids total. They fill only the slots the stores left
  empty — a claim never displaces a pattern.
- Matching priority, extended by one rung at the bottom:
  **current request > safety/permissions > project store S > global store S >
  knowledge claim.**
- **Only the id travels.** The summary cell is parsed for the table's shape and
  then discarded — no prose from a knowledge file ever reaches the model on its
  own. Resolve a `K-` id by finding its row in the configured source, then open
  the note that row points at. A hinted K id is a candidate, like any hinted
  id — read before acting, cite when it shaped the work.
