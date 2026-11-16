@echo off
chcp 65001 >nul
title CBI Monitor - Monitoramento de Servicos Ativos
cd /d "%~dp0"
if exist "MonitorServicosCBI.exe" (
    start "" "MonitorServicosCBI.exe"
) else (
    start "" pythonw monitor_servicos_cbi.py
    if errorlevel 1 python monitor_servicos_cbi.py
)
