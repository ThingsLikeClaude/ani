## What this changes

<!-- One or two sentences. -->

## Reproduction excerpt

**Which correction or failure motivated this change?** Quote the exchange if you can — the user
turn, the agent turn, and what should have happened instead. This is ani's signature field: a
change with no failure behind it is advice, and advice is what this project exists to replace.

```
User:
Agent:
```

<!-- For a pure docs or typo fix, "no failure — wording only" is a fine answer. -->

## Cross-review

Adjacent documents you read (see the table in
[CONTRIBUTING.md](../CONTRIBUTING.md#the-pairwise-cross-review-rule)) and what you checked:

<!-- e.g. "Read SKILL.md alongside the adapter — the [ani-nudge v1] marker format is
     unchanged and still consumed in Path A." -->

## Verification

How you know this works. Fresh output beats description.

- [ ] `python -m unittest discover -s tests` passes
- [ ] For an adapter: transcript attached showing a correction producing an F file in a clean
      session
- [ ] Encoding checked: UTF-8 without BOM, LF newlines
- [ ] No new dependencies, no network calls

## Anything a reviewer should watch for

<!-- Known limitations, deliberate trade-offs, follow-ups you did not do. -->
