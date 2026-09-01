---
# Copy to <store>/patterns/F-<YYYYMMDD>-<rand8>.md — the global store (~/.ani) by
# default, the project overlay (<repo>/.ani) for repo-specific facts. Then fill in
# and delete every comment line. Field spec: skills/ani/references/schemas.md
id: F-YYYYMMDD-rand8er        # must equal the filename without .md
status: captured              # captured | compiled | archived
date: YYYY-MM-DD              # from the `date` command, never from memory
project: <owner/repo>         # optional — `owner/repo` from the `origin` remote when
                              # there is one, else the repo root's directory name;
                              # omit rather than guess
session: <harness-session-ref>  # optional — the Excerpt must stand alone without it
trigger_quote: "<the user's correction, verbatim, in their language>"
keywords: [<domain>, <artifact>, <situation>]   # 3-6 lowercase tokens
recurrence: 0                 # optional, advisory: times this class came back.
                              # Increment the EXISTING F instead of writing a
                              # duplicate; captured INDEX rows sort by it, desc.
                              # Staying at 0 forever is a correct outcome.
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
