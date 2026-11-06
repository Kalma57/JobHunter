@echo off
rem JobHunter morning run (docs/agents/brain-run.md). Windows Task Scheduler "JobHunter morning", daily 08:00.
rem prepare (sub-agents, prefilter, plan, the code's own board writes) -> brain (claude -p) -> apply (cards onto the board)
rem -> finish (public page + backup to git). No Claude app needed (6/11/2026).
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist state\logs mkdir state\logs
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
echo ==== %DATE% %TIME% end >> %LOG%
