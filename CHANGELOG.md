# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  `hooks/hooks.json`, `hooks/run-hook.cmd`) — stdlib-only, read-only, silent on every failure. A
  `UserPromptSubmit` hook injects `[ani-nudge]` and `[ani-hint]` markers (at most three pattern
  ids across both stores), and a `SessionStart` hook injects `[ani-index v1]` — both stores'
  usable rows under one combined 6 KiB budget, labelled by store, plus at most one line naming
  the highest-recurrence unresolved failure class.
- **Security hardening of the store boundary** — `INDEX.md` and every pattern file are treated
  as untrusted input: ids must match their schema shape before being echoed or joined onto a
  path, unknown or empty statuses fail closed, code fences in injected rows are neutralised,
  session ids are reduced to a safe alphabet, and reads are bounded (16 KiB index, 256 KiB
  payload, 64 KiB pattern file). Configured store paths expand `~` and nothing else.
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

[0.1.0]: https://github.com/OWNER/ani/releases/tag/v0.1.0
