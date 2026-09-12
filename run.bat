@echo off
setlocal
set "ROOT=%~dp0"
"%ROOT%.venv\Scripts\python.exe" -m src.main %*
set "EXITCODE=%ERRORLEVEL%"
endlocal & exit /b %EXITCODE%
