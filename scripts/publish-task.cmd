@echo off
rem JobHunter: publish the public page once the Claude run is done (hourly, "JobHunter publish" in Task Scheduler).
rem The morning task's finish --wait gives up after 10 hours; a Claude run that finishes later is published here.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist state\logs mkdir state\logs
.venv\Scripts\python.exe -m jobhunter.morning finish --if-done >> state\logs\publish.log 2>&1
