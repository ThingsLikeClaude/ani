# Adapter: knowledge source (any wiki)

Optional, and optional twice over. ani works with nothing but its own two stores;
this adapter exists for people who *already* keep a wiki — Obsidian, a
Zettelkasten, a docs folder, a company handbook in plain markdown — and would
rather have the agent consult it than re-derive the same conclusions from
scratch.

The bridge is one file. You export a table of **claims** from your wiki, name it
in `knowledge_sources`, and ani's `UserPromptSubmit` hint engine starts matching
it alongside the correction store. Nothing else about your wiki changes: ani
never reads your notes, never writes to them, and never needs to know what tool
produced them.

**No wiki? Skip this page entirely.** Your correction store already is your
growing knowledge — that is the whole product, and this adapter adds nothing you
are missing.

## 1. What a knowledge file is

A single markdown file holding the **same six-column table as `INDEX.md`**
(`schemas.md` §3). One row per claim:

```markdown
| id | status | scope | keywords | summary | updated |
| --- | --- | --- | --- | --- | --- |
| K-0010 | active | zettel | postgres, index, btree | Composite index column order follows selectivity — see note 0010 | 2026-08-14 |
```

That is the entire contract. A knowledge file is a *build output*: something
your wiki's export script writes, not something a human maintains by hand.

| Column | What to put in it |
| --- | --- |
| `id` | `K-<slug>` — the row's handle, and the only part echoed into the agent's context. Grammar in §2. |
| `status` | `active` for rows you want matched. **Anything else is dropped**, which is how you keep drafts out. |
| `scope` | Free-form and advisory: the wiki, the vault, the area (`zettel`, `handbook`, `ops`). ani does not act on it; keep it short and non-empty. |
| `keywords` | Comma-separated, lowercase. **This is what actually matches** — the hint engine intersects these with the user's prompt, so write the words a person types, not the words a taxonomy prefers. 3–6 is a good row. |
| `summary` | The claim itself, in one line, ending in a pointer back to the note. See §3 — this column is the reason the whole thing exists. |
| `updated` | `YYYY-MM-DD` of the source note's last change. Advisory; useful when you are looking at a stale export. |

## 2. `K-` id grammar, and mapping your wiki onto it

An id is eligible only if it matches `^K-[a-z0-9]+(?:-[a-z0-9]+)*$` and is at
most 64 characters — the same shape `S-` ids must have, with a different prefix.
Lowercase, digits, single hyphens between segments, no trailing hyphen, no
spaces, no unicode. A row whose id does not match is dropped without comment.

The prefix is not decoration: `K` is what keeps knowledge claims out of the
`S-`/`F-` namespace, so ani can rank them last (§5) and never confuse a claim
with a verified correction pattern.

| Your wiki's naming | Map it to | Note |
| --- | --- | --- |
| Folgezettel / numeric ids (`0010`, `12.4a`) | `K-0010`, `K-12-4a` | Keep the number recognisable — the point is that you can find the note from the id. |
| Note titles (`Dark mode tokens`) | `K-dark-mode-tokens` | Lowercase, spaces → hyphens, strip punctuation. |
| File paths (`ops/runbooks/pager.md`) | `K-ops-runbooks-pager` | Separators → hyphens. Drop the extension. |
| UUIDs / timestamps (`202608141530`) | `K-202608141530` | Legal, but a reader cannot guess the note from it — prefer a slug if your tool can produce one. |

Whatever the mapping is, it must be **stable and reversible**: you or the agent
should be able to go from `K-0010` back to the note in a couple of seconds. That
round trip is the entire value of the id.

## 3. What a claim is for

A claim is a **pointer to compiled knowledge**, not the knowledge itself.

You already did the thinking when you wrote the note. The failure mode ani is
attacking is the agent re-deriving that thinking from raw transcripts, half of
it, badly, every time the topic comes up. So the summary's job is to say enough
that the agent recognises the situation, and then to send it to the note:

> Composite index column order follows selectivity — see note 0010

not

> Postgres composite indexes should generally be ordered so that the most
> selective column comes first, although for range queries…

Two rules follow:

- **One line.** The row lives in a hint line inside a real turn's context. A
  paragraph here is a paragraph the user pays for on every match.
- **Name the note.** End with something the agent can act on — `see note 0010`,
  `see handbook/pager`, `consult K-0010 in the vault`. The body is *pulled* when
  it is needed; that is the compile-then-reference split the whole protocol is
  built on.

## 4. Wiring it up

`knowledge_sources` in a store's `config.md` frontmatter — comma-separated
absolute paths, **at most 4 used**:

```markdown
---
knowledge_sources: /home/you/vault/.export/ani-claims.md, /srv/handbook/ani-claims.md
---
```

Project (`<repo>/.ani/config.md`) and global (`~/.ani/config.md`) lists are
merged, project first, then deduped — and the cap of 4 applies **after** that
merge, not per file. Extras are dropped silently.

`ANI_KNOWLEDGE_SOURCES` in the environment takes the identical comma-separated
form and **replaces** both config lists rather than adding to them — an escape
hatch, and the thing to reach for when testing an export before committing to
it. Set-but-empty (`ANI_KNOWLEDGE_SOURCES=""`) is therefore a kill switch: zero
sources, no fall-through to config.

Paths are files, absolute, `~` expanded and nothing else — no environment
interpolation, no shell, no globbing, no directory scanning. An entry that is a
directory, does not exist, is unreadable, runs past 512 characters, or contains
a newline or NUL is skipped silently and costs its own rows only.

One limitation inherited from the hook adapter: the hooks locate the project
overlay by its `INDEX.md`, so a `.ani/` holding a `config.md` but no index yet
contributes no `knowledge_sources`. Use the environment variable until the
overlay has an index, or keep the key in the global store's config.

`/ani doctor` reports what it found: how many sources are configured, how many
resolved, and how many eligible `K-` rows each one yielded. Run it after your
first export.

## 5. What ani does with it, and what it will not do

- Matched **only at `UserPromptSubmit`**, never at session start. Correction
  patterns earn their standing context cost by being few and verified; a wiki
  does not, and silence costs nothing.
- K ids ride the existing `[ani-hint v1] patterns=` line, **after** the S ids,
  under the same cap of **3 ids in total**. K rows fill only the slots the
  stores left empty: three matching S patterns means no K ids at all. A claim
  never displaces a pattern.
- Priority for the model, unchanged at the top and extended at the bottom:
  **current request > safety and permissions > project store S > global store S
  > knowledge claim.** A claim is background; a verified pattern outranks it;
  the user outranks everything.
- **Only the id is injected**, never the summary. The agent resolves a hinted
  `K-0010` by reading the row back out of your file, and then opens the note the
  row points at — so a hinted id is a candidate, exactly like a hinted `S-` id,
  and your prose stays out of the context until something actually needs it.
- Rows are **untrusted input**, treated the way `INDEX.md` is: the id grammar is
  enforced before an id is echoed or joined onto a path, a status that is not
  `active` fails closed, and the file is read only up to **16 KiB** — past that
  cap it is skipped whole, not truncated.

That 16 KiB cap is the design constraint worth planning around: a knowledge file
is a **curated shortlist**, not a dump of your vault. Export the claims you
would actually want an agent to know, roughly 60–100 rows, and let the rest of
the wiki stay where it is.

## 6. Regeneration

The knowledge file is disposable build output, and treating it as anything else
is the one way to get hurt:

- **Re-export when the wiki changes.** A note edited after the last export is a
  claim ani is quoting from memory. Wire the export into whatever you already
  run — a commit hook, a nightly job, a `make` target, a manual command you
  remember to type.
- **Never hand-edit the file.** The next export overwrites it. If a claim is
  wrong, fix the note.
- **It is not a second source of truth.** Your wiki is. This is a cache of
  one-line pointers into it, exactly as `INDEX.md` is a cache of the pattern
  files — same architecture, one layer out.
- **Deleting it is safe.** Sources that do not resolve are skipped; ani goes back
  to behaving like it does for a user with no wiki, which is to say: fine.
- Keep it out of your wiki's own sync if that sync is shared — the export is
  cheap to regenerate and there is no reason for two machines to fight over it.

## 7. Worked example

An export from a Zettelkasten, four notes wide:

```markdown
# ani knowledge claims — exported from vault, do not edit

| id | status | scope | keywords | summary | updated |
| --- | --- | --- | --- | --- | --- |
| K-0010 | active | zettel | postgres, index, composite, selectivity | Composite index column order follows selectivity, not query order — see note 0010 | 2026-08-14 |
| K-0042 | active | zettel | retry, backoff, idempotent, queue | Retries need idempotency keys before they need backoff tuning — see note 0042 | 2026-07-02 |
| K-ops-pager | active | handbook | pager, oncall, escalation, incident | Escalate to secondary after 15 minutes of no ack, never by judgement call — see handbook/pager | 2026-08-20 |
| K-0113 | draft | zettel | cache, invalidation | (unfinished — dropped by the status filter) | 2026-08-29 |
```

Three rows are matched; the `draft` one is dropped silently, which is exactly
what you want a status column for. A prompt containing "composite index" fires
`K-0010`; the agent opens note 0010 and works from what you already concluded
there, instead of reasoning it out again in the dark.
