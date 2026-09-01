# Adapter: publish (share global patterns with a repo's team)

The global store follows the user, not the repo — a pattern learned on one project
never reaches a teammate on another unless someone moves it there on purpose.
`/ani git` is that deliberate act: it lists global patterns that look relevant to
the current repo and copies the ones the user names into `<repo>/.ani/`, so the
next person who clones the repo starts with them already in place.

This is a **Tier 1** adapter: optional, and never a precondition for the core
protocol. Without it a pattern just stays global — personal until the user
publishes it or promotes it some other way.

Read `references/adapters/bootstrap.md` §1 for the shared "dumb miner" contract
before running this one; the difference that matters here is stronger than the
family resemblance suggests. Bootstrap ends in one decision that covers an
entire table, because a cold-start sweep can surface dozens of candidates and
asking for dozens of individual yes/no answers is how a user abandons the sweep
halfway. Publishing is the opposite shape: `schemas.md` §2 states plainly that
moving a pattern between stores is "a separate decision the user states
explicitly," and forbids a single approval from doing it for more than one
pattern at a time. Carry the wrong habit over from bootstrap and this flow
breaks the rule it exists to enforce. Treat every row below as its own yes or
no.

---

## 1. What this is

Publishing is teaching, not sorting. The candidate the user selects is **copied**
into `<repo>/.ani/patterns/`; the global original is never moved, edited, or
deleted. The user does not lose a pattern by sharing it — after a publish, the
file at `~/.ani/patterns/<id>.md` reads exactly as it did before the command ran.

`scripts/ani_publish.py` is the miner behind this, and it is dumb in the same
sense `ani_bootstrap.py` is: it reads the global store and the repo, prints a
digest of candidates, and writes nothing. Every relocation this adapter performs
is the agent acting on the user's explicit, per-row selection — never an
inference the script made for them.

---

## 2. Overlay check (A1)

Before anything else, check whether `<repo>/.ani/` exists.

- **It exists** — continue to the next step.
- **It does not exist** — ask the user before creating it, and say plainly what
  creating it means: this directory is committed to the repo and read by
  everyone who clones it, so anything published into it stops being personal.
  Creating a project overlay is opt-in (`SKILL.md`, "Stores"); this command does
  not get to assume the user wants one just because they typed `/ani git`.
  A refusal ends the command here — nothing is written, not even the directory.

---

## 3. Run the miner

Run `scripts/ani_publish.py` from the install root, by absolute path — the same
resolution `/ani doctor` uses (`SKILL.md` References, "Resolving the install
root"). Never a bare relative `python scripts/ani_publish.py`; that fails with
`[Errno 2] No such file` outside the install root.

```bash
python <install root>/scripts/ani_publish.py --repo <repo> --out <tmp>
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--repo` | current directory | Repo root to publish into. |
| `--global-store` | `~/.ani` | Where to read candidates from. Pass this explicitly when `config.md` sets a non-default `global_store` (`references/schemas.md` §4) — the script does not read `config.md` itself. |
| `--out` | stdout | Write the digest to a file instead. Prefer this for a store with many patterns, same reasoning as bootstrap's `--out`. |

The script is read-only: it never touches any store. If it exits non-zero or
raises, that is a bug in the miner, not a signal to fall back to reading the
store by hand — report it and stop.

**No `scripts/` at the install root** (a skill-directory-only install) — say the
subcommand is unavailable in this install and stop. Unlike F/S capture, there is
no manual fallback for this one: the point of the script is the repo-slug and
vocabulary matching, and reproducing that by hand from inside a conversation
burns context for no insight — the same reasoning `bootstrap.md` §1 gives for
why a script does the scanning at all.

---

## 4. Present the digest

Show the table the script emitted, verbatim: both groups, in the columns it
printed — `id | summary | compiled from | already in overlay | group`. Do not
re-sort, re-word, or merge the two groups into one list; keep the digest's own
caveat sentence for the keyword-overlap group intact, in the user's view, not
paraphrased away:

- **captured in this repo** — the pattern's source failure recorded this repo's
  slug in `project`. This is provenance.
- **keyword overlap with this repo** — no recorded provenance; the pattern's
  `keywords` happen to intersect this repo's vocabulary. This is a guess, and
  the two-group split exists precisely so a guess is never shown as if it were
  provenance.

Relay the digest's `## Scan` block with the table, and its
"**A resource cap fired during this scan.**" warning whenever that appears — the
digest was written to a file the user never opens, and those two are what make
the table honest about what it is *not* showing: how many patterns were held
back, and whether the miner managed to read the whole store.

Patterns whose `status` is `review-needed` or `retired` are **not in the table at
all**: they are excluded from search because a wrong manual cannot be re-applied
(`references/schemas.md` §2), so publishing one would hand a team a pattern that
was quarantined *because it was proven wrong*. The digest's `## Scan` block names
how many were held back, which is what keeps the filter visible instead of silent.

If the digest reports no candidates, say so and stop — there is nothing to
select, and that is a normal outcome, not a broken run. Relay the digest's own
reason, though: it distinguishes an empty result from a store directory it could
not find, and the second one means a wrong `--global-store`, not an empty store.

---

## 5. Selection (A4)

Ask the user which rows to publish, by id. There is no control that selects
every row at once, and do not build a shorthand that amounts to one ("the first
three", "everything in group (a)") — `schemas.md` §2 forbids a single approval
from relocating more than one pattern, and a shorthand is still one approval
underneath.

Naming a row says nothing about any other row. An id the user does not mention
stays exactly where it is — global, untouched, unpublished — and needs its own
explicit mention in a future run to move at all.

---

## 6. Write (A5)

For each id the user selected, in the order they named them:

1. If that id is already listed in `<repo>/.ani/patterns/` (the digest's
   "already in overlay" column said so, or a fresh check confirms it) — **skip
   it**, and remember it for the closing report. Never overwrite: the file
   already there is someone else's work, and replacing it needs its own
   explicit instruction the user has not given.
2. Otherwise, copy `<global-store>/patterns/<id>.md` to
   `<repo>/.ani/patterns/<id>.md` unchanged.
3. In the copy — and only in the copy — set `scope: project` in the frontmatter,
   adding the field if the original does not carry one. Touch nothing else in the
   file: not the body, not `compiled_from`, not `keywords`. The global original at
   `<global-store>/patterns/<id>.md` must read byte-identical to how it read
   before step 1.

Once every selected id has been handled, regenerate `<repo>/.ani/INDEX.md` from
the frontmatter of everything now in `<repo>/.ani/patterns/`, honoring the
60-row / 6KB budget (`references/schemas.md` §3). A skipped id changes nothing
in the overlay, so it needs no INDEX update.

The budget can be full. §3's drop rules usually free a slot, but not always — and
a pattern whose row does not fit is a file nobody will ever match: it is in the
overlay, and search never reaches it. When that happens, say so in the closing
report, by id. "Written" is not the whole truth for a row that did not fit.

---

## 7. Stop (A6)

Report two lists to the user: the files written (their paths, in the overlay)
and the ids skipped because they already existed there. Then stop.

Do not commit, branch, or push, and do not touch git config — nothing outside a
store is written by this command. Say plainly that committing the overlay
change is the user's to do; `/ani git` hands them a working tree with new files
in it, not a finished change.
