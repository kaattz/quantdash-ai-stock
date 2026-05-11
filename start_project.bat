@echo off
setlocal

cd /d "%~dp0"
where pwsh >nul 2>nul
if errorlevel 1 (
  echo [ERROR] PowerShell 7+ ^(pwsh^) is required to start this project.
  exit /b 1
)

pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_project.ps1"
