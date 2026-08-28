#!/usr/bin/env python3
"""ani — Claude Code UserPromptSubmit hook (Tier 1 adapter).

Two independent, deterministic detections run on every submitted prompt:

1. Correction signal — the prompt contains a canonical "no, that's not it"
   phrase (ko/en/ja/zh). Emits an ``[ani-nudge v1]`` marker carrying the
   session id and a prompt hash so the skill can verify the marker belongs to
   the current turn before consuming it.
2. Proactive hint — the prompt overlaps the keywords of a usable S-pattern in
   the project's ``.ani/INDEX.md``. Emits an ``[ani-hint v1]`` marker listing
   up to three pattern ids.

Contract (see references/adapters/claude-code.md):
* stdout carries ONLY the single-line hook JSON, and only when there is
  something to say.
* Any failure whatsoever is silent: nothing on stdout, optional stderr note,
  exit code 0. The hook must never break the user's session.
* This is Tier 1. The core protocol (Tier 0) works without it.

stdlib only. UTF-8 no BOM, LF newlines. Runs on Windows and POSIX.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

MARKER_VERSION = "v1"
MAX_HINT_PATTERNS = 3
MAX_INDEX_BYTES = 256 * 1024
MAX_PARENT_LEVELS = 5

NUDGE_SENTENCE = (
    "Correction signal detected — if this is a genuine correction of the "
    "assistant's previous work, follow the ani skill protocol."
)
HINT_SENTENCE = (
    "These .ani success patterns may apply to this request — consult them "
    "before acting."
)

# Canonical correction phrases. Ordered most-specific first: the first match
# wins and supplies ``pattern=<slug>``. These are hints, not the protocol —
# semantic recognition by the model (P5) remains the real matcher.
CORRECTION_PHRASES = (
    # Korean
    ("ko-ani-geuge-anira", r"아니[\s,]*그게\s*아니라"),
    ("ko-ani-geureon-tteusi", r"아니[\s,]*그런\s*뜻이"),
    ("ko-geuge-anira", r"그게\s*아니라"),
    ("ko-anirago", r"아니라고"),
    ("ko-geugeo-malgo", r"그거\s*말고"),
    ("ko-raneun-tteusieosseo", r"(?:라는|란)\s*뜻이었"),
    ("ko-nae-mareun", r"내\s*말은"),
    ("ko-wae-jakku", r"왜\s*자꾸"),
    ("ko-tto-geureone", r"또\s*그러네"),
    # English (case-insensitive)
    ("en-no-thats-not", r"\bno[,!.\s]+that['’]?s\s+not\b"),
    ("en-thats-not-what-i", r"that['’]?s\s+not\s+what\s+i\b"),
    ("en-not-what-i-asked", r"\bnot\s+what\s+i\s+asked\b"),
    ("en-i-meant", r"\bi\s+meant\b"),
    ("en-you-misunderstood", r"\byou\s+misunderstood\b"),
    # Japanese
    ("ja-iya-sou-janakute", r"いや[、,]?\s*そうじゃなくて"),
    ("ja-sou-janakute", r"そうじゃなくて"),
    ("ja-souiu-imi-janai", r"そういう意味じゃない"),
    # Chinese
    ("zh-bushi-zhege-yisi", r"不是这个意思"),
    ("zh-wode-yisi-shi", r"我的意思是"),
)

_COMPILED_PHRASES = tuple(
    (slug, re.compile(pattern, re.IGNORECASE)) for slug, pattern in CORRECTION_PHRASES
)

# Common Korean particles stripped from prompt tokens before comparing them
# with INDEX keywords ("배경색을" -> "배경색"). Longest first.
KOREAN_PARTICLES = (
    "에서",
    "으로",
    "을",
    "를",
    "이",
    "가",
    "은",
    "는",
    "에",
    "로",
    "과",
    "와",
    "도",
    "만",
)

# S-patterns in these states are searchable (spec 3.3: review-needed and
# retired patterns are excluded from matching). active outranks provisional.
STATUS_PRIORITY = ("active", "provisional")

_TOKEN_RE = re.compile(r"[\w#+.\-]+", re.UNICODE)
_SEPARATOR_CELL_RE = re.compile(r"^:?-{2,}:?$")


def _force_utf8() -> None:
    """Never let a Windows cp949 console kill the hook."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def read_stdin() -> str:
    """Read the payload as UTF-8 regardless of the host locale.

    Claude Code sends UTF-8. On a Windows cp949 box the text wrapper would
    decode it with the ANSI code page and blow up on the first Korean
    character, so the bytes are taken straight from the buffer.
    """
    try:
        data = sys.stdin.buffer.read()
    except Exception:
        try:
            return sys.stdin.read()
        except Exception:
            return ""
    if isinstance(data, bytes):
        return data.decode("utf-8-sig", errors="replace")
    return data or ""


def detect_correction(prompt: str):
    """Return the slug of the first canonical correction phrase found."""
    for slug, regex in _COMPILED_PHRASES:
        if regex.search(prompt):
            return slug
    return None


def prompt_sha8(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]


def resolve_project_dir(payload) -> str:
    """CLAUDE_PROJECT_DIR > payload cwd > process cwd."""
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir and env_dir.strip():
        return env_dir.strip()
    if isinstance(payload, dict):
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd.strip():
            return cwd.strip()
    return os.getcwd()


def find_index(project_dir: str):
    """Locate .ani/INDEX.md at the project dir, else in its parents."""
    try:
        current = os.path.abspath(project_dir)
    except Exception:
        return None
    for _ in range(MAX_PARENT_LEVELS + 1):
        candidate = os.path.join(current, ".ani", "INDEX.md")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if not parent or parent == current:
            break
        current = parent
    return None


def read_index(path: str) -> str:
    try:
        if os.path.getsize(path) > MAX_INDEX_BYTES:
            return ""
    except OSError:
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read(MAX_INDEX_BYTES)


def _split_row(line: str):
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return cells


def _split_keywords(cell: str):
    cell = cell.strip().strip("`").strip()
    if cell.startswith("[") and cell.endswith("]"):
        cell = cell[1:-1]
    out = []
    for raw in re.split(r"[,;]", cell):
        keyword = raw.strip().strip("`'\"").strip().lower()
        if len(keyword) >= 2:
            out.append(keyword)
    return out


def parse_index(text: str):
    """Parse the INDEX cache table into (id, status, keywords) rows.

    Column order defaults to the documented
    ``| id | status | scope | keywords | summary | updated |`` but a header
    row, when present, wins — the table is a regenerable cache and may drift.
    """
    id_col, status_col, keyword_col = 0, 1, 3
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = _split_row(stripped)
        if not cells:
            continue
        if all(_SEPARATOR_CELL_RE.match(cell or "-") for cell in cells):
            continue
        lowered = [cell.lower() for cell in cells]
        if "id" in lowered and "keywords" in lowered:
            id_col = lowered.index("id")
            keyword_col = lowered.index("keywords")
            status_col = lowered.index("status") if "status" in lowered else -1
            continue
        if len(cells) <= max(id_col, keyword_col):
            continue
        pattern_id = cells[id_col].strip().strip("`")
        if not pattern_id.lower().startswith("s-"):
            continue
        status = ""
        if 0 <= status_col < len(cells):
            status = cells[status_col].strip().lower()
        keywords = _split_keywords(cells[keyword_col])
        if keywords:
            rows.append((pattern_id, status, keywords))
    return rows


def prompt_variants(prompt: str):
    """Lowercased prompt tokens plus Korean particle-stripped forms."""
    lower = prompt.lower()
    variants = set()
    for token in _TOKEN_RE.findall(lower):
        if not token:
            continue
        variants.add(token)
        for particle in KOREAN_PARTICLES:
            if token.endswith(particle) and len(token) > len(particle):
                variants.add(token[: -len(particle)])
    return lower, variants


def collect_hints(prompt: str, rows):
    """Up to MAX_HINT_PATTERNS S-ids whose keywords intersect the prompt."""
    lower, variants = prompt_variants(prompt)
    if not lower.strip():
        return []
    buckets = {status: [] for status in STATUS_PRIORITY}
    for pattern_id, status, keywords in rows:
        # A missing status cell is treated as active; retired / review-needed /
        # unknown states are not searchable.
        effective = status or STATUS_PRIORITY[0]
        if effective not in buckets:
            continue
        for keyword in keywords:
            if keyword in lower or keyword in variants:
                bucket_list = buckets[effective]
                if pattern_id not in bucket_list:
                    bucket_list.append(pattern_id)
                break
    ordered = []
    for status in STATUS_PRIORITY:
        for pattern_id in buckets[status]:
            if pattern_id not in ordered:
                ordered.append(pattern_id)
    return ordered[:MAX_HINT_PATTERNS]


def sanitize_session(session_id) -> str:
    if not isinstance(session_id, str):
        return "unknown"
    cleaned = re.sub(r"\s+", "", session_id)
    return cleaned[:128] if cleaned else "unknown"


def build_context(session_id, prompt: str, slug, hint_ids) -> str:
    blocks = []
    if slug:
        blocks.append(
            "[ani-nudge {version}] session={session} prompt_sha={sha} "
            "pattern={slug}\n{sentence}".format(
                version=MARKER_VERSION,
                session=sanitize_session(session_id),
                sha=prompt_sha8(prompt),
                slug=slug,
                sentence=NUDGE_SENTENCE,
            )
        )
    if hint_ids:
        blocks.append(
            "[ani-hint {version}] patterns={ids}\n{sentence}".format(
                version=MARKER_VERSION,
                ids=",".join(hint_ids),
                sentence=HINT_SENTENCE,
            )
        )
    return "\n".join(blocks)


def emit(context: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    line = json.dumps(payload, ensure_ascii=False)
    try:
        line.encode(getattr(sys.stdout, "encoding", None) or "utf-8")
    except (UnicodeEncodeError, LookupError):
        line = json.dumps(payload, ensure_ascii=True)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def run(raw: str) -> None:
    payload = json.loads(raw) if raw.strip() else None
    if not isinstance(payload, dict):
        return
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return

    slug = detect_correction(prompt)

    hint_ids = []
    try:
        index_path = find_index(resolve_project_dir(payload))
        if index_path:
            hint_ids = collect_hints(prompt, parse_index(read_index(index_path)))
    except Exception as exc:
        # An unreadable or malformed store must never cost us the nudge.
        hint_ids = []
        try:
            sys.stderr.write("ani_trigger: index lookup failed: {0}\n".format(exc))
        except Exception:
            pass

    if not slug and not hint_ids:
        return

    emit(build_context(payload.get("session_id"), prompt, slug, hint_ids))


def main() -> int:
    _force_utf8()
    try:
        raw = read_stdin()
    except Exception:
        return 0
    try:
        run(raw)
    except Exception as exc:  # never break the user's session
        try:
            sys.stderr.write("ani_trigger: {0}: {1}\n".format(type(exc).__name__, exc))
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
