# Standalone Windows application

The ready-to-run build is `../dist/CookingAgents.exe` (Windows x64). Distribute
that single file. It contains the Python runtime, game libraries and music;
participants do not need to install Python or dependencies.

Double-click the executable, enter a participant ID, select a robot and start.
Keep Logging ON for recorded sessions. The first recorded session creates a
`logs` folder beside the executable. Each session has its own CSV file and
`summary.csv` collects run summaries. Returning to the menu closes the current
recording. Place the game in a writable folder, such as Documents or the Desktop.

The menu's questionnaire link opens the participant's browser. Completing the
form requires internet access; local gameplay and logging do not.

## Rebuild after source changes

On Windows, using the project's Python 3.11 environment, run from the repository
root:

```powershell
.\overcookedAI\.venv\Scripts\python.exe -m pip install -r .\overcookedAI\requirements-build.txt
.\overcookedAI\build_exe.ps1
```

`CookingAgents.spec` builds one executable without a console window and includes
the `assets` directory. Generated `build/` and `dist/` directories are ignored by
Git. Rebuilding replaces the executable; source edits do not update it automatically.
The build uses PyInstaller 6.22.3. Asset paths use bundled module locations, while
output paths use the executable location. See the official
[spec-file](https://pyinstaller.org/en/stable/spec-files.html) and
[runtime-path](https://pyinstaller.org/en/stable/runtime-information.html) documentation.

## Verification

All 235 source tests passed before this rebuild. The finished executable was copied to a separate
temporary folder and launched from a different working directory with Python
environment variables removed and PATH limited to Windows System32.
Its built-in `--self-check` passed: the main menu rendered, the bundled MP3
decoded and played through SDL's silent audio driver, all three robot modes
started, mute/pause/restart/menu return worked, and six session CSVs plus a
summary were written beside the copied executable. No logs appeared in the
unrelated working directory. The current build additionally checks meal-end
cleanup while preserving the yellow order, and successful second-pot cooking
with an unrelated ingredient kept in the first pot for all three robot types.
It also checks taking and returning all eight raw ingredients with E.
The copied binary's hash matched the delivered one.

The report is `../build/standalone-verification.json`. This was automated
verification on this Windows computer, not a manual test on another computer.

`--self-check` is a developer diagnostic that writes `build-check.json` and
BUILD_CHECK logs beside the executable. Run it only on a copy in a clean folder;
normal double-click startup opens the game menu.
