@echo off
chcp 65001 >nul
title Puglia Termica 2026 - Validazione Web Match (12.000 Prodotti)
color 0B
cd /d "%~dp0"

echo ===============================================================================
echo      PUGLIA TERMICA 2026 - VALIDATORE MATCH WEB & CATALOGO (12.000 PRODOTTI)
echo ===============================================================================
echo.
echo Avvio del processo di validazione incrociata:
echo - Cross-reference con 57.608 prodotti Puglia Termica
echo - Ricerca web in tempo reale su codici produttore (MPN)
echo - Cache locale permanente SQLite (nessun duplicato)
echo - Generazione Report Excel a Colori (.xlsx) e CSV
echo.

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
)

"%PYTHON_EXE%" -u run_web_match_audit.py

echo.
echo ===============================================================================
echo Processo terminato. Premi un tasto per uscire...
pause >nul
