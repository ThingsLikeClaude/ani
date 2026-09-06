# Correction detection — recall, one table, and the way in

Status: approved 2026-09-06, implemented 2026-09-06 on branch
`fix/correction-detection-recall`. The measurement claims in C1 were corrected
against post-implementation numbers; C5 records a defect found while building.

## Why

ani's entry point is a detector. `hooks/ani_trigger.py` reads each prompt, looks
for a correction phrase, and emits `[ani-nudge v1]` so the agent enters Path B.
`scripts/ani_bootstrap.py` runs the same idea over past transcripts. Everything
downstream — the F file, `recurrence`, the evidence score E, the compiled S —
starts there. Nothing reaches the store that the detector did not first notice.

The detector was measured on 2026-09-06 and it notices almost nothing.

### The measurement

**Ground truth.** Eleven F files in the user's global store each carry a
`trigger_quote`: the user turn that an agent, in a live session, judged to be a
correction. That is eleven known positives, labelled by the system itself.

Running `ani_trigger.detect_correction` over those eleven quotes:

| | |
| --- | --- |
| Detected | 1 |
| Missed | 10 |
| **Recall** | **9%** |

**Frequency.** Over the same five-day window, 227 transcript files, 1,585 human
prose turns (317/day):

| Signal | Turns | Rate |
| --- | --- | --- |
| Current detector (19 regexes) | 10 | 2.0/day |
| Sentence-initial `아니` | 26 | 5.2/day |
| Defect report (`안 되는데`, `작동 안`) | 24 | 4.8/day |
| Negative verdict (`슬롭`, `이상해`, `별로`, `촌스`) | 23 | 4.6/day |
| Stated recurrence (`여러번`, `또 그러`, `전에도 말했`) | 3 | 0.6/day |
| Reversal (`다시 생각`, `안 쓰게`, `없던 걸로`) | 2 | 0.4/day |

The detector fires 2/day against roughly 12/day of real correction turns.

### What the misses look like

Ten missed quotes, grouped:

```
아니 그냥 html 로 만들어서 열어                    문두 "아니" + 지시
아니 근데 ... 사용하고있는거아니었어?               문두 "아니" + 반문
아니 이거 중앙으로 바꿔줘                          문두 "아니" + 지시
아니 너가 직접 개발서버 띄워서 알려줘               문두 "아니" + 지시
(여러번 지적함, 특히 책상같은거)                    재발 명시
내가 상세페이지에서 겪었던 슬롭임                   재발 명시 + 부정판정
... AI 슬롭같아 ... 다시해봐                        부정판정 + 재작업
프런트가 안되는데?                                 결함보고
굉장히 짧고 간결하게 눌러서 써야돼                  의무형 지시
3456은 다시생각해보니까 안쓰게될거같아              번복
```

Five of eleven open with a bare sentence-initial `아니`. The current table
requires `아니` followed by a specific continuation (`그게 아니라`,
`그런 뜻이`), which this user almost never says. The single highest-value family
— a user stating outright that they have said this before — has no entry at all,
even though it is the one signal that proves recurrence without inference.

### The chain

```
recall 9%
  → the nudge fires on 2 turns/day of ~12
  → the agent often never enters Path B
  → no F is written, or a duplicate opens instead of incrementing recurrence
  → E is never computed for that class
  → nothing crosses T=5
  → F files sit `captured`               ← "쌓이기만 하고 안 굳는다"
  → the store holds 2 S after five days  ← "주입돼도 행동이 안 바뀐다"
```

The store's own numbers match: 11 F, 9 of them `captured`, 2 S, over five days.

### What this is not

Two things were suspected and measured out:

- **The context budget is not the problem.** Only S rows are injected
  (`STATUS_PRIORITY = ("active", "provisional")`). The resident cost today is
  515 bytes — 8% of the 6 KiB injection budget, about 140 tokens — with room for
  roughly 21 more S rows. F rows live in the INDEX file but never enter context.
- **The layers are not merged.** Matching already happens on demand:
  `ani_trigger` reads the INDEX from disk on every prompt and emits at most
  three ids (`MAX_HINT_PATTERNS = 3`). The corpus/index/resident separation that
  looked missing is largely already there.

## Invariants

1. **The hook nudges; the agent judges.** Widening detection buys recall, and
   precision stays where it already lives — Path B's RESTATE step, which makes
   the agent state what it thinks the correction is before writing anything. A
   nudge is never a capture.
2. **One table, two readers.** The hook and the miner detect the same thing, so
   they read the same list. Divergence is how a fix lands in one and not the
   other.
3. **Detection never blocks.** A prompt that matches nothing proceeds unchanged;
   a prompt that matches is still just a prompt with a marker appended.
4. **No new store writes.** This changes what is noticed, not what is written or
   where. F and S schemas are untouched.
5. **A widened net is measured, not assumed.** Every family added carries its
   measured rate, and the spec states the false-positive cost it accepts.

## The changes

### C1. Detection vocabulary, rebuilt from observed speech

The table is rebuilt around the five families the measurement found. Each entry
keeps a slug, as today, so a hit is attributable.

**Family A — sentence-initial `아니`.** Anchored to the start of the prompt, with
one exclusion. The rule this spec first wrote — that `아니라`, `아니면`, `아닌`,
`아니야` are ordinary Korean and must not fire — was mostly disproved by
measurement. `아니야`, `아니요` and `아니지` opened four sentences in the window
and every sampled one was a genuine correction. `아닌데`, `아닌가`, `아니었` and
`아니라` opened none, so a guard for them is untested weight in a table that is
read on every prompt. `아니면` is a conjunction proposing an alternative
(`아니면 버셀 배포할까???`) and is Family A's only exclusion. It was described
here as *the* only measured false positive; that was wrong in the same corpus.
Re-reading the 55 new-detector fires in the five-day window found a second:
Family D's `구려` matching inside `싸구려` in a pasted design document, twice —
the user saying the result must *not* look cheap, which is the opposite verdict.
That entry now carries a `(?<!싸)` guard, so the table has two exclusions and
two measured false positives, not one of each. The rule is
therefore **sentence-initial `아니`, except `아니면`** — a lookahead on word
class, not on sentence mood: ground-truth quote #5 is interrogative and a
genuine correction, so a guard keyed on `?` would have been wrong. Measured
5.2/day. The two specific phrases the old table already carried,
`아니 그게 아니라` and `아니 그런 뜻이`, keep their `ko-ani-` slugs and sort
first, so the prefix names the family rather than the bare interjection, which
takes `ko-ani-muntu`; a hit on either specific phrase is still attributable to
Family A, which is what the prefix is for.

**Family B — stated recurrence.** `여러번`, `또 그러`, `아까도`, and
`(전에도|계속) (말|얘기|지적)(했|함|하셨|하잖|씀)`. Measured 0.6/day. The rarest
family and the most
valuable: the user is saying the recurrence out loud, which is exactly what
`recurrence` exists to count. `여러번` alone is an ordinary frequency adverb —
`여러번 실행해줘` is a request, not a complaint — so it fires only when paired
with a speech verb, the same `말|얘기|지적` that `전에도`/`계속` carry. A bare
one-syllable `말|얘기|지적` does not discriminate, though: `말` is also all of
`말고` and the front of every present-tense `말하다`, so `여러 번 말고 한 번에`
and `계속 말하면서 잡아야하니?` both landed in the family — one of them a real
fire in the measured window. The saying has to have already happened, which is
how `references/triggers.md` described the family from the start; `아까도`
stays bare, since nothing measured disproves it. `왜 자꾸` and `또 그러네`,
which the old table carried loose, are complaints about repetition and so belong
here: both were re-slugged into `ko-recur-`, and the second widened to
`또 그러`.

**Family C — defect report.** `안 되는데`, `안 됨`, `작동 안 (해/함/된다/돼)`.
Measured 4.8/day. The last entry requires the verb the negation adverb negates,
because bare `작동 안` fires on 작동 followed by any word that opens with 안 —
안정성, 안내, 안전, 안심 — and `\s*` matches a newline, so the paragraph break
before an 안녕하세요 counted too. That was a defect report raised against a
question about how something operates.

**Family D — negative verdict.** `슬롭`, `이상해`, `별로야`, `촌스`, `구려`.
Measured 4.6/day. This family is the most user-specific in the list and the most
likely to need tuning for another user; it is kept because two of the eleven
ground-truth quotes are nothing but this.

**Family E — reversal.** `다시 생각`, `안 쓰게`, `없던 걸로`. Measured 0.4/day.

English and Japanese and Chinese entries are kept as they are. They were not
measured — this user's corpus is Korean — and removing unmeasured entries would
be a change with no evidence behind it.

**The false-positive budget, and how it was missed.** This spec accepted
"roughly 12 nudges/day against 317 turns/day: under 4% of turns." Both halves of
that fraction were wrong. The numerator was a prediction, not a count. The
denominator counted injected skill bodies, compaction preambles, system
reminders and tool results as user speech. Re-measured after implementation over
the same five-day window, counting only prompts the user actually typed:

| | turns/day | fires/day | % of turns |
| --- | --- | --- | --- |
| corpus | 273 | — | — |
| old detector | — | 1.4 | 0.51% |
| new detector | — | 15.8 | 5.78% |

Recall against the eleven ground-truth `trigger_quote` values went from 1/11
(9%) to 10/11 (91%). The known miss is still the bare directive
`굉장히 짧고 간결하게 눌러서 써야돼`, exactly as this spec predicted.

Per family, measured after implementation: A 6.0/day, D 5.6/day, C 2.0/day,
B 0.8/day, E 0.2/day, plus the pre-existing entries. These are attributions from
the built table — one slug per firing turn, first match wins — and not the
per-phrase probes the family rates above came from, so the two lists are not
comparable entry by entry.

Those attributions were taken while the bare interjection `^\s*아니(?!면)` sat
third in the table, ahead of `그게 아니라`, `그거 말고`, `내 말은` and all of
families B–E, so any correction the user prefixed with `아니` was counted as A
even when a sharper entry also matched. The A figure above is therefore an
upper bound and B–E lower bounds, by an amount nobody measured — 0 of the 55
fires in the window took that path, so the bias is latent rather than visible.
The bare interjection now sorts last among the Korean entries, which changes
which slug is reported and never whether anything fires.

5.78% is not under 4%, so the budget was missed. What the sample says is that
the overshoot is not noise: reading the 79 fires in the window, most are genuine
corrections. This user corrects roughly 6% of their turns. That is a fact about
the user, not a defect in the detector.

The reason a wide net stays cheap is unchanged. A false nudge costs one line of
injected text and an agent that reads it, finds nothing to correct, and moves
on. Invariant 1 is what makes that cheap. The families are ordered so the most
specific matches first, and the emitted slug says which family fired, so a family
that proves noisy in practice can be removed on evidence rather than on taste.

Two entries a tightening pass would look at first, recorded as observations and
not as changes. `ko-defect-an-doem` (`안\s*됨`, 1.6/day) fires inside long
instruction text that merely contains the phrase as a rule rather than as a
complaint about the work. `ko-verdict-chonseu` and `ko-verdict-guryeo` (1.4/day
combined) are low-volume and specific to this user's vocabulary. Neither has been
touched, and neither should be on the strength of one window.

### C2. One table, two readers

`hooks/ani_trigger.py` owns the canonical table. `scripts/ani_bootstrap.py`
imports it rather than keeping its own.

Today there are two, and they disagree:

| | Location | Matching | Entries |
| --- | --- | --- | --- |
| Hook | `ani_trigger.CORRECTION_PHRASES` | compiled regex | 19 |
| Miner | `ani_bootstrap.CORRECTION_PHRASES` | literal substring, language-aware | 14 |

The hook's form wins: sentence-initial anchoring (Family A) needs a regex, and a
literal substring table cannot express it. The miner already imports nothing from
`hooks/`, but the precedent exists — `scripts/ani_doctor.py` imports
`ani_trigger` — so the import direction is established.

The miner runs those patterns over the raw turn, not over its normalised form.
`is_correction` used to match literal phrases against `normalize_for_match(text)`
(lowercased, punctuation stripped); keeping that step would be a second matcher
wearing the first one's name, and it would silently break Family A's anchor.

`POSITIVE_ACK_PHRASES` stays in the miner and is out of scope. It feeds the
miner's retro hint, not the live path, and it was not measured.

### C3. `no_agent_context`, relaxed to what it meant

`collect_moments` drops a correction with no preceding assistant turn. The
reason is sound: the opening turn of a headless run can carry a trigger phrase,
and mining it lets noise buy itself a `+2`.

The implementation is wider than the reason. `scan_file` only appends entries
that produce prose (`extract_text` returns `""` for a message of tool_use blocks
alone), so an assistant turn that was nothing but tool calls is absent from
`messages` entirely. A user correcting an agent mid-tool-work can therefore look
like an opening turn.

The rescue: an assistant **entry** counts as context even when it carries no
prose. The quote and the stored `assistant_context` still come from prose, so a
tool-only turn contributes presence, not text. A correction that is genuinely
the first thing in a transcript is still dropped, which is the case the filter
was written for.

### C4. The way in, end to end

The chain in Why is a claim about how the pieces connect, and no test covers it.
One end-to-end test walks it on a synthetic transcript: a correction turn is
detected, becomes a moment, survives clustering, and appears in the digest with
its slug. That is the miner's half, which is the half that is code.

The live half — nudge to Path B to F to E to S — is agent behaviour and stays
prose. What can be pinned is that the nudge fires: given a prompt from each
family, the hook emits `[ani-nudge v1]` with the expected slug.

### C5. The description the model reads

Found while implementing C1, after this spec was approved.

The `description:` in `skills/ani/SKILL.md` frontmatter is the string that
decides whether the model loads the skill at all. It listed nine example
phrases, and all nine were drawn from `CORRECTION_PHRASES` — the same table
that had just measured 9% recall.

The three-layer story above says the hook owns recall and the model's semantic
match owns breadth. Both layers were written from one vocabulary, so the second
could not rescue what the first missed. `프런트가 안되는데?` is not a rephrasing
of "no, that's not it"; it is a symptom report, and nothing in that description
told the model to treat a symptom report as a correction. A user who reports the
bug instead of naming the mistake fell through both layers at once.

The description now names an example from each of the five families — a
rejection, a symptom report, a verdict on the work, a reminder they already said
it, a reversal — and says outright that a complaint or a bug report is a
correction too. The constraint that shaped the rewrite: this string is resident
in every session's context, so breadth had to come without bloat. It cost 190
characters, roughly 50 tokens, and one example was dropped to make room —
`그게 아니라`, strictly weaker than the `아니 그게 아니라` beside it, whose slot
went to the bare `아니` that opens five of the eleven labelled corrections. The
en/ja/zh examples, the Path A clause and the `/ani …` subcommands are unchanged.

`tests/test_skill_frontmatter.py` pins the coupling rather than trusting it: for
each of the five families, the description must offer a quoted example that the
hook's own table attributes to that family. A family cannot be added to the
table while the description is left behind.

## Testing

Propositions, each one a test:

- **C1 recall.** The eleven ground-truth quotes in this spec are a fixture. The
  rebuilt table detects at least ten of them. (The eleventh, `굉장히 짧고
  간결하게 눌러서 써야돼`, is a bare directive with no correction marker; it is
  named here as a known miss rather than chased with a rule that would fire on
  every instruction the user gives.)
- **C1 precision guards.** `아니면` at the start of a prompt does not fire
  Family A, and neither does `아니` in the middle of a sentence. `아니야`,
  `아니요` and `아니지` do fire: they were measured and every sampled one was a
  genuine correction, so the guard this spec first proposed for them was
  dropped.
- **C2 single source.** The miner detects exactly what the hook detects: for a
  sample spanning all families, `bootstrap.is_correction` and
  `trigger.detect_correction` agree on every input.
- **C3 rescue.** A transcript whose only assistant entry before the correction is
  a tool-use message yields a moment. A transcript whose correction is the first
  entry still yields none.
- **C4 end to end.** A synthetic transcript carrying one correction of each
  family produces a digest naming all of them.
- **C5 breadth.** Every measured family has a quoted example in the `SKILL.md`
  `description:` that the hook's table attributes to that family.

## Out of scope

- **The context budget and the three-layer split.** Measured and found sound; see
  "What this is not".
- **`POSITIVE_ACK_PHRASES`.** Unmeasured, and it feeds the miner's advisory hint
  rather than the live path.
- **The promotion arithmetic.** E and T are agent judgment specified in
  `SKILL.md`; this spec changes what reaches that judgment, not the judgment.
- **Per-user tuning.** Family D is this user's vocabulary. A configurable table
  is a real idea and a separate one.

## Known limits

- Family D is the least portable entry in the table. Another user who never says
  `슬롭` loses nothing, but also gains nothing from it.
- A bare directive with no correction marker (`굉장히 짧고 간결하게 써야돼`)
  stays invisible. Catching it means firing on ordinary instructions, and the
  cost of that is a store full of things the user simply asked for.
- The measured rates come from one user's five days. They are the best evidence
  available and they are not a general claim about Korean.
