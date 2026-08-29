@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -NoExit -Command ".\scripts\studio-doctor.ps1 -Fast"
