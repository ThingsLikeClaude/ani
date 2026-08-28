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

## Korean (ko)

| Phrase | Note |
| --- | --- |
| 아니 그게 아니라 | The canonical form; the protocol is named after it |
| 그게 아니라 | Same, without the leading 아니 |
| 아니라고 | Emphatic repeat — often the *second* correction; check TRIAGE |
| 그거 말고 | Rejects the chosen target/object |
| 내 말은 (~라는 거였어) | Re-specifies the intent |
| ~라는 뜻이었어 / ~라는 의미였어 | Re-specifies the intent |
| 아니 그런 뜻이 (아니고/아니라) | Rejects the interpretation |
| 왜 자꾸 | **Escalation** — frustration at repetition; treat as a pollution signal |
| 또 그러네 | **Escalation** — same failure recurring |
| 그게 아니고 / 아니 아니 | Common colloquial variants |
| 내가 언제 ~라고 했어 | Denies the premise the agent acted on |

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
Register them in `.ani/config.md`:

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
- Harvest them from real `trigger_quote` values in `.ani/patterns/F-*.md`,
  not from imagination.
- Keep them short and distinctive. A phrase common in normal conversation
  ("아니") produces false positives for the deterministic adapters, which cannot
  read intent the way you can.
