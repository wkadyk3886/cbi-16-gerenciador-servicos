@echo off
chcp 65001 >nul
title CBI - Encerrar TODOS os Servicos Imediatamente
cd /d "%~dp0"
echo =================================================================
echo   ENCERRANDO TODOS OS SERVICOS E PROCESSOS ATIVOS DO CBI...
echo =================================================================
python encerrar_servicos_cbi.py --all --yes
echo.
pause
