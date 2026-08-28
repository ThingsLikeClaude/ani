---
# Copy to .ani/patterns/F-<YYYYMMDD>-<rand8>.md, then fill in and delete every
# comment line. Field spec: skills/ani/references/schemas.md
id: F-YYYYMMDD-rand8er        # must equal the filename without .md
status: captured              # captured | compiled | archived
date: YYYY-MM-DD              # from the `date` command, never from memory
project: <project-slug>       # optional — omit rather than guess
session: <harness-session-ref>  # optional — the Excerpt must stand alone without it
trigger_quote: "<the user's correction, verbatim, in their language>"
keywords: [<domain>, <artifact>, <situation>]   # 3-6 lowercase tokens
---

## Intent

<!-- What the user actually wanted. 1-2 sentences, stated positively. -->

## Misreading

<!-- What the agent did instead, AND why it went wrong — the causal step
     (which word was read how), not just the wrong output. -->

## Correction

<!-- What actually fixed it. Concrete: files, commands, values. -->

## Excerpt

<!-- REQUIRED. Self-contained verbatim exchange: a reader with no transcript
     access must be able to reconstruct the failure from this block alone.
     Elide with … but never paraphrase. -->

> User: <verbatim>
> Agent: <verbatim>
> User: <the correction, verbatim>
> Agent: <the restatement>

## Context

<!-- Optional, 3 lines MAX. Only context that changes how the failure reads
     (framework, constraint, prior turn). Not a session summary. -->
