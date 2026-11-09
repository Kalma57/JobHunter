@echo off
rem JobHunter morning run (docs/agents/brain-run.md). Windows Task Scheduler "JobHunter morning": every hour 08:00-23:00;
rem runs once a day - "due" exits at once when today is done or a run is going (9/11/2026: a missed run was not caught up).
rem prepare -> brain (claude -p) -> apply (cards onto the board) -> finish (public page + backup to git). No Claude app needed.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist state\logs mkdir state\logs
.venv\Scripts\python.exe -m jobhunter.morning due > nul 2>&1
if errorlevel 1 exit /b 0
.venv\Scripts\python.exe -m jobhunter.morning lock
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%d
set LOG=state\logs\morning-%TODAY%.log
rem the background browser of the HireMeTech agent must match the Playwright version (21/10/2026)
.venv\Scripts\python.exe -m playwright install --only-shell chromium >> %LOG% 2>&1
echo ==== %DATE% %TIME% prepare >> %LOG%
.venv\Scripts\python.exe -m jobhunter.morning prepare >> %LOG% 2>&1
echo ==== %DATE% %TIME% brain >> %LOG%
.venv\Scripts\python.exe -m jobhunter.morning brain >> %LOG% 2>&1
echo ==== %DATE% %TIME% apply >> %LOG%
.venv\Scripts\python.exe -m jobhunter.morning apply >> %LOG% 2>&1
echo ==== %DATE% %TIME% finish >> %LOG%
.venv\Scripts\python.exe -m jobhunter.morning finish >> %LOG% 2>&1
.venv\Scripts\python.exe -m jobhunter.morning unlock
echo ==== %DATE% %TIME% end >> %LOG%
