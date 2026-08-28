#!/usr/bin/env python3
"""ani bootstrap miner — cold-start pattern discovery from past transcripts.

This script is a DUMB MINER. It scans local Claude Code session transcripts,
finds moments where the user corrected the agent, clusters them by keyword
overlap, and prints a markdown digest.

It deliberately does NOT:

  * call any model or network service (stdlib only, fully offline),
  * write anything into ``.ani/`` (drafting F/S patterns is the agent's job),
  * decide anything. Every number it emits is advisory input for the LLM
    running ``/ani bootstrap``.

See ``skills/ani/references/adapters/bootstrap.md`` for the full flow and
``skills/ani/references/schemas.md`` for the F/S schemas the agent drafts.

Usage:
    python ani_bootstrap.py [--claude-dir PATH] [--project SLUG]
                            [--days N] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

__version__ = "1.0.0"

# --------------------------------------------------------------------------
# Phrase hints
# --------------------------------------------------------------------------
# (phrase, language). Korean is matched as a plain substring because Korean
# agglutinates without spaces; English is matched on whitespace boundaries so
# that "i meant" does not fire inside "hi meant".
CORRECTION_PHRASES = [
    ("아니 그게 아니라", "ko"),
    ("그게 아니라", "ko"),
    ("아니라고", "ko"),
    ("그거 말고", "ko"),
    ("내 말은", "ko"),
    ("라는 뜻이었어", "ko"),
    ("왜 자꾸", "ko"),
    ("또 그러네", "ko"),
    ("아니 그런 뜻이", "ko"),
    ("no, that's not", "en"),
    ("that's not what i", "en"),
    ("i meant", "en"),
    ("not what i asked", "en"),
    ("you misunderstood", "en"),
]

POSITIVE_ACK_PHRASES = [
    ("좋아", "ko"),
    ("좋네", "ko"),
    ("됐다", "ko"),
    ("됐네", "ko"),
    ("그래 그거야", "ko"),
    ("완벽", "ko"),
    ("perfect", "en"),
    ("great", "en"),
    ("thanks", "en"),
    ("that works", "en"),
]

# Trigger words themselves must not become cluster keywords.
STOPWORDS = {
    # Korean — trigger fragments plus very common filler
    "아니", "아니라", "아니라고", "그게", "그거", "말고", "말은", "뜻이었어",
    "라는", "뜻이", "자꾸", "그러네", "그런", "이거", "저거", "이건", "저건",
    "해줘", "해라", "하라고", "다시", "그리고", "근데", "그냥", "진짜", "지금",
    "그대로", "이렇게", "저렇게", "여기", "거기",
    # English — trigger fragments plus stopwords
    "no", "not", "that", "thats", "what", "meant", "asked", "misunderstood",
    "you", "your", "the", "an", "is", "are", "was", "were", "be", "to", "of",
    "and", "or", "in", "on", "at", "for", "with", "this", "these", "those",
    "it", "its", "do", "did", "does", "my", "me", "but", "so", "just", "only",
    "should", "would", "could", "please", "can", "will", "have", "has",
}

# Single-char Korean particles stripped from tokens of length >= 3 (stem >= 2).
# This is the one place the miner does more than the letter of the spec: without
# it "배경색만" and "배경색을" never cluster, which guts cross-session recall for
# Korean users. Documented in bootstrap.md.
KO_PARTICLES_1 = "을를은는이가만도에의로와과"
KO_PARTICLES_2 = ("에서", "으로", "에게", "부터", "까지", "한테")

# Characters kept during tokenisation: digits, ASCII letters, Hangul, kana, CJK.
# Everything else collapses to a single space, so punctuation, em dashes and
# apostrophes never break a phrase match.
_KEEP_RE = re.compile(
    "[^0-9a-z"
    "가-힣"   # Hangul syllables
    "ㄱ-ㆎ"   # Hangul compatibility jamo
    "぀-ヿ"   # kana
    "一-鿿"   # CJK unified ideographs
    "]+"
)

QUOTE_TRIM = 200
CONTEXT_TRIM = 300
FOLLOWUP_TRIM = 160
MAX_FOLLOWUPS = 2
MAX_MEMBERS_SHOWN = 3
MAX_KEYWORDS = 8
REPEAT_WINDOW = 10          # user messages examined for a repeated correction
JACCARD_THRESHOLD = 0.3

SKIP_ENTRY_TYPES = {
    "system", "summary", "progress", "file-history-snapshot", "attachment",
}


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------
def normalize_for_match(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    return " ".join(_KEEP_RE.sub(" ", text.lower()).split())


def _contains(haystack_norm: str, phrase: str, lang: str) -> bool:
    needle = normalize_for_match(phrase)
    if not needle:
        return False
    if lang == "en":
        return (" " + needle + " ") in (" " + haystack_norm + " ")
    return needle in haystack_norm


def find_phrases(text: str, table) -> list:
    norm = normalize_for_match(text)
    if not norm:
        return []
    return [p for p, lang in table if _contains(norm, p, lang)]


def is_correction(text: str) -> list:
    return find_phrases(text, CORRECTION_PHRASES)


def is_positive_ack(text: str) -> list:
    return find_phrases(text, POSITIVE_ACK_PHRASES)


def _strip_particle(token: str) -> str:
    if len(token) >= 4:
        for suffix in KO_PARTICLES_2:
            if token.endswith(suffix) and _is_hangul(token[0]):
                return token[: -len(suffix)]
    if len(token) >= 3 and token[-1] in KO_PARTICLES_1 and _is_hangul(token[0]):
        return token[:-1]
    return token


def _is_hangul(ch: str) -> bool:
    return "가" <= ch <= "힣"


def tokenize(text: str) -> set:
    """Correction quote -> keyword token set used for clustering."""
    tokens = set()
    for raw in normalize_for_match(text).split():
        if len(raw) < 2 or raw in STOPWORDS:
            continue
        tok = _strip_particle(raw)
        if len(tok) < 2 or tok in STOPWORDS:
            continue
        tokens.add(tok)
    return tokens


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / float(len(a | b))


def trim(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 3].rstrip() + "..."


# --------------------------------------------------------------------------
# Transcript parsing
# --------------------------------------------------------------------------
def parse_timestamp(value):
    """Parse an ISO-8601 timestamp into an aware UTC datetime, or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z") or raw.endswith("z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        # Tolerate a trailing non-ISO suffix such as " UTC".
        try:
            parsed = datetime.fromisoformat(raw.split(" ")[0])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def extract_text(content) -> str:
    """Pull user/assistant prose out of a message ``content`` field.

    Handles a plain string and a list of blocks; only ``type == "text"`` blocks
    contribute, so tool_use / tool_result / thinking blocks are ignored.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "text":
                continue
            piece = block.get("text")
            if isinstance(piece, str) and piece.strip():
                parts.append(piece.strip())
        return "\n".join(parts).strip()
    return ""


def entry_role(entry: dict) -> str:
    etype = entry.get("type")
    if etype in ("user", "assistant"):
        return etype
    message = entry.get("message")
    if isinstance(message, dict):
        role = message.get("role")
        if role in ("user", "assistant"):
            return role
    return ""


def scan_file(path: Path, cutoff, stats: dict) -> list:
    """Return the ordered list of prose messages in one transcript file."""
    messages = []
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError as exc:                                   # pragma: no cover
        stats["unreadable_files"] += 1
        stats["notes"].append("could not open %s: %s" % (path, exc))
        return messages

    with handle:
        for lineno, raw in enumerate(handle, 1):
            stats["lines"] += 1
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except ValueError:
                stats["malformed"] += 1
                continue
            if not isinstance(entry, dict):
                stats["malformed"] += 1
                continue
            if entry.get("isSidechain") is True:
                stats["sidechain_skipped"] += 1
                continue
            if entry.get("type") in SKIP_ENTRY_TYPES:
                continue

            role = entry_role(entry)
            if not role:
                continue

            message = entry.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if content is None:
                content = entry.get("content")
            text = extract_text(content)
            if not text:
                # Tool results, tool calls and empty turns land here.
                stats["non_prose_skipped"] += 1
                continue

            timestamp = parse_timestamp(entry.get("timestamp"))
            if cutoff is not None and timestamp is not None and timestamp < cutoff:
                stats["out_of_window"] += 1
                continue

            messages.append(
                {
                    "lineno": lineno,
                    "role": role,
                    "text": text,
                    "timestamp": timestamp,
                }
            )
    return messages


# --------------------------------------------------------------------------
# Moment extraction
# --------------------------------------------------------------------------
def preceding_assistant(messages: list, index: int) -> str:
    for j in range(index - 1, -1, -1):
        if messages[j]["role"] == "assistant":
            return messages[j]["text"]
    return ""


def retro_hint(messages: list, user_order: list, position: int):
    """Advisory hindsight evidence for one moment.

    +2  a positive acknowledgement appears in a later user message
    +1  no further correction phrase within the next REPEAT_WINDOW user messages
    """
    score = 0
    reasons = []

    later = user_order[position + 1:]
    if any(is_positive_ack(messages[i]["text"]) for i in later):
        score += 2
        reasons.append("positive ack later in session (+2)")
    else:
        reasons.append("no positive ack (+0)")

    window = later[:REPEAT_WINDOW]
    if any(is_correction(messages[i]["text"]) for i in window):
        reasons.append("re-correction within next %d user turns (+0)" % REPEAT_WINDOW)
    else:
        score += 1
        reasons.append("no re-correction within next %d user turns (+1)" % REPEAT_WINDOW)

    return score, reasons


def collect_moments(session_id: str, messages: list) -> list:
    moments = []
    user_order = [i for i, m in enumerate(messages) if m["role"] == "user"]
    position_of = {idx: pos for pos, idx in enumerate(user_order)}

    for index in user_order:
        message = messages[index]
        hits = is_correction(message["text"])
        if not hits:
            continue

        followups = []
        for later in user_order[position_of[index] + 1:]:
            followups.append(trim(messages[later]["text"], FOLLOWUP_TRIM))
            if len(followups) >= MAX_FOLLOWUPS:
                break

        score, reasons = retro_hint(messages, user_order, position_of[index])
        timestamp = message["timestamp"]
        moments.append(
            {
                "session": session_id,
                "lineno": message["lineno"],
                "timestamp": timestamp.isoformat() if timestamp else "",
                "sort_key": timestamp or datetime.min.replace(tzinfo=timezone.utc),
                "quote": trim(message["text"], QUOTE_TRIM),
                "matched": hits,
                "assistant_context": trim(preceding_assistant(messages, index), CONTEXT_TRIM),
                "followups": followups,
                "retro_hint": score,
                "retro_reasons": reasons,
                "tokens": tokenize(message["text"]),
            }
        )
    return moments


# --------------------------------------------------------------------------
# Clustering
# --------------------------------------------------------------------------
def cluster_moments(moments: list) -> list:
    clusters = []
    for moment in moments:
        best_cluster = None
        best_score = 0.0
        for cluster in clusters:
            score = max(
                (jaccard(moment["tokens"], member["tokens"]) for member in cluster["members"]),
                default=0.0,
            )
            if score >= JACCARD_THRESHOLD and score > best_score:
                best_cluster = cluster
                best_score = score
        if best_cluster is None:
            clusters.append({"members": [moment], "order": len(clusters)})
        else:
            best_cluster["members"].append(moment)

    for cluster in clusters:
        members = cluster["members"]
        cluster["retro_hint"] = max(m["retro_hint"] for m in members)
        cluster["sessions"] = sorted({m["session"] for m in members})
        counts = {}
        for member in members:
            for token in member["tokens"]:
                counts[token] = counts.get(token, 0) + 1
        cluster["keywords"] = [
            token
            for token, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ][:MAX_KEYWORDS]

    clusters.sort(key=lambda c: (-len(c["members"]), c["order"]))
    return clusters


# --------------------------------------------------------------------------
# Digest rendering
# --------------------------------------------------------------------------
NEXT_STEPS = """\
## Next steps

This digest is raw mining output — nothing has been written to `.ani/`. The
agent running `/ani bootstrap` continues from here:

1. **Read every cluster as one candidate failure.** The quotes are verbatim
   user turns; the assistant context is what preceded them. Discard clusters
   that are quotations, jokes, or corrections of the *user's own* earlier
   statement rather than of the agent.
2. **Draft one F per surviving cluster** at `.ani/patterns/F-<YYYYMMDD>-<rand8>.md`
   with `status: captured`, per `references/schemas.md` §1. Use the cluster's
   verbatim quote for `trigger_quote`, the cluster keywords as the starting
   point for `keywords`, and build `## Excerpt` from the correction quote plus
   the assistant context — the excerpt must stand alone without this digest.
   Get `<YYYYMMDD>` from the `date` command, never from memory.
3. **Score the evidence** per design §3.3.1. The `retro-E hint` below counts
   only the two hindsight signals this script can see:
   positive ack `+2`, no re-correction `+1`. The agent adds the repetition
   signal itself: `+2` when a cluster has **2 or more members** (the same
   failure recurred across turns/sessions). So a cluster with an ack, no
   re-correction, and 2+ members reaches `E = 5` — the default threshold `T`.
4. **Draft a provisional S** for every cluster reaching `E >= 5`, per
   `references/schemas.md` §2: `status: provisional`, `scope: project`,
   `compiled_from` pointing at the F drafted in step 2, `summary` in use-when
   form. Every `## Verification` item needs all five fields. Ask "what check
   would have caught this misreading?" — that answer is the verification.
5. **Present one digest table** (`cluster | quote | members | E | proposed id |
   proposed status`) and let the user batch-approve. Approved drafts are
   written as `active` S; the rest stay `captured` F. Nothing is written until
   the user approves.
6. **Regenerate `.ani/INDEX.md`** from the frontmatter of everything written,
   respecting the 60-row / 6KB budget.

Reminder: the miner is a keyword hint, not a judge. Clusters it missed are
still real, and clusters it found may be noise — semantic recognition (P5) is
the authority.
"""


def render_digest(clusters, moments, stats, args, cutoff) -> str:
    lines = []
    add = lines.append

    add("# ani bootstrap digest")
    add("")
    add("Mined from local Claude Code transcripts. Advisory only — nothing was")
    add("written to `.ani/`.")
    add("")
    add("## Scan")
    add("")
    add("- Generated: %s" % datetime.now(timezone.utc).isoformat(timespec="seconds"))
    add("- Miner version: %s" % __version__)
    add("- Claude dir: `%s`" % args.claude_dir)
    add("- Project filter: %s" % ("`%s`" % args.project if args.project else "(none)"))
    if cutoff is None:
        add("- Window: all history (no --days filter)")
    else:
        add("- Window: last %d days (since %s)" % (args.days, cutoff.date().isoformat()))
    add("- Files scanned: %d" % stats["files"])
    add("- Lines read: %d" % stats["lines"])
    add("- Malformed lines skipped: %d" % stats["malformed"])
    add("- Non-prose entries skipped: %d" % stats["non_prose_skipped"])
    add("- Sidechain entries skipped: %d" % stats["sidechain_skipped"])
    add("- Entries outside window: %d" % stats["out_of_window"])
    add("- Correction moments found: %d" % len(moments))
    add("- Clusters formed: %d" % len(clusters))
    add("")

    if not clusters:
        add("## Clusters")
        add("")
        add("No correction moments matched the phrase hints in this window.")
        add("")
        add("Widen the search before concluding the history is clean: raise")
        add("`--days`, drop `--project`, or check that `--claude-dir` points at the")
        add("right transcript store. Phrase hints also miss corrections phrased in")
        add("other words — that is expected, and is why this script is only a")
        add("bootstrap aid.")
        add("")
        add(NEXT_STEPS.rstrip())
        add("")
        return "\n".join(lines)

    for number, cluster in enumerate(clusters, 1):
        members = cluster["members"]
        add("## Cluster %d - %d moment(s)" % (number, len(members)))
        add("")
        add("- Sessions: %s" % ", ".join("`%s`" % s for s in cluster["sessions"]))
        add("- retro-E hint: %d (max across members; advisory, not authoritative)"
            % cluster["retro_hint"])
        add("- Repetition signal (+2, agent-applied): %s"
            % ("yes - 2+ members" if len(members) >= 2 else "no - single member"))
        add("- Suggested keywords: %s"
            % (", ".join(cluster["keywords"]) if cluster["keywords"] else "(none)"))
        add("")

        shown = members[:MAX_MEMBERS_SHOWN]
        for position, member in enumerate(shown, 1):
            stamp = member["timestamp"] or "(no timestamp)"
            add("### Moment %d.%d - `%s`:%d - %s"
                % (number, position, member["session"], member["lineno"], stamp))
            add("")
            add("- Matched hint(s): %s" % ", ".join('"%s"' % h for h in member["matched"]))
            add("- retro-E hint: %d (%s)" % (member["retro_hint"], "; ".join(member["retro_reasons"])))
            add("")
            add("Correction (verbatim):")
            add("")
            add("> %s" % member["quote"])
            add("")
            if member["assistant_context"]:
                add("Assistant context immediately before:")
                add("")
                add("> %s" % member["assistant_context"])
                add("")
            else:
                add("Assistant context immediately before: (none in window)")
                add("")
            if member["followups"]:
                add("Next user turn(s):")
                add("")
                for followup in member["followups"]:
                    add("- %s" % followup)
                add("")
        if len(members) > MAX_MEMBERS_SHOWN:
            add("_%d further moment(s) in this cluster not shown._"
                % (len(members) - MAX_MEMBERS_SHOWN))
            add("")

    add(NEXT_STEPS.rstrip())
    add("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
def iter_transcripts(projects_dir: Path, project_filter):
    if not projects_dir.is_dir():
        return
    try:
        slugs = sorted(p for p in projects_dir.iterdir() if p.is_dir())
    except OSError:                                          # pragma: no cover
        return
    for slug_dir in slugs:
        if project_filter and project_filter not in slug_dir.name:
            continue
        try:
            files = sorted(slug_dir.glob("*.jsonl"))
        except OSError:                                      # pragma: no cover
            continue
        for path in files:
            yield slug_dir.name, path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ani_bootstrap.py",
        description=(
            "Mine past Claude Code transcripts for correction moments and emit "
            "an ani bootstrap digest. Read-only: never writes into .ani/."
        ),
    )
    parser.add_argument(
        "--claude-dir",
        default=str(Path.home() / ".claude"),
        help="Harness config dir holding projects/<slug>/*.jsonl (default: ~/.claude)",
    )
    parser.add_argument(
        "--project",
        default="",
        help="Substring filter on the project slug (default: all projects)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Only consider entries newer than N days; 0 or less disables the filter (default: 90)",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Write the digest to FILE (UTF-8, LF) instead of stdout",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    cutoff = None
    if args.days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)

    claude_dir = Path(args.claude_dir).expanduser()
    projects_dir = claude_dir / "projects"

    stats = {
        "files": 0,
        "lines": 0,
        "malformed": 0,
        "non_prose_skipped": 0,
        "sidechain_skipped": 0,
        "out_of_window": 0,
        "unreadable_files": 0,
        "notes": [],
    }

    moments = []
    for slug, path in iter_transcripts(projects_dir, args.project):
        stats["files"] += 1
        session_id = "%s/%s" % (slug, path.name)
        messages = scan_file(path, cutoff, stats)
        moments.extend(collect_moments(session_id, messages))

    moments.sort(key=lambda m: (m["sort_key"], m["session"], m["lineno"]))
    clusters = cluster_moments(moments)
    digest = render_digest(clusters, moments, stats, args, cutoff)

    if args.out:
        out_path = Path(args.out).expanduser()
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(digest)
    else:
        # Bypass the console codec entirely so Korean survives on Windows.
        sys.stdout.buffer.write(digest.encode("utf-8"))
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
