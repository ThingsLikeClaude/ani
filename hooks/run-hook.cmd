: << 'ANI_BATCH_BLOCK'
@echo off
REM ani hook launcher -- one file that both cmd.exe and bash can run.
REM
REM Why it exists: there is no interpreter name that works everywhere. Most
REM POSIX distributions ship "python3" and either lack "python" or still point
REM it at Python 2; Windows ships "python" (and the "py" launcher) and has no
REM "python3" at all. Hard-coding either name into hooks.json breaks half the
REM installs, so the name is resolved here, at run time.
REM
REM The extension is .cmd rather than .sh on purpose: Claude Code's Windows
REM command handling special-cases commands containing ".sh", and a hook that
REM gets rewritten underneath us is worse than one extra polyglot header.
REM
REM Under bash the whole batch section is swallowed by the quoted heredoc
REM above (":" is a no-op, and heredoc text is read from the script file, so
REM the hook's stdin is never touched). Under cmd.exe the first line is just a
REM label and execution starts here.
REM
REM Usage: run-hook.cmd <trigger|session-start>
REM Exit code is always 0: a missing interpreter degrades the plugin to Tier 0
REM (the skill alone), which is a supported configuration, not an error.

setlocal
set "ANI_HOOK_DIR=%~dp0"
set "ANI_SCRIPT="
if /i "%~1"=="trigger" set "ANI_SCRIPT=ani_trigger.py"
if /i "%~1"=="session-start" set "ANI_SCRIPT=ani_session_start.py"
if not defined ANI_SCRIPT exit /b 0

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python "%ANI_HOOK_DIR%%ANI_SCRIPT%"
    exit /b 0
)

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py -3 "%ANI_HOOK_DIR%%ANI_SCRIPT%"
    exit /b 0
)

REM No interpreter: stay silent rather than fail the session.
exit /b 0
ANI_BATCH_BLOCK

# --- POSIX / bash section -------------------------------------------------

# Git Bash hands a native python.exe whatever string we pass; `pwd -W` yields
# the Windows form of the directory there and does not exist anywhere else,
# where plain `pwd` is already correct.
ani_hook_dir=$(cd "$(dirname "$0")" 2>/dev/null && { pwd -W 2>/dev/null || pwd; })
[ -n "$ani_hook_dir" ] || exit 0

case "${1:-}" in
    trigger)       ani_script="ani_trigger.py" ;;
    session-start) ani_script="ani_session_start.py" ;;
    *)             exit 0 ;;
esac

# python3 first: on the systems that have both, it is the one guaranteed to be
# Python 3. `exec` keeps stdin attached -- the hooks read their payload from it.
for ani_python in python3 python; do
    if command -v "$ani_python" >/dev/null 2>&1; then
        exec "$ani_python" "${ani_hook_dir}/${ani_script}"
    fi
done

if command -v py >/dev/null 2>&1; then
    exec py -3 "${ani_hook_dir}/${ani_script}"
fi

exit 0
