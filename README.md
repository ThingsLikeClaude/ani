# ani — Agent Negative Index

**the no-that's-not-it protocol · a resolution loop for negative feedback**

`ani` carries a double meaning:

- **Agent Negative Index** — an index of your agent's negatives: every "no, that's not it"
  moment, captured, compiled into verified patterns, and consulted before the mistake can
  repeat. As in negative indexing — `history[-1]` — it reads backward from the last failure
  in order to move forward.
- Korean **아니** ("no"), from **"아니 그게 아니라…"** ("no, that's not it…") — the sentence
  every developer eventually says to their coding agent.

ani is a file-based, agent-agnostic protocol that takes that moment seriously: it captures
the correction, compiles it into a verified success pattern, and makes the polluted context
that produced the failure safe to throw away. It is not a phrase detector for one language —
it is a universal loop in which negative feedback gets *resolved*: any language, any harness,
any kind of correction.

Open source, no server, no vendor lock-in. If your agent can read and write files, it can
speak ani.

---

## The idea in 30 seconds

A correction is the most valuable signal an agent will ever receive. In a single utterance
the user hands over three things at once — **the misread intent, the real intent, and the
fix** — delivered at the exact moment of failure, with the ground truth attached. It is a
bug report written by the only person who knows what "correct" meant.

Today every agent throws it away. The session ends, the transcript scrolls off, and the
next session makes the same mistake. That is the actual source of repeat-correction fatigue,
and no amount of context window solves it, because the problem is not memory capacity —
it is that nothing was ever written down.

ani does three things about it:

1. **Captures** the correction as a failure pattern `F` — intent, misreading, correction,
   and a verbatim excerpt, in a file, outside the context window.
2. **Compiles** `F` into a success pattern `S` under a trust ladder: quantitative evidence
   auto-compiles to a *provisional* rung that is usable immediately, and a human stamp
   raises it to *active*. The human is an auditor, not a gatekeeper.
3. **Frees the context.** Because the failure is now recorded *outside* the session, ani
   actively recommends rewinding or resetting a polluted context instead of grinding on it.
   The F file is the checkpoint; a fresh session reads one file and restarts clean.

Every `S` carries mandatory verification conditions. A pattern without a check is just
advice, and agents ignore advice.

---

## Design pillars

**P1 — Corrections are bug reports, not noise.**
An annoyed "no, that's not it" contains the misread intent, the real intent, and the repair
in one packet. Letting it evaporate with the session is the root cause of repeated
corrections. ani's first job is simply not to throw it away.

**P2 — Compile, don't just remember. The human is an auditor, not a gatekeeper.**
A pile of failure logs is search noise; like a wiki promoting a draft to an article, `F`
must be compiled before it becomes `S`. But per-item approval that *blocks usage* becomes
the bottleneck that quietly kills the system (the inbox-zero failure mode). So evidence
auto-compiles to *provisional*, usable right away, and approval raises trust rather than
unlocking use. No automatic step ever beats a user veto, and anything auto-promoted is
retired by a single counterexample.

**P3 — Verification is first-class.**
Every `S` must carry executable verification conditions: what to run or observe, what
counts as passing, what evidence gets left behind. **"Done" cannot be declared before the
verification passes.**

**P4 — Files are the protocol.**
No server, no API, no vendor. The entire system is markdown + YAML frontmatter + naming
conventions in a directory. Anything that reads and writes files — Claude Code, Codex,
Cursor, a human with an editor — can participate. Where there is git, revision history,
blame, review, and team sharing come free.

**P5 — The model is the matcher.**
Neither correction detection nor pattern lookup is regex at its core. **Semantic
recognition of a correction is the agent's job; phrase lists and hooks are hints and
reinforcement.** This is what makes ani language-independent — Korean, English, Japanese,
it fires on meaning, not on a string.

**P6 — Progressive enhancement.**
*Tier 0* is pure markdown: zero scripts, zero hooks, works in any agent that reads a skill
or instruction file. *Tier 1* adds optional platform adapters (deterministic hooks, slash
commands) where the platform allows. The core is complete without them — the moment an
adapter becomes a prerequisite, portability is dead.

**P7 — Knowledge travels with the repo.**
The default store is `.ani/` at the project root. Clone the repo and your teammates'
corrections teach your agent too. Adding or promoting a pattern becomes a PR review —
**learning becomes an object of code review.** A personal global store (`~/.ani`) stays
optional.

**P8 — Capture makes context disposable.**
Sessions with repeated corrections usually have polluted context, yet most users keep
patching on top of it out of sunk cost — "I don't want to lose everything so far." Often
the real fix is to throw the context away. ani breaks the dilemma: the essence of the
failure is already saved in an F file, so the context is now a consumable. After capture,
ani evaluates context health and recommends rewinding or restarting — and a single F file
can seed several independent fresh attempts.

---

## How it works

The correction loop. Detection is semantic (P5), so it runs with or without a hook.

```
user says something that means "no, that's not it"
        │
   [1] RESTATE  ─ state the user's real intent back, in one line.
        │         At most one clarifying question. This comes before anything else.
        │
   [2] SEARCH   ─ scan .ani/INDEX.md, open only the candidate S files.
        │         ├─ active S hit      → apply its action + verification, cite the ID
        │         │                       re-corrected after applying?
        │         │                       → record a counterexample F, demote S to review-needed
        │         ├─ provisional S hit → ranked below active; MUST be disclosed as provisional
        │         │                       re-corrected after applying? → S retired immediately
        │         └─ no hit            → continue
        │
   [3] FIX      ─ actually carry out the correction. Recording never blocks the work.
        │
   [4] CAPTURE  ─ write .ani/patterns/F-<date>-<rand8>.md, refresh INDEX (+ commit if git).
        │
   [5] TRIAGE   ─ rate context health (P8), then recommend — advice only, user decides:
        │         ├─ first correction, simple misread  → continue in this session (default)
        │         ├─ second correction on the same item → recommend a rewind
        │         └─ repeated failure / long, polluted session → recommend a reset:
        │             "F-<id> recorded. Start a new session, read only that file, and retry."
        │
   compile ─┬─ automatic: evidence score E ≥ 5 → provisional S (usable now, disclosed)
            └─ manual:    /ani ok <F-id>       → active S
            → either way, write S with situation / action / verification / counter-examples
            → close F as compiled, keep provenance in compiled_from
```

There is also a proactive path: because `INDEX.md` is budgeted to stay in context (60 lines
/ 6KB), the agent compares each *new* request against every pattern summary before it acts.
Summaries are written in "use when …" form, the same matching principle that makes an agent
pick the right skill. The best correction is the one the user never has to make.

### The trust ladder

| Rung | Entered by | How it is used | Left by |
| --- | --- | --- | --- |
| **provisional** | automatically, when evidence score `E ≥ 5` | usable immediately; ranked below active; **must be disclosed** as provisional and cited by ID | one counterexample → retired, immediately, no deliberation (no human ever vouched for it) |
| **active** | explicit human approval (`/ani ok`), or promotion of a provisional that survived 2 separate sessions | applied first, cited by ID | a counterexample → review-needed |
| **review-needed** | a counterexample F was recorded against an active pattern | **excluded from search** — a wrong manual must not be re-applied | re-approval → active, or discard → retired |
| **retired** | demotion or discard | never applied | stays as history |

`F` runs a parallel machine: `captured → compiled` (automatic or manual), or
`captured → archived` when tidying up. Every state has an exit — there are no dead states.

### The evidence score E

Only the signals below are counted. Threshold `T` defaults to 5 and is configurable.

| Signal, observed in-session | Score | Kind |
| --- | --- | --- |
| Explicit positive acknowledgement ("that's it", "좋아") | +2 | sentiment — politeness can be a false positive, never sufficient alone |
| Objective verification passed (the draft check was actually run) | +2 | behavioral |
| No re-correction on the same topic through end of session | +1 | behavioral — silence is weak evidence |
| Recurrence: the same class of pattern seen again (keyword overlap, ≥2 times) | +2 | repetition |
| Structural lint: every required field of the S draft is concrete | prerequisite | an eligibility gate, not points |
| A re-correction on the same topic | instant disqualification | this round is void |

**The cushion rule.** In a mixed utterance like *"좋은데, but change X"* the scoring unit is
the **per-topic round**, not the utterance: if the correction targets the *same* topic, the
round is disqualified and the "좋은데" scores zero — behavior beats sentiment, and a
politeness softener is not an endorsement; if it targets a *different* aspect, the original
round keeps its +2 and the new demand opens its own round. When it is ambiguous, rule it a
correction. The asymmetry is deliberate: a wrong compile (a polluted store) costs more than
a delayed one.

These signals are approximations, and ani says so: silence is not satisfaction and "thanks"
may be manners. That is exactly why behavioral signals outweigh sentiment ones and why
**automation is capped at the provisional rung.** Free-form vibes ("seemed happy") score
nothing.

---

## Why this is safe: closing the verification loop

The obvious objection to any self-learning system is *who verifies the verifier* — a wrong
pattern that verifies itself would silently propagate. ani's answer has four layers.

1. **Verification is externalized.** It is not the model's self-assessment. Every check
   names `method / target / expected / evidence / on_failure`, which forcibly converts
   "looks right to me" into "I ran X, observed Y, and left Z behind."
2. **Evidence must be fresh tool output.** Only outputs, file paths, and timestamps from
   tool calls actually made *this turn* count. Saying "I checked" in prose is not evidence.
   Tool output is rendered by the harness, so it is an anchor the model cannot forge.
3. **The correction detector itself is the outermost regression loop.** If verification is
   bypassed and a wrong result ships, that failure surfaces as the user's next correction —
   and detecting corrections is precisely what ani does. The result is a counterexample F
   and a demotion. **The verification loop does not need to be perfect; it only needs to be
   caught when it is wrong.** In this system a failure cannot structurally slip past the
   detector, which is why a wrong pattern cannot fail silently.
4. **Checks are born from failures.** Compilation always asks: *"which check would have
   caught this misreading?"* The answer becomes the verification condition. These are not
   generic checklists but regression tests derived from a real incident — the TDD principle
   of one test per bug, applied to intent.

---

## The store

```
<project>/.ani/
├── INDEX.md                      # one line per pattern:
│                                 # | id | status | scope | keywords | summary | updated |
├── patterns/
│   ├── F-20260828-a1b2c3d4.md    # failure pattern — F-<date>-<random8>
│   └── S-dark-mode-tokens.md     # success pattern — S-<slug>
└── config.md                     # optional: extra trigger phrases, language, budget overrides
```

Four conventions do the work that a database would otherwise do:

- **INDEX.md is a regenerable cache, not the source of truth.** The frontmatter in each
  pattern file is normative. If the INDEX disagrees with the frontmatter, the frontmatter
  wins and the agent regenerates the INDEX on the spot. Concurrent sessions self-heal.
- **Filenames avoid collisions structurally.** The `random8` suffix on F files means two
  sessions writing at once cannot land on the same path.
- **git history is the wiki revision history.** Blame, diff, and revert come free; teams
  share by cloning, and adding or promoting a pattern is reviewed as a PR. Without git
  everything still works — you just lose the history, an explicit trade-off.
- **The INDEX has a budget** (60 lines / 6KB) so that the whole catalog fits in context by
  design. That budget is what makes proactive matching free.

The normative schema for `F` and `S` frontmatter and sections lives in
[`skills/ani/references/schemas.md`](skills/ani/references/schemas.md). Field names,
statuses, and headings are English; values may be in any language.

---

## Install

### 1. Claude Code plugin (primary)

Install from the plugin marketplace with `/plugin`. Skills (Tier 0), hooks (Tier 1), and the
`/ani` commands are activated together in a single step — the same distribution model as
superpowers.

### 2. Copy the skill

For Claude-family environments without the plugin system, copy `skills/ani/` into your
agent's skills directory. Tier 0 is pure markdown and complete on its own; you lose only
the deterministic hook and the slash commands.

### 3. Paste the AGENTS.md snippet

For agents with no skill system at all (Codex and friends), paste the ready-made block from
[`skills/ani/references/adapters/agents-md.md`](skills/ani/references/adapters/agents-md.md)
into `AGENTS.md` or your system prompt. For anything else that can read and write files,
see [`generic.md`](skills/ani/references/adapters/generic.md).

**Day one is not an empty store.** Run `/ani bootstrap [--days N]` to mine your existing
Claude Code transcripts for past correction moments, cluster them, score them in hindsight,
and approve the candidates in one batch — so you begin with dozens of patterns instead of
zero. See [`bootstrap.md`](skills/ani/references/adapters/bootstrap.md) for the full flow.

---

## FAQ

**Why no embeddings, no vector database?**
P4 and P5. The store is files so that any agent — and any human — can participate without a
runtime, and the matcher is the model, which is already better at "is this request like that
past failure?" than cosine similarity over chunks. The INDEX is budgeted to fit in context
*by design*, so retrieval is a read, not an infrastructure problem. If your store outgrows
the budget, the answer is merging and retiring patterns, not adding a database.

**Doesn't it automatically learn wrong things?**
It can propose wrong things; it cannot silently keep them. Automation is capped at the
provisional rung, provisional application must be disclosed and cited so you can veto it on
sight, and a single counterexample retires it with no deliberation. An active pattern that
draws a counterexample drops to review-needed and is excluded from search until re-approved.
And because a wrong pattern's failure shows up as your next correction, the detector catches
it by construction.

**Does it work outside English?**
Yes — detection is semantics-first (P5), so it fires on the meaning of "you misunderstood me"
in any language. `references/triggers.md` carries per-language phrase hints (ko/en/ja/zh/…)
as reinforcement, and `config.md` lets a project add its own. Field names and statuses are
English; the values you write can be in any language.

**What about Cursor, Codex, my own harness?**
Tier 0 already works anywhere a skill or instruction file is read, and `generic.md` is the
minimal convention for anything else. Platform adapters live in
`skills/ani/references/adapters/` — contributions for other harnesses are welcome,
especially transcript formats for `bootstrap`.

---

## Status

v0.1.0 — spec-driven and early. The normative schema is
[`skills/ani/references/schemas.md`](skills/ani/references/schemas.md); the core protocol is
`skills/ani/SKILL.md`. Issues and adapter contributions welcome.

MIT licensed.

---

## 한국어 소개

**ani**는 한국어 *아니*에서 왔다. "아니 그게 아니라…" — 코딩 에이전트를 쓰는 사람이라면
누구나 하게 되는 그 말이다.

교정은 에이전트가 받을 수 있는 가장 값진 신호다. 한 문장 안에 오해된 의도, 진짜 의도,
고치는 방법이 실패의 현장에서 정답과 함께 배달된다. 그런데 오늘날 모든 에이전트는
세션이 끝나면 이걸 버린다. 반복 교정 피로의 진짜 원인은 컨텍스트 크기가 아니라,
아무것도 기록되지 않는다는 사실이다.

ani는 이 순간을 실패패턴 `F` 파일로 기록하고, 신뢰 사다리를 거쳐 검증 조건이 필수인
성공패턴 `S`로 컴파일한다. 증거 점수 E가 임계값(기본 5)에 닿으면 **잠정(provisional)**
등급으로 자동 컴파일되어 즉시 쓸 수 있고, 사람의 승인은 사용을 여는 열쇠가 아니라
신뢰 등급을 올리는 도장이다 — 사람은 게이트키퍼가 아니라 감사자다. 잠정 패턴은 적용할
때 반드시 "잠정"임을 고지하며, 반례가 한 번 나오면 심의 없이 즉시 퇴역한다.

검증 조건은 일급 시민이다. 모든 S는 method/target/expected/evidence/on_failure를 명시한
실행 가능한 체크를 가지며, 증거로는 이번 턴에 실제로 실행한 도구 출력만 인정한다.
안전성의 최종 근거는 자기 교정 루프다 — 잘못된 패턴의 실패는 조용히 쌓이지 않고
사용자의 다음 교정으로 나타나며, 그 교정을 감지하는 것이 바로 ani다.

그리고 실패가 이미 컨텍스트 **밖에** 기록됐으므로, 오염된 컨텍스트는 이제 버려도 되는
소모품이다. ani는 교정을 포착한 뒤 컨텍스트 건강도를 평가해 리와인드나 초기화를 능동적으로
권고한다(권고일 뿐, 결정은 사용자 몫). 새 세션은 F 파일 하나만 읽고 깨끗하게 재출발한다.

서버도 DB도 없다. 전체 시스템이 프로젝트 루트 `.ani/` 안의 마크다운과 frontmatter이고,
INDEX는 재생성 가능한 캐시, 정본은 각 패턴 파일의 frontmatter다. git이 있으면 개정 이력과
팀 공유(clone/PR)가 공짜로 따라온다. 설치는 세 갈래 — Claude Code 플러그인(1차),
`skills/ani/` 복사, AGENTS.md 스니펫 붙여넣기. `/ani bootstrap`으로 기존 대화 기록을
전수조사하면 첫날부터 빈 저장소가 아니다.
