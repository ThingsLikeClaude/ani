#!/usr/bin/env python3
"""ani doctor - installation self-check for the Tier 1 adapter (spec 3.8b).

Answers the one question a user actually has when nothing seems to happen:
*is any of this wired up?* Every check prints exactly one line

    OK|WARN|FAIL <check>: <detail>

and the process exits 0 (clean), 1 (at least one WARN) or 2 (at least one
FAIL). The output is deliberately ASCII-only: this runs on the console the user
already has, and on Windows that console is frequently cp949, where a stray
box-drawing character is the difference between a report and a traceback.

What it will not do: pretend to know that the hooks fire. A hook runs inside
Claude Code, in a process this script cannot see, so the last line is a NOTE
rather than a check - the honest answer is "open a fresh session and look".

Writes nothing except one probe file in the global store, which it removes
again. No network, ever. stdlib only.

Usage: python scripts/ani_doctor.py   (from any working directory)
"""

from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_DIR = os.path.join(REPO_ROOT, "hooks")

# The hooks own the definitions of "where do the stores live", "which rows are
# valid" and "which knowledge sources are configured". Importing them is the
# only way the doctor can report on the same resolution the hooks perform,
# rather than on a second implementation that drifts.
try:
    sys.dont_write_bytecode = True
    sys.path.insert(0, HOOK_DIR)
    import ani_trigger  # noqa: E402
except Exception:  # pragma: no cover - defensive
    ani_trigger = None
finally:
    try:
        sys.path.remove(HOOK_DIR)
    except ValueError:  # pragma: no cover - defensive
        pass

MIN_PYTHON = (3, 8)
PROBE_NAME = ".doctor-probe"
PROBE_BODY = "ani doctor write probe\n"
PLUGIN_ROOT = os.path.join("~", ".claude", "plugins")
PLUGIN_NAME = "ani"
# A plugin cache is <root>/cache/<marketplace>/<plugin>/<version>/, i.e. four
# levels plus the manifest directory. The walk is bounded in both depth and
# breadth so a doctor run can never turn into a disk crawl.
MAX_SCAN_DEPTH = 6
MAX_SCAN_DIRS = 4000
MAX_MANIFEST_BYTES = 64 * 1024
MAX_DETAIL_PATH = 160

NOTE_LINE = (
    "NOTE hook firing cannot be verified from here - open a fresh session "
    "and look for [ani-index v1]"
)

OK, WARN, FAIL = "OK", "WARN", "FAIL"
_EXIT = {OK: 0, WARN: 1, FAIL: 2}


def _ascii(text) -> str:
    """Force a value into the console's lowest common denominator.

    Paths are the reason: a home directory with a Korean or accented name is
    ordinary, and a cp949 console would raise on it mid-report.
    """
    return str(text).encode("ascii", "replace").decode("ascii")


def _short(path) -> str:
    text = _ascii(path)
    if len(text) > MAX_DETAIL_PATH:
        text = "..." + text[-MAX_DETAIL_PATH:]
    return text


class Report(object):
    """Collects lines, remembers the worst level seen."""

    def __init__(self):
        self.worst = OK

    def line(self, level, check, detail):
        if _EXIT[level] > _EXIT[self.worst]:
            self.worst = level
        sys.stdout.write(
            "{0} {1}: {2}\n".format(level, _ascii(check), _ascii(detail))
        )

    def note(self, text):
        sys.stdout.write(_ascii(text) + "\n")

    def exit_code(self):
        return _EXIT[self.worst]


# --- individual checks -----------------------------------------------------


def check_python(report):
    version = "{0}.{1}.{2}".format(*sys.version_info[:3])
    if sys.version_info[:2] >= MIN_PYTHON:
        report.line(OK, "python", "{0} (>= 3.8)".format(version))
    else:
        report.line(
            FAIL, "python", "{0} is below the required 3.8".format(version)
        )


def resolve_global_store(project_index):
    """(source label, path) for the global store, in the hooks' own order."""
    env_path = ani_trigger._expand_store_path(
        os.environ.get(ani_trigger.GLOBAL_STORE_ENV)
    )
    if env_path:
        return "env " + ani_trigger.GLOBAL_STORE_ENV, env_path
    if project_index:
        config = os.path.join(os.path.dirname(project_index), "config.md")
        configured = ani_trigger._expand_store_path(
            ani_trigger.read_config_value(config, "global_store")
        )
        if configured:
            return "config global_store", configured
    return "default ~/.ani", ani_trigger._expand_store_path(
        ani_trigger.DEFAULT_GLOBAL_STORE
    )


def check_global_store(report, source, store):
    if not store:
        report.line(FAIL, "global store", "could not be resolved to a path")
        return
    exists = os.path.isdir(store)
    detail = "{0} -> {1} ({2})".format(
        source, _short(store), "directory exists" if exists else "does not exist yet"
    )
    report.line(OK if exists else WARN, "global store", detail)


def check_write_probe(report, store):
    if not store:
        report.line(FAIL, "global store write", "no store path to probe")
        return
    if not os.path.isdir(store):
        report.line(
            WARN,
            "global store write",
            "skipped - {0} does not exist yet (it is created on first "
            "capture)".format(_short(store)),
        )
        return
    probe = os.path.join(store, PROBE_NAME)
    try:
        with open(probe, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(PROBE_BODY)
    except Exception as exc:
        report.line(
            FAIL,
            "global store write",
            "cannot write {0}: {1}".format(_short(probe), type(exc).__name__),
        )
        return
    try:
        os.remove(probe)
    except Exception as exc:
        report.line(
            WARN,
            "global store write",
            "wrote but could not remove {0}: {1}".format(
                _short(probe), type(exc).__name__
            ),
        )
        return
    report.line(OK, "global store write", "probe created and removed in " + _short(store))


def find_project_store(start):
    """The nearest ``.ani/`` directory at or above ``start``, or None.

    Deliberately looks for the directory, not for ``INDEX.md``: an overlay that
    exists but has no index yet is a real state, and one the hooks treat as
    absent - which is worth saying out loud rather than hiding.
    """
    try:
        current = os.path.abspath(start)
    except Exception:
        return None
    for _ in range(ani_trigger.MAX_PARENT_LEVELS + 1):
        candidate = os.path.join(current, ".ani")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if not parent or parent == current:
            break
        current = parent
    return None


def check_project_store(report, store):
    if not store:
        report.line(
            OK,
            "project store",
            "no .ani/ at or above the working directory (the overlay is "
            "opt-in)",
        )
        return
    if os.path.isfile(os.path.join(store, "INDEX.md")):
        report.line(OK, "project store", "found " + _short(store))
    else:
        report.line(
            WARN,
            "project store",
            "{0} exists but has no INDEX.md - the hooks locate a store by its "
            "index, so this overlay contributes nothing yet".format(_short(store)),
        )


def _id_column(text):
    """The id column index: a header row wins, else the documented order."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = ani_trigger._split_row(stripped)
        if not cells:
            continue
        lowered = [cell.lower() for cell in cells]
        if "id" in lowered and "keywords" in lowered:
            return lowered.index("id")
    return 0


def data_rows(text):
    """Every table row that is neither a separator nor the header."""
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = ani_trigger._split_row(stripped)
        if not cells:
            continue
        if all(ani_trigger._SEPARATOR_CELL_RE.match(cell or "-") for cell in cells):
            continue
        lowered = [cell.lower() for cell in cells]
        if "id" in lowered and "keywords" in lowered:
            continue
        rows.append(cells)
    return rows


def check_index(report, label, store):
    """One line about a store's INDEX.md, or one saying there is none."""
    path = os.path.join(store, "INDEX.md")
    check = "index (" + label + ")"
    if not os.path.isfile(path):
        report.line(OK, check, "no INDEX.md in " + _short(store) + " - nothing recorded yet")
        return
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        report.line(FAIL, check, "cannot stat {0}: {1}".format(_short(path), type(exc).__name__))
        return
    if size > ani_trigger.MAX_INDEX_BYTES:
        report.line(
            WARN,
            check,
            "{0} bytes exceeds the {1} byte cap - the hooks skip this file "
            "entirely".format(size, ani_trigger.MAX_INDEX_BYTES),
        )
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(ani_trigger.MAX_INDEX_BYTES)
    except Exception as exc:
        report.line(FAIL, check, "cannot read {0}: {1}".format(_short(path), type(exc).__name__))
        return
    valid = len(ani_trigger.parse_index(text))
    id_col = _id_column(text)
    bad = 0
    for cells in data_rows(text):
        candidate = cells[id_col].strip().strip("`") if id_col < len(cells) else ""
        if not (
            ani_trigger.valid_pattern_id(candidate)
            or ani_trigger.valid_failure_id(candidate)
        ):
            bad += 1
    detail = "{0} matchable S row(s) in {1}".format(valid, _short(path))
    if bad:
        report.line(
            WARN,
            check,
            detail + "; {0} row(s) have an id that is not a valid S- or F- id "
            "and are dropped".format(bad),
        )
    else:
        report.line(OK, check, detail)


def check_knowledge(report, project_index):
    sources = ani_trigger.knowledge_source_paths(project_index)
    origin = (
        "from " + ani_trigger.KNOWLEDGE_SOURCES_ENV
        if os.environ.get(ani_trigger.KNOWLEDGE_SOURCES_ENV) is not None
        else "from config.md"
    )
    if not sources:
        report.line(
            OK, "knowledge_sources", "none configured ({0})".format(origin)
        )
        return
    report.line(
        OK,
        "knowledge_sources",
        "{0} source(s) {1}, cap {2}".format(
            len(sources), origin, ani_trigger.MAX_KNOWLEDGE_SOURCES
        ),
    )
    for position, path in enumerate(sources, 1):
        check = "knowledge source {0}".format(position)
        if not os.path.isfile(path):
            report.line(WARN, check, "skipped - not a readable file: " + _short(path))
            continue
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            report.line(WARN, check, "skipped - cannot stat: " + type(exc).__name__)
            continue
        if size > ani_trigger.MAX_INDEX_BYTES:
            report.line(
                WARN,
                check,
                "skipped - {0} bytes exceeds the {1} byte cap: {2}".format(
                    size, ani_trigger.MAX_INDEX_BYTES, _short(path)
                ),
            )
            continue
        rows = ani_trigger.parse_knowledge(ani_trigger.read_knowledge_index(path))
        if rows:
            report.line(
                OK, check, "{0} active K rows in {1}".format(len(rows), _short(path))
            )
        else:
            report.line(
                WARN,
                check,
                "no usable rows in {0} - a row needs a K-<slug> id and status "
                "active".format(_short(path)),
            )


def _manifest_names(directory):
    """Candidate plugin.json paths directly under one directory."""
    return (
        os.path.join(directory, ".claude-plugin", "plugin.json"),
        os.path.join(directory, "plugin.json"),
    )


def _is_ani_manifest(path):
    try:
        if os.path.getsize(path) > MAX_MANIFEST_BYTES:
            return False
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            data = json.loads(handle.read(MAX_MANIFEST_BYTES))
    except Exception:
        return False
    return isinstance(data, dict) and data.get("name") == PLUGIN_NAME


def find_installed_plugin(root):
    """The directory of an installed ``ani`` plugin under ``root``, or None."""
    if not os.path.isdir(root):
        return None
    root_depth = root.rstrip(os.sep).count(os.sep)
    visited = 0
    for current, subdirs, _files in os.walk(root):
        visited += 1
        if visited > MAX_SCAN_DIRS:
            break
        if current.count(os.sep) - root_depth >= MAX_SCAN_DEPTH:
            del subdirs[:]
            continue
        for manifest in _manifest_names(current):
            if os.path.isfile(manifest) and _is_ani_manifest(manifest):
                return current
    return None


def check_hook_install(report):
    root = os.path.abspath(os.path.expanduser(PLUGIN_ROOT))
    found = find_installed_plugin(root)
    if found:
        report.line(OK, "hook install", "ani plugin found at " + _short(found))
    else:
        report.line(
            WARN,
            "hook install",
            "no ani plugin.json under {0} - expected if you run ani from a "
            "local checkout".format(_short(root)),
        )
    report.note(NOTE_LINE)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    report = Report()
    check_python(report)
    if ani_trigger is None:
        report.line(
            FAIL,
            "hooks",
            "cannot import ani_trigger.py from " + _short(HOOK_DIR),
        )
        report.note(NOTE_LINE)
        return report.exit_code()

    cwd = os.getcwd()
    project_index = ani_trigger.find_index(cwd)
    source, global_store = resolve_global_store(project_index)

    check_global_store(report, source, global_store)
    check_write_probe(report, global_store)

    project_store = find_project_store(cwd)
    check_project_store(report, project_store)

    if project_store:
        check_index(report, "project", project_store)
    if global_store:
        check_index(report, "global", global_store)

    check_knowledge(report, project_index)
    check_hook_install(report)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
