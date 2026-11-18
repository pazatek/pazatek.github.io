@echo off
rem Keeps the lamp relay running: restarts it 5 s after any exit. Matter's storage lock stops a second copy.
cd /d "%~dp0"
:loop
node relay.mjs >> relay.out 2>&1
timeout /t 5 /nobreak >nul
goto loop
