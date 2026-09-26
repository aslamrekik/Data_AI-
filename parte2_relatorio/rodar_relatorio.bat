@echo off
REM Executa o relatorio semanal (pode ser agendado no Agendador de Tarefas do Windows)
cd /d "%~dp0"
python relatorio_semanal.py
exit /b %ERRORLEVEL%
