# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-08-31

Two defects found by the first post-update verification session (issues #4, #5).

### Fixed

- **`/ani doctor` no longer reports an orphaned plugin cache** (#4). After a plugin
  update the old version directory stays in the cache with an `.orphaned_at` marker, and
  `find_installed_plugin()` returned the first manifest in walk order — alphabetically the
  stale one. It now ranks every match: live (no `.orphaned_at`) beats orphaned, then the
  numerically highest version wins, and a found orphan still beats "not found". The OK line
  now also names the winning version (`... (version 0.1.3)`), sourced from the manifest and
  sanitised before echoing. On the real cache that produced the report, the doctor moved
  from `found at .../0.1.0` to `found at .../0.1.2 (version 0.1.2)`.

### Changed

- **Docs: the install root is resolved, not guessed** (#5). The v0.1.1 "two directories
  above SKILL.md" wording still let a session run a bare relative
  `python scripts/ani_doctor.py` into `[Errno 2]`. SKILL.md References now carries the
  recipe — take the harness's `Base directory for this skill:` line, strip the trailing
  `skills/ani`, run by absolute path — and names the concrete cache shape
  `~/.claude/plugins/cache/<marketplace>/ani/<version>/` (`${CLAUDE_PLUGIN_ROOT}` in hook
  context). The doctor subcommand row and `adapters/claude-code.md` point at the same
  recipe.

## [0.1.2] - 2026-08-31

The three miner defects found by the first real-world sweep, fixed (issues #1, #2, #3).

### Fixed

- **The file cap trims the oldest history, not the alphabet** (#1). `iter_transcripts` now
  visits files newest-first by mtime, and with `--days N` files last modified before the
  window are skipped up front (`Files skipped outside window` in the Scan block). Rerunning
  the originally broken sweep on the same store went from "2,000 files scanned, 12,428
  skipped over cap, recent projects never opened" to "342 recent files scanned, 0 over cap".
- **Resumed sessions can no longer forge the repetition bonus** (#2). A session resumed under
  another project slug mirrors its transcript prefix byte-for-byte; moments are now
  deduplicated before clustering, keyed on entry uuid (fallback: timestamp + line + quote)
  and counted as `Duplicate moments removed`.
- **Machine-injected user turns are no longer mined** (#3). Slash-command expansions (which
  embed skill documents — ani's own trigger list included), task notifications and
  compaction preambles are skipped and counted as `Machine-injected user turns skipped`. On
  the real store this removed 431 injected turns and cut the sweep from 25 candidates in 16
  clusters to 6 real moments in 5 clusters.

### Changed

- **Bootstrap digest format spec** (`adapters/bootstrap.md` step 6): the approval request is
  now a specified decision document — approval table first, markdown tables only,
  self-contained rows, methodology demoted to one line + digest pointer, decision tracks
  numbered. Learned from the first real sweep, whose report buried the decision mid-page.
- Bootstrap adapter notes describe the new scanner behaviour (newest-first ordering,
  injected-turn skipping, resumed-session dedupe); the interim known-limit entries for the
  three defects are gone. Miner `__version__` is 1.1.0.

## [0.1.1] - 2026-08-31

Documentation release — nothing in the protocol or the code changed.

### Changed

- **Korean-first README.** `README.md` is now the Korean edition; English moved to
  `README.en.md`. The first audience is Korean Claude Code users.
- **Hand-designed SVG diagrams** under `docs/assets/` (ko + en) replace the default-theme
  mermaid blocks: the correction loop in one picture, the five-step loop, and an install
  self-check flow. Self-backgrounded panels, so they render identically on light and dark
  GitHub themes with no image hosting.
- **Install self-check section.** Both READMEs now say explicitly that two doctor WARNs and a
  missing `[ani-index v1]` right after install are *normal* (no store yet — no heart to beat),
  and walk the reader through verification by doing: one correction → F file → heartbeat.

### Fixed

- **Docs: `scripts/` and `templates/` located from the skill directory.** SKILL.md referenced
  `scripts/ani_doctor.py` and `templates/*.md` as if they sat beside it, but in a plugin install
  they live at the plugin root, two directories above SKILL.md. A real first-install session
  followed the documented path and found nothing. SKILL.md now defines the **install root** once
  (References section) and points every mention at it; `adapters/bootstrap.md` and
  `adapters/claude-code.md` carry the same locator. Skill-directory-only installs (no `scripts/`
  or `templates/`) are told to build files from `references/schemas.md` and skip `/ani doctor`.

## [0.1.0] - 2026-08-28

Initial release.

### Added

- **The ani protocol** (`skills/ani/SKILL.md`) — the Tier 0 core: a proactive path that consults
  recorded patterns before non-trivial work, and a five-step correction loop (RESTATE, SEARCH,
  FIX, CAPTURE, TRIAGE) that runs on semantic recognition of a correction in any language. Pure
  markdown, no scripts or hooks required.
- **Two-tier store** — a global store (`~/.ani`, the default sink, relocatable with the
  `global_store` config key) for knowledge that follows the user, plus an opt-in project overlay
  (`<repo>/.ani`) for repo-local patterns shared through git. Capture routes repo-specific facts
  to the overlay and everything ambiguous to the global store; search reads both, project first.
- **The file store and its schema** (`skills/ani/references/schemas.md`) — failure patterns
  (`F`), success patterns (`S`) with mandatory five-field verification conditions, the
  regenerable `INDEX.md` cache under a 60-row / 6KB budget, and `config.md` overrides, with a
  full worked example.
- **The trust ladder** — automatic compilation to `provisional` at evidence score `E ≥ 5`,
  human approval to `active`, demotion to `review-needed` or `retired` on a counterexample, plus
  the per-topic cushion rule for utterances that mix praise and correction.
- **Compile queue and token economy** — compilation is parasitic on the success run the fix
  already performed, never a dedicated offline re-run (`/ani resolve <F-id>` is the only
  exception, and only the user can ask for it). Unresolved failures carry an advisory
  `recurrence` count and captured `INDEX.md` rows sort by it, so the index *is* the queue; a
  class that never recurs is meant to stay `captured`.
- **Multilingual trigger hints** (`skills/ani/references/triggers.md`) for ko/en/ja/zh, as
  reinforcement for semantic detection rather than as the detector.
- **Tier 1 adapters** (`skills/ani/references/adapters/`) — Claude Code (hook installation and
  marker contract), `AGENTS.md` snippet, a generic minimal convention for any file-capable
  agent, and the bootstrap flow.
- **Claude Code hook adapters** (`hooks/ani_trigger.py`, `hooks/ani_session_start.py`,
  `hooks/hooks.json`, `hooks/run-hook.cmd`) — stdlib-only, read-only, and silent on every failure
  except the one below that must not be silent (a missing interpreter). A
  `UserPromptSubmit` hook injects `[ani-nudge]` and `[ani-hint]` markers (at most three pattern
  ids across both stores), and a `SessionStart` hook injects `[ani-index v1]` — both stores'
  usable rows under one combined 6 KiB budget, labelled by store, plus at most one line naming
  the highest-recurrence unresolved failure class.
- **Security hardening of the store boundary** — `INDEX.md` and every pattern file are treated
  as untrusted input: ids must match their schema shape before being echoed or joined onto a
  path, unknown or empty statuses fail closed, code fences in injected rows are neutralised,
  session ids are reduced to a safe alphabet, and reads are bounded (16 KiB index, 256 KiB
  payload, 64 KiB pattern file). Configured store paths expand `~` and nothing else.
- **Knowledge sources — the optional wiki bridge**
  (`skills/ani/references/adapters/knowledge-source.md`) — the `UserPromptSubmit` hint engine can
  additionally match claims compiled out of *any* wiki (Obsidian, Zettelkasten, a plain markdown
  handbook), named by `knowledge_sources` in `config.md`: comma-separated absolute paths, the
  project list then the global one, deduped, at most 4 used, with `ANI_KNOWLEDGE_SOURCES`
  replacing both lists outright. A knowledge file is the same six-column table as `INDEX.md`; a
  row is used only when its id matches `^K-[a-z0-9]+(?:-[a-z0-9]+)*$` (≤ 64 chars) and its status
  is `active`, everything else is dropped silently, and a file past a 16 KiB cap is skipped whole
  rather than truncated. `K` ids ride the existing `[ani-hint v1]` line after the `S` ids under
  the same cap of three and never displace one — priority runs current request > safety >
  project S > global S > knowledge claim. Nothing is injected at session start, and a user
  without a wiki configures nothing and sees no change: their correction store *is* their
  knowledge store.
- **Operation guarantees — no silent failure** — `[ani-index v1]` is the handshake: a session
  that never shows one means the hooks are not firing, so the skill switches to manual mode,
  reads the `INDEX.md` files itself, runs the protocol unchanged, and tells the user once.
  *Hooks are accelerators; the protocol is the guarantee.* `/ani doctor`
  (`scripts/ani_doctor.py`) checks the Python interpreter, store resolution plus a write probe,
  `INDEX.md` parse counts, knowledge-source validation, and the plugin install, printing one
  `OK` / `WARN` / `FAIL` line per check (exit `0` clean, `1` warnings, `2` failures) — and says
  outright that it cannot verify hook firing, pointing at `[ani-index v1]` in a fresh session as
  the real test. Install instructions now end at "run `/ani doctor` until all green". Finally,
  `hooks/run-hook.cmd` no longer dies quietly when no `python3`/`python`/`py` is on `PATH`: the
  session-start invocation emits a one-line manual-mode notice, while the per-prompt invocation
  stays silent so the warning cannot become noise.
- **Bootstrap miner** (`scripts/ani_bootstrap.py`) — `/ani bootstrap [--days N]` scans existing
  Claude Code transcripts offline and read-only, clusters past correction moments by keyword
  overlap, and prints a digest for bulk approval into the global store, so a new store does not
  start empty.
- **Templates** (`templates/F-template.md`, `templates/S-template.md`).
- **Tests** (`tests/`) — stdlib `unittest` coverage for both hooks (dual-store search, combined
  injection budget, recurrence surfacing, untrusted-input handling, encodings) and the bootstrap
  miner, with a sample transcript fixture. Test runs never touch a real `~/.ani`.
- **Documentation** — README, [design rationale](docs/design.md), and
  [contribution guide](CONTRIBUTING.md).

[0.1.3]: https://github.com/ThingsLikeClaude/ani/releases/tag/v0.1.3
[0.1.2]: https://github.com/ThingsLikeClaude/ani/releases/tag/v0.1.2
[0.1.1]: https://github.com/ThingsLikeClaude/ani/releases/tag/v0.1.1
[0.1.0]: https://github.com/ThingsLikeClaude/ani/releases/tag/v0.1.0
