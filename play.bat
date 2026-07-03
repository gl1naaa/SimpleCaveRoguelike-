@echo off
title Stone Dungeon
chcp 65001 >nul

:: Maximize window on start
if "%~1"=="" (
    start "" /MAX "%~f0" keep
    exit /b
)

cd /d D:\scripts\rogue_py\src
D:\scripts\rogue_py\.venv\Scripts\python.exe main.py
pause