# Adapter: Claude Code (Tier 1)

Optional. The ani core protocol (Tier 0) is pure markdown and works in Claude
Code with nothing installed but the skill. This adapter adds a deterministic,
zero-LLM-call detector on top: a `UserPromptSubmit` hook that injects
structured markers into the turn's context.

The hook is a hint generator, not the protocol. It never decides anything —
it only tells the skill "look here". If it is missing, misconfigured, or
crashes, semantic recognition (P5) still fires and every ani step still works.

## 1. What the hook does

`hooks/ani_trigger.py` reads the Claude Code hook payload from stdin (it
expects `prompt`, `session_id`, `cwd`, and tolerates all of them being absent)
and runs two independent detections.

**a. Correction detection.** The prompt is matched against a deliberately
conservative subset of `references/triggers.md` — the canonical, high-precision
phrases in ko/en/ja/zh, kept as the `CORRECTION_PHRASES` constant at the top of
the script. First match wins and names the marker. The hook does not read
`triggers_extra` from `.ani/config.md`, and it carries none of the softer
phrasings; those live with the model, which is the real matcher.

**b. Proactive hint.** The hook locates `.ani/INDEX.md` — under
`CLAUDE_PROJECT_DIR` if set, else the payload's `cwd`, else the process cwd,
walking up to 5 parent directories — parses the cache table's `id`, `status`,
and `keywords` columns, and intersects the keywords with the prompt.
Matching is substring-based on the lowercased prompt, plus a comparison
against prompt tokens with common Korean particles stripped
(을/를/이/가/은/는/에/에서/으로/로/과/와/도/만), so INDEX keyword `배경색`
still fires on the prompt `배경색을 바꿔줘`. Only `active` and `provisional`
S-patterns are searchable (`review-needed` and `retired` are excluded, per the
state machine); `active` ids are listed first, and at most 3 ids are emitted.

Output, when and only when something matched, is a single line of JSON on
stdout:

```json
{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"<context>"}}
```

`<context>` contains one or both of these blocks, nudge first:

```
[ani-nudge v1] session=<session_id> prompt_sha=<sha8> pattern=<matched-phrase-slug>
Correction signal detected — if this is a genuine correction of the assistant's previous work, follow the ani skill protocol.
```

```
[ani-hint v1] patterns=<S-id,S-id>
These .ani success patterns may apply to this request — consult them before acting.
```

- `session_id` — verbatim from the payload, whitespace removed; `unknown` when
  the payload had none.
- `sha8` — first 8 hex characters of `sha256(prompt.encode("utf-8"))`.
- `pattern` — a stable ASCII slug for the phrase that matched, e.g.
  `ko-ani-geuge-anira`, `en-i-meant`, `ja-souiu-imi-janai`,
  `zh-bushi-zhege-yisi`.

When nothing matches, the hook prints nothing at all.

## 2. How the skill must validate a nudge

A marker is evidence about **one specific turn**. Stale markers are the known
failure mode of hook-based detection (a marker from an earlier prompt leaking
into a later turn's context and triggering a phantom capture).

Before acting on `[ani-nudge v1]`, verify **both**:

1. `session=<id>` equals the current session id.
2. `prompt_sha=<sha8>` equals the first 8 hex characters of
   `sha256(<the user's current prompt>.encode("utf-8"))`.

If either check fails, ignore the marker entirely — do not capture, do not
mention it. If both pass, the marker still only says "a canonical phrase was
present". It is not a verdict:

- The phrase may be a quote, a joke, or a report about someone else's
  conversation. Step 1 RESTATE resolves this; if it turns out not to be a
  correction of the assistant's own previous work, stop silently.
- Mixed utterances ("좋은데 근데 그게 아니라 이쪽이야") always nudge. The hook
  deliberately does not filter — separating praise from correction and
  assigning it to the right topic round is the model's job (§3.3.1).
- Absence of a marker means nothing. Most corrections use no canonical phrase.
  Semantic recognition remains primary.

`[ani-hint v1]` carries no session/hash binding because it is not a claim
about the turn's meaning — it is a search result. Treat the listed ids as
candidates to open in Step 2 (or before acting at all, on the proactive path),
subject to the usual priority: current user request > safety/permissions >
active S > provisional S. Never apply a hinted pattern without reading its
file, and always cite the id — noting explicitly when a pattern is provisional.

## 3. Install

### Plugin (recommended)

The plugin bundles the skill (Tier 0) and this hook (Tier 1) together.

```
/plugin marketplace add <owner>/ani
/plugin install ani
```

For a local checkout:

```
/plugin marketplace add D:\path\to\ani
/plugin install ani
```

`${CLAUDE_PLUGIN_ROOT}` is resolved by Claude Code, so no paths need editing.
Verify with `/hooks` — `UserPromptSubmit` should list the ani command — and
confirm the skill is loadable with `/skills`.

The bundled command is `python "${CLAUDE_PLUGIN_ROOT}/hooks/ani_trigger.py"`.
On a system where `python` is absent or still points at Python 2 (many Linux
and macOS setups), install manually instead and put `python3` in the command.

### Manual (no plugin system)

1. Copy `hooks/ani_trigger.py` anywhere stable, e.g.
   `~/.claude/ani/ani_trigger.py`.
2. Copy `skills/ani/` into `~/.claude/skills/ani/` (user scope) or
   `<project>/.claude/skills/ani/` (project scope).
3. Register the hook in `~/.claude/settings.json` (or
   `<project>/.claude/settings.json`):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python \"$HOME/.claude/ani/ani_trigger.py\"",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

On Windows, use the absolute path with escaped backslashes and `python` (or
`py -3`) as available on PATH:

```json
"command": "python \"C:\\Users\\<you>\\.claude\\ani\\ani_trigger.py\""
```

Restart the session (or `/hooks` → reload) for the change to take effect.
Requirements: Python 3.8+ on PATH. No third-party packages — stdlib only.

## 4. Triage commands on this platform (Step 5)

Step 5 TRIAGE is a recommendation, never an action taken on the user's behalf.
On Claude Code the escalation ladder is:

| Situation | Recommendation |
| --- | --- |
| First correction, simple misread | Stay in this session (default). |
| Second correction on the same thing, loop forming | Suggest `/rewind` to a checkpoint before the polluted exchange, then retry with the correction restated. |
| Repeated failures, long session, heavy pollution | Suggest a fresh start: `/clear` (same window) or a new session, then "read only `.ani/patterns/F-<id>.md` and start over from it". |

The F file is the checkpoint that makes the context disposable (P8): intent,
misreading, correction, and a self-contained verbatim excerpt are already
outside the context window. Capture first, then recommend. The same F file can
seed several independent fresh attempts.

Because `/rewind` can roll back file changes as well as conversation, say which
mode is meant and let the user choose. Never run these for the user.

## 5. Failure behavior

The hook is designed to fail silently and harmlessly.

- Any exception → nothing on stdout, a one-line note on stderr, exit 0.
- Malformed, empty, or non-JSON stdin → no output, exit 0.
- Missing keys in the payload → no crash; detection degrades to what is
  available (no `.ani` found means correction detection alone).
- Encoding is pinned to UTF-8 on every side, because the correction phrases
  are mostly non-ASCII: stdin is decoded from raw bytes as UTF-8 (a text-mode
  read would raise on the first Korean character under a cp949 locale, and the
  hook would go silent exactly when it is needed), `stdout`/`stderr` are
  reconfigured to UTF-8, and the JSON falls back to ASCII escaping if the
  stream still refuses the bytes. A UTF-8 BOM on the payload is tolerated.
- A malformed or unreadable `.ani/INDEX.md` costs the hint only — the nudge is
  still emitted.
- Nothing detected → no output at all, so the hook stays invisible in normal
  use.
- Hook not installed, Python missing, timeout exceeded → Claude Code drops the
  (empty) output and the turn proceeds. The skill's semantic detection is
  unaffected; you lose the deterministic assist, not the protocol.

Debug it directly, without a session:

```bash
echo '{"prompt":"아니 그게 아니라 배경색만 바꾸라고","session_id":"abc","cwd":"."}' | python hooks/ani_trigger.py
```

Regression tests live in `tests/test_ani_trigger.py`
(`python -m unittest discover tests`, stdlib only).

## 6. Transcript location (for `/ani bootstrap`)

Claude Code stores session transcripts as JSONL under
`~/.claude/projects/<project-slug>/*.jsonl` (Windows:
`C:\Users\<you>\.claude\projects\<project-slug>\*.jsonl`), where the slug is
the project path with separators replaced by dashes. This is the input the
cold-start bootstrap sweep reads to mine past corrections. Read-only —
bootstrap never modifies transcripts.
