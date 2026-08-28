---
name: Platform support (adapter request)
about: Ask for — or offer — an adapter for another agent harness
title: 'Adapter: <harness name>'
labels: adapter
assignees: ''
---

## Harness

- Name and version:
- Link to its docs:
- Are you offering to write the adapter, or requesting one?

## How does it load skills or instructions?

<!-- This is the one that matters: without it there is no Tier 0. Examples: a skills
     directory, an AGENTS.md file, a system-prompt field, a plugin manifest. Paste the
     relevant doc section or a path. -->

## Hook support

- [ ] It can run a command on every user prompt (deterministic detection is possible)
- [ ] It has some other extension point (describe below)
- [ ] No hooks — Tier 0 only

<!-- If hooks exist: what is passed to the hook, and how does its output reach the model? -->

## Session transcripts

Can `bootstrap` mine past sessions on this harness?

- Where transcripts are stored:
- Format (JSONL, SQLite, other):
- [ ] Not stored locally / not accessible

## Rewind and reset

What are the platform's equivalents of "go back before the mistake" and "start a fresh
session"? TRIAGE names these actions.

## Acceptance test

An adapter is merged once this has been demonstrated:

> In a clean session, send a correction like "아니 그게 아니라 …" (or its equivalent), and an F
> file actually appears in `.ani/patterns/`.

- [ ] Transcript attached (the correction, the reply, and the created file path)
- [ ] Not yet run — this is a request, not a submission
