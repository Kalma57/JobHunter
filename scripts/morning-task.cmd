@echo off
rem JobHunter morning run, code half (docs/agents/morning-run.md). Run by Windows Task Scheduler ("JobHunter morning").
rem prepare: sub-agents + prefilter + plan  ->  the Claude run (09:05) reads state\plan\next.json and writes the board
rem finish --wait: waits for the Claude run's done marker, then public page + state backup to git.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist state\logs mkdir state\logs
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%d
echo ==== %DATE% %TIME% prepare >> state\logs\morning-%TODAY%.log
.venv\Scripts\python.exe -m jobhunter.morning prepare >> state\logs\morning-%TODAY%.log 2>&1
echo ==== %DATE% %TIME% finish --wait >> state\logs\morning-%TODAY%.log
.venv\Scripts\python.exe -m jobhunter.morning finish --wait >> state\logs\morning-%TODAY%.log 2>&1
echo ==== %DATE% %TIME% end >> state\logs\morning-%TODAY%.log
