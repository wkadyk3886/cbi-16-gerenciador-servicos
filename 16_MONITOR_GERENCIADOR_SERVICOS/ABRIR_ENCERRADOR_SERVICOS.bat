@echo off
chcp 65001 >nul
title CBI KillSwitch - Encerrador de Servicos CBI
cd /d "%~dp0"
if exist "EncerradorServicosCBI.exe" (
    start "" "EncerradorServicosCBI.exe"
) else (
    start "" pythonw encerrar_servicos_cbi.py
    if errorlevel 1 python encerrar_servicos_cbi.py
)
