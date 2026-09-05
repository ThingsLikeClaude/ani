# Correction triggers — phrase hints, not a matcher

## The model is the matcher

**Semantic recognition is the detector. These phrase lists are hints.**

The tables below exist for three narrow purposes: to calibrate what a correction
sounds like in a language you see less often, to give deterministic hooks
(Tier 1 adapters) something cheap to grep for, and to let a project register its
own idioms. None of them is the mechanism.

The mechanism is this question, asked on every user turn:

> Does this turn mean *"you misread what I wanted"*?

If yes, the correction loop runs — even when the wording appears nowhere below,
even when the user is polite, terse, or writing in a language this file does not
list. If no, it does not run, no matter how many listed phrases appear.

Consequences worth stating plainly:

- A listed phrase is **not sufficient**. "그게 아니라 이건 원래부터 그랬어" is a
  factual aside, not a correction of you.
- An unlisted phrasing is **not exempt**. "…배경색을 말한 건데" is a full
  correction with no trigger phrase in it at all.
- A missing hook marker never means no correction occurred. Adapters reinforce
  the detector; they do not replace it.
- A correction is **not always a rephrasing**. A symptom report
  ("프런트가 안되는데?"), a verdict on the work ("이거 좀 별로야") and a
  withdrawal ("없던 걸로") are corrections too. This is the failure that made the
  Korean table below worth rebuilding: every entry it used to have was a
  rejection of *wording*, so a user who reported the bug instead of naming the
  mistake fell through both the hook and the reader of this file.

## Korean (ko)

Rebuilt 2026-09-06 from measurement rather than from intuition: the old list was
scored against eleven `trigger_quote` values the store itself had labelled
corrections, and matched one. The groups below are the five *kinds* of correction
that measurement found, and they are the groups
`hooks/ani_trigger.py` now greps for — the slug it emits (`pattern=ko-…`) names
the group, so a group that proves noisy can be dropped on evidence. Rows with no
slug are yours alone: real corrections that no adapter looks for.

### A — rejection and re-specification

| Phrase | Hook slug | Note |
| --- | --- | --- |
| 아니 … (turn-initial) | `ko-ani-muntu` | Bare 아니 opening the turn — five of the eleven labelled corrections start this way. Turn-initial only; mid-sentence 아니 usually corrects the user's own words, not yours |
| 아니면 … | *excluded* | **Not a correction.** A conjunction proposing an alternative ("아니면 버셀 배포할까?") — the one measured false positive, and the only exclusion in the hook |
| 아니 그게 아니라 | `ko-ani-geuge-anira` | The canonical form; the protocol is named after it |
| 그게 아니라 | `ko-geuge-anira` | Same, without the leading 아니 |
| 아니 그런 뜻이 (아니고/아니라) | `ko-ani-geureon-tteusi` | Rejects the interpretation |
| 아니라고 | `ko-anirago` | Emphatic repeat — often the *second* correction; check TRIAGE |
| 그거 말고 | `ko-geugeo-malgo` | Rejects the chosen target/object |
| 내 말은 (~라는 거였어) | `ko-nae-mareun` | Re-specifies the intent |
| ~라는 뜻이었어 / ~라는 의미였어 | `ko-raneun-tteusieosseo` | Re-specifies the intent; the hook greps the 뜻이었 form |
| 그게 아니고 / 아니 아니 | — | Colloquial variants; only the turn-initial ones reach the hook |
| 내가 언제 ~라고 했어 | — | Denies the premise the agent acted on |

### B — stated recurrence

The rarest group and the most valuable: the user is saying the recurrence out
loud, which is the one signal that proves `recurrence` without inference.

| Phrase | Hook slug | Note |
| --- | --- | --- |
| 여러 번 말했잖아 / 얘기했잖아 / 지적했잖아 | `ko-recur-yeoreobeon` | The speech verb is required — "여러번 실행해줘" is a request, not a complaint that something was said several times |
| 전에도 / 계속 (말·얘기·지적)했 | `ko-recur-jeonedo` | Spans sessions; the strongest cheap evidence of an unfixed F |
| 아까도 | `ko-recur-akkado` | Same session, earlier turn |
| 왜 자꾸 | `ko-recur-wae-jakku` | **Escalation** — frustration at repetition; treat as a pollution signal |
| 또 그러네 | `ko-recur-tto-geureo` | **Escalation** — same failure recurring |

### C — defect report

The user reports the symptom instead of naming the mistake. Still a correction.

| Phrase | Hook slug | Note |
| --- | --- | --- |
| ~가 안 되는데 | `ko-defect-an-doeneunde` | "프런트가 안되는데?" — a bug report aimed at your last change |
| 안 됨 | `ko-defect-an-doem` | Also appears inside long instruction text as a *rule* rather than a complaint; RESTATE settles which it is |
| 작동 안 (해/함/된다/돼) | `ko-defect-jakdong-an` | 안 has to be the negation adverb: a verb follows it. Without that, 작동 + 안정성/안내/안전 fires a defect report on a question about how something works |

### D — negative verdict

The most user-specific group here, and the first thing another store should
replace through `triggers_extra`. Kept because two of the eleven labelled
corrections are nothing but this.

| Phrase | Hook slug | Note |
| --- | --- | --- |
| 슬롭 / AI 슬롭 같아 | `ko-verdict-seullop` | A verdict on the work, with no restatement attached — ask what the right shape was |
| 이상해 | `ko-verdict-isanghae` | |
| 별로야 | `ko-verdict-byeolloya` | 별로 on its own is a degree adverb ("별로 안 급해"); only the predicate is a verdict |
| 촌스(럽다) | `ko-verdict-chonseu` | |
| 구려 | `ko-verdict-guryeo` | |

### E — reversal

| Phrase | Hook slug | Note |
| --- | --- | --- |
| 다시 생각해보니 | `ko-reversal-dasi-saenggak` | The user withdraws something they asked for |
| 안 쓰게 (될 것 같아) | `ko-reversal-an-sseuge` | |
| 없던 걸로 | `ko-reversal-eopdeon-geollo` | |

A reversal is a change of intent, not a report of your mistake. RESTATE decides
whether an F is warranted; what matters first is that you stop building the
withdrawn thing.

### The known miss

A bare directive with no correction marker — "굉장히 짧고 간결하게 눌러서 써야돼"
— fires nothing, deliberately: a rule that caught it would fire on every
instruction the user gives. Nothing but semantic judgement catches this one, and
it is exactly the case where a missing hook marker means nothing at all.

## English (en)

| Phrase | Note |
| --- | --- |
| no, that's not… | Canonical |
| that's not what I meant / asked for | Re-specifies intent |
| I meant … | Re-specifies intent |
| not what I asked | Rejects the output |
| you misunderstood / you're missing the point | Names the misreading |
| that's not it | Terse rejection |
| I said … , not … | Contrastive correction — usually a strong, precise F |
| again? / you did it again | **Escalation** — pollution signal |
| no, the *other* one | Rejects the chosen target |

## Japanese (ja)

| Phrase | Note |
| --- | --- |
| いや、そうじゃなくて | Canonical |
| そういう意味じゃない | Rejects the interpretation |
| そうではなくて | Formal variant |
| 私が言いたかったのは… | Re-specifies intent |
| それじゃなくて | Rejects the chosen target |
| また同じことを | **Escalation** |

## Chinese (zh)

| Phrase | Note |
| --- | --- |
| 不是这个意思 | Canonical |
| 我的意思是… | Re-specifies intent |
| 不是这个，是那个 | Rejects the chosen target |
| 我说的是… | Contrastive correction |
| 你误解了 | Names the misreading |
| 怎么又这样 | **Escalation** |

## Other languages (starter hints)

| Language | Phrases |
| --- | --- |
| Spanish (es) | no, no es eso; me refería a…; no es lo que pedí |
| French (fr) | non, ce n'est pas ça; je voulais dire…; ce n'est pas ce que j'ai demandé |
| German (de) | nein, so nicht; ich meinte…; das war nicht gemeint |
| Portuguese (pt) | não é isso; eu quis dizer…; não foi o que pedi |

Unlisted language? The detector is unchanged — recognize the meaning and run the
loop. Record the phrase actually used in the F file's `trigger_quote`; that is
how these tables grow from real usage.

## Escalation signals (feed TRIAGE, not just capture)

Phrases marked **Escalation** above ("왜 자꾸", "또 그러네", "again?",
"また同じことを", "怎么又这样") mean more than "wrong output". They mean *the
same wrongness has survived a previous correction*, which is the strongest cheap
signal that the context itself is polluted. When one appears:

- Still run the full loop (RESTATE → SEARCH → FIX → CAPTURE).
- In TRIAGE, escalate the recommendation one level: rewind instead of continue,
  fresh session instead of rewind.

The Korean two ride in group B and reach you as `ko-recur-wae-jakku` and
`ko-recur-tto-geureo`. Both readings hold at once for the same turn: the hook
counts stated recurrence, TRIAGE reads escalation.

Other pollution signals with no phrase attached: two corrections on the same
topic, repeated failed fix attempts in the last few turns, and your own
self-contradiction across turns.

## Cushion rule (mixed praise and correction)

Corrections often arrive wrapped in politeness — "좋은데, 근데…", "nice, but…",
"いいですね、ただ…". The praise does **not** neutralize the correction, and the
correction does not always cancel the praise. The scoring unit is the per-topic
round, not the utterance:

| Utterance | Reading |
| --- | --- |
| "좋은데 아직 글자색이 바뀌었잖아, 배경색이라고" | Same topic → re-correction. Round disqualified; the praise is a politeness softener worth 0. Behavior beats sentiment. |
| "배경색 좋네. 근데 폰트도 바꿔줘" | Different aspect → the background round keeps its +2; the font request opens its own round (RESTATE decides whether it is even a correction). |
| Ambiguous which aspect is meant | **Rule for the correction side.** A wrong compile costs more than a delayed one. |

## Not a correction (common false positives)

RESTATE resolves these naturally — if the restatement does not land on a changed
intent, end the loop silently, with no F file.

| Case | Example |
| --- | --- |
| Quoting or discussing the phrase | "사용자가 '아니 그게 아니라'라고 말하면 어떻게 처리하지?" |
| Joking or venting about something else | "아니 그게 아니라 오늘 회의가 3개야" |
| Correcting their own earlier statement | "아 내가 잘못 말했다, B로 해줘" → a **new request**, not a misreading by you |
| Rejecting a proposal you offered as a choice | "그거 말고 2번으로" → a selection, not a correction |
| Scope change after a correct implementation | "잘 됐어. 이제 모바일도 해줘" → new work |

The asymmetry: a false negative loses a bug report; a false positive wastes a
file. But a *wrongly compiled* pattern pollutes the store. So capture liberally,
compile conservatively.

## Adding project phrases

Teams develop their own idioms ("again with the mock data", "그거 말고 저거").
Register them in the store's `config.md`:

```markdown
---
triggers_extra:
  - "그거 말고 저거"
  - "again with the mock data"
---
```

Rules for `triggers_extra`:

- Hints only. They raise recall for hooks and for you; they never override the
  semantic judgement, and a listed phrase still has to *mean* a correction.
- Harvest them from real `trigger_quote` values in `<store>/patterns/F-*.md`,
  not from imagination.
- Keep them short and distinctive, and say where in the turn they count. A word
  common in ordinary conversation is safe for a deterministic adapter only when
  it is anchored: bare 아니 earns its place in the ko table because it fires
  turn-initially and nowhere else. Unanchored, it fires everywhere.
