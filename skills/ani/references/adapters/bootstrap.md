# Adapter: bootstrap (cold start from past sessions)

A new `.ani/` store is empty, and an empty store teaches nothing. But the user has already
corrected their agent hundreds of times — those moments are sitting in old session
transcripts on disk. `/ani bootstrap` mines them so day one starts with patterns instead of
zero.

This is a **Tier 1** adapter: optional, platform-specific, and never a precondition for the
core protocol. Without it ani still works; it just starts cold.

---

## 1. The script is a dumb miner

`scripts/ani_bootstrap.py` (stdlib only, offline, read-only) does exactly four things:

1. reads `<claude-dir>/projects/<slug>/*.jsonl` line by line, defensively;
2. flags user turns containing a correction phrase from `references/triggers.md`;
3. clusters those moments by keyword overlap (Jaccard ≥ 0.3);
4. prints a markdown digest.

It does **not** judge, decide, or write. Every number it emits is advisory input. The
semantic work — is this really a correction of the *agent*, what was the intent, what check
would have caught it — is the agent's, per P5. The script exists because grepping 400 JSONL
files by hand burns context for no insight, not because keyword matching is the matcher.

Consequence: the miner's recall is a floor, not a ceiling. A correction phrased in words no
hint list contains is still a real correction — it simply will not appear in the digest.
Never report the digest as a complete inventory of past failures.

---

## 2. Running it

```bash
python scripts/ani_bootstrap.py [--claude-dir PATH] [--project SLUG] [--days N] [--out FILE]
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--claude-dir` | `~/.claude` | Harness config dir holding `projects/<slug>/*.jsonl`. |
| `--project` | *(all)* | Substring filter on the project slug. Use it to bootstrap one repo. |
| `--days` | `90` | Only entries newer than N days. `0` disables the window. Entries with no timestamp are always kept. |
| `--out` | *(stdout)* | Write the digest to a file (UTF-8, no BOM, LF) instead of stdout. |

Exit code is `0` whenever the script ran, including "found nothing" and "directory does not
exist". A missing transcript store is a normal outcome, not an error.

For a first sweep of the current repo:

```bash
python scripts/ani_bootstrap.py --project <your-repo-slug> --days 180 --out /tmp/ani-digest.md
```

Prefer `--out` over stdout for large sweeps: read the file in slices instead of dropping the
whole digest into context at once.

---

## 3. The flow

**Step 1 — Run the script.** Pick `--days` with the user. A wider window finds more but takes
longer to review; 90–180 days is a reasonable first pass.

**Step 2 — Read the digest.** Each cluster is one candidate failure pattern. Discard clusters
that are not agent corrections at all: quotations, jokes, the user correcting *themselves*, or
a phrase hint firing inside unrelated prose. This filtering is the reason a model reads the
digest instead of a script writing files directly.

**Step 3 — Score the evidence.** The digest's `retro-E hint` counts only the two signals the
script can see in hindsight:

| Signal | Score |
| --- | --- |
| A positive acknowledgement appears in a later user turn | `+2` |
| No re-correction within the next 10 user turns of that session | `+1` |

The cluster line reports the **maximum across its members**. The agent then adds the
repetition signal from design §3.3.1 itself:

| Signal | Score |
| --- | --- |
| Cluster has 2 or more members (same failure recurred) | `+2` |

So `E = retro-E hint + repetition bonus`, and the ceiling is `5` — which is exactly the
default threshold `T` (`evidence_threshold` in `.ani/config.md`). A cluster reaches `T` only
when the user acknowledged the fix, never re-corrected it, *and* the same failure happened
more than once. That is deliberately hard.

**Step 4 — Draft F files for every surviving cluster.** One `F-<YYYYMMDD>-<rand8>.md` per
cluster, `status: captured`, per `references/schemas.md` §1. Take `<YYYYMMDD>` from the `date`
command. Use the verbatim quote for `trigger_quote` and build `## Excerpt` from the correction
quote plus the assistant context the digest carries — the excerpt must stand alone, because
the transcript it came from may be deleted tomorrow.

**Step 5 — Draft provisional S files for clusters reaching `E >= T`.** Per
`references/schemas.md` §2: `status: provisional`, `scope: project`, `compiled_from` pointing
at the F from step 4, `summary` in use-when form. Every `## Verification` item carries all
five fields. Derive the verification from the failure — "what check would have caught this
misreading?" — not from a generic checklist.

**Never write `scope: global` from a bootstrap sweep.** `schemas.md` §2 makes `global` a
manual, per-pattern promotion, and a bulk approval is the opposite of that — a user ticking
twenty rows is approving twenty patterns for *this project*, not granting them repo-wide
reach. Every S this flow writes is `scope: project`, without exception.

**Step 6 — Present one digest table and stop.**

```markdown
| # | correction (verbatim) | members | E | proposed | approve? |
| --- | --- | --- | --- | --- | --- |
| 1 | 아니 그게 아니라 배경색만 바꾸라고 | 3 | 5 | S-dark-mode-tokens (provisional) | |
| 2 | no, that's not what I asked — only the header | 1 | 1 | F only (captured) | |
```

**Step 7 — Write only what the user approves.** Batch approval is the whole point: the user
scans one table and says "1, 3, 4" or "all except 2". Approved S drafts are written `active`
(a human approved them) and still `scope: project` — approval raises the trust rung, never the
scope. Unapproved ones stay as `captured` F files — evidence kept, no pattern claimed.
Rejected clusters are dropped entirely.

**Step 8 — Regenerate `.ani/INDEX.md`** from the frontmatter of everything written, honouring
the 60-row / 6KB budget (`schemas.md` §3). Commit if the project uses git.

Nothing is written to `.ani/` before step 7. Bootstrap is a proposal, not an import.

---

## 4. Why batch approval

Per-item approval is the failure mode ani is built to avoid (design P2, §3.3.1). A cold-start
sweep can surface dozens of candidates at once; asking for dozens of individual yes/no
decisions guarantees the user abandons it halfway and the store is left in a half-imported
state. One table, one decision, one write.

The same asymmetry as everywhere else applies: a wrong pattern in the store is more expensive
than a missing one. When a cluster is ambiguous, draft the F and skip the S.

---

## 5. Platform notes

**Claude Code** is the only harness this adapter covers today.

- Transcripts: `~/.claude/projects/<project-slug>/*.jsonl`, one JSON object per line
  (Windows: `C:\Users\<you>\.claude\projects\<project-slug>\*.jsonl`).
- The slug is the project path with separators replaced, so `--project` matching is a plain
  substring test against the directory name.
- The miner reads user-authored prose only. It skips `isSidechain: true` entries (subagent
  transcripts), `system`/`summary` entries, and content blocks that are not `type: "text"` —
  so tool calls and tool results never masquerade as user speech.
- Malformed lines are counted and skipped. Transcripts are appended to live and can be
  truncated mid-write; a partial last line must never abort a sweep.

**Other harnesses.** The flow in §3 is format-independent; only the scanner is not. Adding a
harness means contributing a scanner that yields the same shape — ordered
`(role, text, timestamp, session id, line number)` tuples — and everything downstream is
reused. Contributions welcome; open an issue with a sample transcript format.

**Windows.** The script writes UTF-8 bytes directly to stdout rather than through the console
codec, so Korean and other non-Latin text survives on `cp949`/`cp1252` consoles. When piping
to a file, prefer `--out` over shell redirection for the same reason.

---

## 6. Privacy

The script reads local transcript files and nothing else. No network calls, no telemetry, no
model invocation, stdlib only. It never writes to the transcript store and never writes to
`.ani/` — its only output is the digest, to stdout or to the `--out` path you name.

Two things the *agent* must respect, since the digest lands in context and then in files:

- Transcripts contain whatever the user pasted into past sessions, including secrets. Do not
  copy tokens, keys, credentials, or personal data into an F file. Excerpts should carry the
  misunderstanding, not the payload — redact and note the redaction.
- `.ani/` is usually committed and shared with the team (P7). Treat a bootstrap sweep of a
  personal machine as a proposal for a *shared* repo, and say so when presenting the table.

---

## 7. Known limits

- **Phrase hints, not semantics.** The miner finds corrections that use a listed phrase.
  Everything else is invisible to it. Extend `references/triggers.md` and re-run to widen
  recall.
- **Korean agglutination.** Tokens are normalised by stripping common single-character
  particles (`배경색만` → `배경색`) so the same noun clusters across turns. It is a heuristic;
  it occasionally trims a syllable that was not a particle. Keywords in the digest are
  suggestions for the agent to refine, never final `keywords` values.
- **Clustering is lexical.** Two corrections about the same underlying mistake in different
  vocabulary land in different clusters. The agent should merge them when reading the digest —
  and merging raises the repetition bonus, so it matters.
- **Hindsight is not consent.** A past session ending without complaint is weak evidence, the
  same `+1` it is worth anywhere else in ani. It never justifies writing an `active` pattern
  without the user's approval.

---

## 8. Tests

`tests/test_bootstrap.py` (stdlib `unittest`, no pytest) drives the script through
`subprocess` against `tests/fixtures/sample_transcript.jsonl` copied into a temp
`--claude-dir`. It never reads a real transcript store.

```bash
python -m unittest discover -s tests -p "test_bootstrap.py" -v
```
