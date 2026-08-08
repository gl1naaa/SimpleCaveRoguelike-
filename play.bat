@echo off
title Simple Cave Roguelike
chcp 65001 >nul

:: Maximize window on start
if "%~1"=="" (
    start "" /MAX "%~f0" keep
    exit /b
)

cd /d D:\scripts\SimpleCaveRoguelike\src
D:\scripts\.venv312\Scripts\python.exe main.py
pause