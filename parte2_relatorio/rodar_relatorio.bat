@echo off
REM Gera o relatorio semanal do funil. Uso: duplo clique, ou pelo Agendador de Tarefas.
REM Argumentos opcionais sao repassados: rodar_relatorio.bat --referencia 2025-06-16
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] Ambiente .venv nao encontrado. Veja a secao "Instalacao" do README.
  exit /b 1
)
".venv\Scripts\python.exe" parte2_relatorio\relatorio_semanal.py %*
set CODIGO=%ERRORLEVEL%
if %CODIGO%==0 (
  echo Relatorio gerado em parte2_relatorio\output\
) else (
  echo [ERRO] Codigo %CODIGO%. Veja o log mais recente em parte2_relatorio\logs\
)
exit /b %CODIGO%
