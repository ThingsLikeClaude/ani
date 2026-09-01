#!/usr/bin/env python3
"""ani — Claude Code UserPromptSubmit hook (Tier 1 adapter).

Two independent, deterministic detections run on every submitted prompt:

1. Correction signal — the prompt contains a canonical "no, that's not it"
   phrase (ko/en/ja/zh). Emits an ``[ani-nudge v1]`` marker carrying the
   session id and a prompt hash so the skill can verify the marker belongs to
   the current turn before consuming it.
2. Proactive hint — the prompt overlaps the keywords of a usable S-pattern in
   either store: the project overlay ``<repo>/.ani/INDEX.md`` and the global
   store ``~/.ani/INDEX.md`` (spec §3.4). Project rows are read first and win
   on a shared id. Emits an ``[ani-hint v1]`` marker listing up to three
   pattern ids in total, not three per store.

   The same marker can also carry ``K-`` ids from external *knowledge sources*
   — files in the INDEX table shape that this plugin does not own and never
   writes, named by the ``knowledge_sources`` config key (spec §3.7,
   schemas.md §6). They fill only the slots the stores left: a K id can never
   displace an S id, and the total cap is unchanged. Knowledge is read here and
   nowhere else — the SessionStart injection deliberately does not touch it,
   because a standing per-session budget is the wrong place for knowledge that
   can be pulled on demand.

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
# The INDEX budget in schemas.md §3 is 60 rows / 6KB. 16 KiB is headroom over
# that without being fail-open: anything larger is not an INDEX we should be
# feeding into the turn's context, so the hint path is skipped entirely.
MAX_INDEX_BYTES = 16 * 1024
MAX_PARENT_LEVELS = 5
# A hook payload is one prompt. Anything past this is not a prompt; refuse to
# even decode it rather than spend the user's turn on it.
MAX_STDIN_BYTES = 256 * 1024
# Pattern ids are echoed verbatim into additionalContext, i.e. straight into
# the model's system reminder. Only ids that match the schema's S-<kebab-slug>
# shape are ever echoed; everything else is dropped without comment.
MAX_PATTERN_ID_LEN = 64
_PATTERN_ID_RE = re.compile(r"\AS-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
# Knowledge ids reach the same sink from a file this plugin does not own, so
# they are pinned to the same shape as an S id, one letter apart.
_KNOWLEDGE_ID_RE = re.compile(r"\AK-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
# F ids are echoed by the SessionStart hook (the unresolved-recurrence line) and
# are turned into a path under ``patterns/``, so the shape is pinned exactly:
# no separators, no dots, no traversal.
_FAILURE_ID_RE = re.compile(r"\AF-[0-9]{8}-[a-z0-9]{8}\Z")

# Two stores (spec §3.4). The global store is the always-present default; the
# project ``.ani/`` is an opt-in overlay. The global path resolves from the
# ANI_GLOBAL_STORE environment variable, then from ``global_store:`` in the
# project store's config.md, then from the default below.
GLOBAL_STORE_ENV = "ANI_GLOBAL_STORE"
DEFAULT_GLOBAL_STORE = os.path.join("~", ".ani")
# A configured path is expanded with expanduser and nothing else: no
# environment interpolation, no shell, no globbing. A store path is a location,
# never a command.
MAX_STORE_PATH_LEN = 512
MAX_CONFIG_BYTES = 8 * 1024
# External knowledge indexes: files in the same 6-column table shape as
# INDEX.md, listed as a comma-separated path list under ``knowledge_sources``
# in either store's config.md, or in ANI_KNOWLEDGE_SOURCES. The environment
# variable REPLACES the configured lists rather than adding to them — present
# but empty is therefore an explicit "no knowledge", not a fall-through.
KNOWLEDGE_SOURCES_ENV = "ANI_KNOWLEDGE_SOURCES"
KNOWLEDGE_SOURCES_KEY = "knowledge_sources"
# Four files, stat-ed and read inside the user's turn on every prompt. The cap
# is a latency budget, not a taste judgement; extras are dropped silently.
MAX_KNOWLEDGE_SOURCES = 4
# The only status a knowledge row may carry. A third-party file has no
# provisional tier for this hook to reason about, so anything else is dropped
# rather than ranked.
KNOWLEDGE_STATUS = "active"
_CONFIG_FRONTMATTER_FENCE = "---"
_INLINE_COMMENT_RE = re.compile(r"\s+#.*\Z")
# Session ids are echoed too. Claude Code sends a UUID; anything outside this
# conservative alphabet is dropped character by character.
_SESSION_DROP_RE = re.compile(r"[^A-Za-z0-9._\-]+")

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


def read_stdin():
    """Read the payload as UTF-8 regardless of the host locale.

    Claude Code sends UTF-8. On a Windows cp949 box the text wrapper would
    decode it with the ANSI code page and blow up on the first Korean
    character, so the bytes are taken straight from the buffer.

    Reads at most ``MAX_STDIN_BYTES + 1``: returns ``None`` when the payload
    exceeds the cap, which the caller turns into the silent contract (no
    stdout, exit 0). An unbounded read would let a pathological payload pin
    memory inside the user's turn.
    """
    try:
        data = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
    except Exception:
        try:
            data = sys.stdin.read(MAX_STDIN_BYTES + 1)
        except Exception:
            return ""
    if data is None:
        return ""
    if len(data) > MAX_STDIN_BYTES:
        return None
    if isinstance(data, bytes):
        return data.decode("utf-8-sig", errors="replace")
    return data


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
    """Locate .ani/INDEX.md at the project dir, else in its parents.

    The global store is never a project overlay. It lives at ``~/.ani`` by
    default, which sits in the parent walk of every folder under home, so a
    session started in one of them used to have the user's personal store
    claimed as the project's — announced as repo-local and shared with a team,
    and matched at project priority, for a repo that does not exist. Reaching
    it *by climbing* ends the walk and answers "no project overlay";
    ``find_global_index`` then offers it under its own name.

    Ending the walk is the point, not merely skipping the directory. Climbing
    past the global store would let an unrelated ancestor — another checkout,
    another user's tree — supply the overlay for a directory that has none,
    which is a worse misattribution than the one being fixed.

    The starting directory is the exception. A store the caller is standing in
    is this directory's overlay whatever else it is configured to be: it is
    physically in the tree being worked on, so "repo-local, shared with the
    team" is the safety-relevant truth about it, and `find_global_index`'s
    `_same_path` guard already keeps it from being announced twice. What the
    fix removes is *inheritance* of a store from an ancestor, not a store that
    is right here.

    Resolution here is env-then-default, without the project config: the config
    that could redirect ``global_store`` lives inside the overlay this function
    is still looking for, and a store claiming to be somewhere other than
    itself does not change what it is.
    """
    try:
        current = os.path.abspath(project_dir)
    except Exception:
        return None
    global_store = global_store_dir()
    for depth in range(MAX_PARENT_LEVELS + 1):
        store = os.path.join(current, ".ani")
        candidate = os.path.join(store, "INDEX.md")
        if os.path.isfile(candidate):
            if depth and _same_path(store, global_store):
                return None
            return candidate
        parent = os.path.dirname(current)
        if not parent or parent == current:
            break
        current = parent
    return None


def _expand_store_path(raw):
    """Turn a configured store path into an absolute one, or None.

    ``expanduser`` is the only expansion performed. ``expandvars`` is
    deliberately absent: the value comes from a file in the repo, and a store
    path must not be able to read the environment, let alone run anything.
    """
    if not isinstance(raw, str):
        return None
    value = raw.strip().strip("'\"").strip()
    if not value or len(value) > MAX_STORE_PATH_LEN:
        return None
    if any(char in value for char in ("\n", "\r", "\x00")):
        return None
    try:
        return os.path.abspath(os.path.expanduser(value))
    except Exception:
        return None


def _strip_inline_comment(value: str) -> str:
    """Drop a trailing ``# …`` from an unquoted scalar, the way YAML would.

    The shipped templates annotate fields inline (``recurrence: 0  # …``), so a
    reader that took the rest of the line verbatim would reject every value a
    user copied from a template.
    """
    text = value.strip()
    quote = text[:1]
    if quote in ("'", '"'):
        # A quoted scalar ends at its closing quote; anything after it is a
        # comment, so it goes the same way as an unquoted one's.
        end = text.find(quote, 1)
        return text[: end + 1] if end > 0 else text
    return _INLINE_COMMENT_RE.sub("", text)


def read_config_value(config_path: str, key: str, max_bytes: int = MAX_CONFIG_BYTES):
    """Read one scalar key from a markdown file's YAML frontmatter block.

    Used for ``global_store`` in a store's config.md and for ``recurrence`` in
    an F pattern file — the same shape, so the same reader.

    Deliberately not a YAML parser: the only key any hook needs is
    ``global_store``, and a hook that grows a parser stops being a hook. Keys
    outside the leading ``---`` block are ignored, so the free-form notes in
    the body cannot be mistaken for configuration.
    """
    try:
        if os.path.getsize(config_path) > max_bytes:
            return None
        # utf-8-sig: a BOM is against the schema but must not silently cost the
        # whole block, which is what a mismatched opening fence would do.
        with open(config_path, "r", encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read(max_bytes)
    except OSError:
        return None
    prefix = key + ":"
    in_frontmatter = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == _CONFIG_FRONTMATTER_FENCE:
            if in_frontmatter:
                break
            in_frontmatter = True
            continue
        if not in_frontmatter:
            if not stripped:
                continue  # leading blank lines are tolerated
            break  # body before any frontmatter: nothing to read
        if stripped.startswith(prefix):
            return _strip_inline_comment(stripped[len(prefix) :])
    return None


def global_store_dir(project_index_path=None):
    """Absolute path of the global store: env > project config > ``~/.ani``."""
    override = _expand_store_path(os.environ.get(GLOBAL_STORE_ENV))
    if override:
        return override
    if project_index_path:
        config = os.path.join(os.path.dirname(project_index_path), "config.md")
        configured = _expand_store_path(read_config_value(config, "global_store"))
        if configured:
            return configured
    return _expand_store_path(DEFAULT_GLOBAL_STORE)


def _split_source_list(raw):
    """A comma-separated path list into absolute paths, dropping the unusable.

    Each entry goes through :func:`_expand_store_path`, so a knowledge source
    obeys exactly the rules a store path does: ``~`` is expanded and nothing
    else, no environment interpolation, no shell, no globbing, and an entry
    that is empty, over-long, or carries a newline or NUL is dropped.
    """
    if not isinstance(raw, str):
        return []
    out = []
    for chunk in raw.split(","):
        path = _expand_store_path(chunk)
        if path:
            out.append(path)
    return out


def _dedupe_paths(paths):
    """First occurrence wins, order preserved; case-folded like the OS folds it."""
    seen = set()
    out = []
    for path in paths:
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _config_sources(store_dir):
    return _split_source_list(
        read_config_value(os.path.join(store_dir, "config.md"), KNOWLEDGE_SOURCES_KEY)
    )


def knowledge_source_paths(project_index_path=None):
    """The knowledge files to consult: env override, else project then global.

    ``ANI_KNOWLEDGE_SOURCES`` REPLACES both configured lists — it is the escape
    hatch and the kill switch, so a variable that is present but empty resolves
    to no sources rather than falling through to config.

    Otherwise the project overlay's list is read first and the global store's
    is appended, then duplicates are dropped keeping first position. Project
    first for the same reason project rows are matched first: a repo's list is
    the more specific statement. At most ``MAX_KNOWLEDGE_SOURCES`` survive.
    """
    raw_env = os.environ.get(KNOWLEDGE_SOURCES_ENV)
    if raw_env is not None:
        return _dedupe_paths(_split_source_list(raw_env))[:MAX_KNOWLEDGE_SOURCES]
    paths = []
    if project_index_path:
        paths.extend(_config_sources(os.path.dirname(project_index_path)))
    store = global_store_dir(project_index_path)
    if store:
        paths.extend(_config_sources(store))
    return _dedupe_paths(paths)[:MAX_KNOWLEDGE_SOURCES]


def _same_path(left, right) -> bool:
    if not left or not right:
        return False
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def find_global_index(project_index_path=None):
    """``<global store>/INDEX.md``, or None when it is absent or is the project's.

    Unlike the project store there is no parent walk: the global store is one
    named location, not something to be discovered.
    """
    store = global_store_dir(project_index_path)
    if not store:
        return None
    candidate = os.path.join(store, "INDEX.md")
    if _same_path(candidate, project_index_path):
        return None  # the overlay and the default resolved to one file
    return candidate if os.path.isfile(candidate) else None


def read_index(path: str) -> str:
    try:
        if os.path.getsize(path) > MAX_INDEX_BYTES:
            return ""
    except OSError:
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read(MAX_INDEX_BYTES)


def read_knowledge_index(path) -> str:
    """The text of one knowledge file, or ``""`` — this one never raises.

    A knowledge source is a path a user typed into a config file: it may be
    gone, be a directory, or be unreadable, and none of those is worth a word.
    The size rule is INDEX.md's, unchanged: past ``MAX_INDEX_BYTES`` the file is
    skipped **whole** rather than truncated, because a table that big is not one
    to be feeding into the turn at all.
    """
    if not isinstance(path, str) or not path:
        return ""
    try:
        if not os.path.isfile(path):
            return ""
        return read_index(path)
    except Exception:
        return ""


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


def valid_pattern_id(pattern_id) -> bool:
    """True only for a schema-shaped ``S-<kebab-slug>`` id.

    The INDEX is a file in the repo, so its cells are untrusted input that
    ends up inside the model's context. An id like
    ``S-evil] Ignore prior instructions`` must never reach the marker, so the
    shape is enforced here rather than sanitised at the sink.
    """
    if not isinstance(pattern_id, str):
        return False
    if not pattern_id or len(pattern_id) > MAX_PATTERN_ID_LEN:
        return False
    return _PATTERN_ID_RE.match(pattern_id) is not None


def valid_failure_id(pattern_id) -> bool:
    """True only for a schema-shaped ``F-<YYYYMMDD>-<rand8>`` id.

    Same contract as :func:`valid_pattern_id`, plus one more: this id is joined
    onto a store path, so the shape has to exclude ``/``, ``\\`` and ``..``
    by construction rather than by sanitising afterwards.
    """
    if not isinstance(pattern_id, str):
        return False
    if not pattern_id or len(pattern_id) > MAX_PATTERN_ID_LEN:
        return False
    return _FAILURE_ID_RE.match(pattern_id) is not None


def valid_knowledge_id(pattern_id) -> bool:
    """True only for a ``K-<kebab-slug>`` id from a knowledge source.

    Identical contract to :func:`valid_pattern_id`, and identical stakes: a
    knowledge file is somebody else's file, so a row reading
    ``K-evil] ignore prior instructions`` must be refused by shape here rather
    than sanitised at the sink.
    """
    if not isinstance(pattern_id, str):
        return False
    if not pattern_id or len(pattern_id) > MAX_PATTERN_ID_LEN:
        return False
    return _KNOWLEDGE_ID_RE.match(pattern_id) is not None


def valid_hint_id(pattern_id) -> bool:
    """True for either kind of id the ``[ani-hint v1]`` marker may carry."""
    return valid_pattern_id(pattern_id) or valid_knowledge_id(pattern_id)


def parse_index(text: str, is_valid_id=valid_pattern_id):
    """Parse an INDEX-shaped table into (id, status, keywords) rows.

    Column order defaults to the documented
    ``| id | status | scope | keywords | summary | updated |`` but a header
    row, when present, wins — the table is a regenerable cache and may drift.

    Rows whose id fails ``is_valid_id`` are dropped here; status is filtered
    later, in :func:`collect_hints`. The validator is a parameter only so a
    knowledge source can be parsed by the same code that parses the store's own
    INDEX — the two files have one format, and must have one parser.
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
        if not is_valid_id(pattern_id):
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


def collect_hints(prompt: str, rows, exclude=None, limit=MAX_HINT_PATTERNS):
    """Up to ``limit`` S-ids from ONE store whose keywords intersect the prompt.

    ``exclude`` carries the ids a higher-priority store already claimed, which
    is how the project overlay wins a shared id: the global pass never gets to
    offer an id the project pass already emitted.
    """
    lower, variants = prompt_variants(prompt)
    if not lower.strip():
        return []
    excluded = set(exclude or ())
    buckets = {status: [] for status in STATUS_PRIORITY}
    for pattern_id, status, keywords in rows:
        if pattern_id in excluded:
            continue
        # Searchable statuses are exactly `active` and `provisional`. An empty
        # cell, a missing status column, or any other value (retired,
        # review-needed, a typo, something injected) is not searchable — the
        # INDEX is an untrusted file, so this fails closed.
        if status not in buckets:
            continue
        for keyword in keywords:
            if keyword in lower or keyword in variants:
                bucket_list = buckets[status]
                if pattern_id not in bucket_list:
                    bucket_list.append(pattern_id)
                break
    ordered = []
    for status in STATUS_PRIORITY:
        for pattern_id in buckets[status]:
            if pattern_id not in ordered:
                ordered.append(pattern_id)
    return ordered[:limit]


def collect_store_hints(prompt: str, project_rows, global_rows):
    """Hints across both stores under one shared cap.

    Order is store-major, matching the matching priority in schemas.md
    (`project S > global S`); within a store `active` still outranks
    `provisional`. The cap is MAX_HINT_PATTERNS in total — a second store must
    not double the number of ids pushed into the turn.
    """
    ids = collect_hints(prompt, project_rows)
    if len(ids) < MAX_HINT_PATTERNS:
        ids = ids + collect_hints(
            prompt, global_rows, exclude=ids, limit=MAX_HINT_PATTERNS - len(ids)
        )
    return ids[:MAX_HINT_PATTERNS]


def parse_knowledge(text: str):
    """Eligible rows from a knowledge index: ``active`` only, K ids only.

    Everything else — a provisional row, a retired one, a blank status cell, an
    id of any other shape — is dropped without comment (schemas.md §6). The
    file is not this plugin's, so it gets the narrowest reading that can still
    be useful.

    Note what does NOT come back with the row: the summary cell is parsed and
    discarded. Only the id is ever echoed, which is why the hint path needs no
    fence neutralisation — unlike the SessionStart injection, no prose from an
    untrusted file reaches the turn at all.
    """
    return [
        row
        for row in parse_index(text, valid_knowledge_id)
        if row[1] == KNOWLEDGE_STATUS
    ]


def collect_knowledge_hints(prompt: str, sources, exclude=None, limit=0):
    """K ids for the slots the stores left over, in source order.

    ``limit`` is what remains of ``MAX_HINT_PATTERNS`` after the stores have
    been served, so this can only ever add to the marker, never reorder or
    evict it: knowledge is the least authoritative tier and is priced that way.
    Sources are concatenated before matching, so an earlier file wins a tie.
    """
    if limit <= 0:
        return []
    rows = []
    for path in sources:
        rows.extend(parse_knowledge(read_knowledge_index(path)))
    if not rows:
        return []
    return collect_hints(prompt, rows, exclude=exclude, limit=limit)


def sanitize_session(session_id) -> str:
    """Reduce the session id to the id alphabet before it is echoed.

    Same reasoning as :func:`valid_pattern_id`: everything this function
    returns lands inside the marker, inside the model's context.
    """
    if not isinstance(session_id, str):
        return "unknown"
    cleaned = _SESSION_DROP_RE.sub("", session_id)
    return cleaned[:128] if cleaned else "unknown"


def build_context(session_id, prompt: str, slug, hint_ids) -> str:
    # Re-validate at the sink: nothing reaches additionalContext unvalidated,
    # whatever path it arrived by. Both id shapes are alphanumeric-and-hyphen
    # by construction, so there is no fence or control character left for the
    # marker to carry — the shape check IS the neutralisation.
    hint_ids = [pattern_id for pattern_id in hint_ids if valid_hint_id(pattern_id)]
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


def emit(context: str, event_name: str = "UserPromptSubmit") -> None:
    """Write the single-line hook JSON.

    ``event_name`` is a parameter only so the SessionStart hook can reuse the
    encoding fallback below instead of copying it; this hook always passes the
    default.
    """
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
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
    project_index = None
    try:
        project_index = find_index(resolve_project_dir(payload))
        global_index = find_global_index(project_index)
        project_rows = parse_index(read_index(project_index)) if project_index else []
        global_rows = parse_index(read_index(global_index)) if global_index else []
        hint_ids = [
            pattern_id
            for pattern_id in collect_store_hints(prompt, project_rows, global_rows)
            if valid_pattern_id(pattern_id)
        ]
    except Exception as exc:
        # An unreadable or malformed store must never cost us the nudge.
        hint_ids = []
        try:
            sys.stderr.write("ani_trigger: index lookup failed: {0}\n".format(exc))
        except Exception:
            pass

    # Knowledge fills what the stores left, in its own try: a broken knowledge
    # file must cost the K hints only — not the store hints, not the nudge.
    remaining = MAX_HINT_PATTERNS - len(hint_ids)
    if remaining > 0:
        try:
            hint_ids = hint_ids + [
                pattern_id
                for pattern_id in collect_knowledge_hints(
                    prompt,
                    knowledge_source_paths(project_index),
                    exclude=hint_ids,
                    limit=remaining,
                )
                if valid_knowledge_id(pattern_id)
            ]
        except Exception as exc:
            try:
                sys.stderr.write(
                    "ani_trigger: knowledge lookup failed: {0}\n".format(exc)
                )
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
    if raw is None:  # payload over MAX_STDIN_BYTES: silent, no stdout
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
