@echo off
rem ============================================================
rem  Swarm-Intelligence Algorithm Encyclopedia - local server
rem  Double-click to start; the browser opens automatically.
rem  Keep this window open while browsing; close it to stop.
rem  (Opening index.html directly via file:// cannot run the
rem   algorithms - the Python runtime needs http.)
rem ============================================================
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py serve.py
) else (
    python serve.py
)
pause
