@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title Puglia Termica 2026 - Motore di Ricerca AI
cd /d "%~dp0"

echo =======================================================================
echo          PUGLIA TERMICA 2026 - MOTORE DI RICERCA AI (PORTABLE)
echo =======================================================================
echo.

rem 1. Verifica ambiente virtuale (.venv)
set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else (
    rem 2. Cerca Python di sistema per creare .venv locale
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        set "SYS_PYTHON=python"
    ) else (
        where py >nul 2>&1
        if !errorlevel! equ 0 (
            set "SYS_PYTHON=py"
        ) else (
            echo [ERRORE] Python non trovato nel sistema.
            echo Installa Python 3.10 o 3.11 da python.org e riprova.
            echo.
            pause
            exit /b 1
        )
    )

    echo Creazione ambiente virtuale locale .venv in corso...
    !SYS_PYTHON! -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERRORE] Impossibile creare l'ambiente virtuale .venv.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=.venv\Scripts\python.exe"

    echo Installazione librerie da requirements.txt in corso...
    "!PYTHON_EXE!" -m pip install --upgrade pip
    "!PYTHON_EXE!" -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [ERRORE] Errore durante l'installazione delle dipendenze.
        pause
        exit /b 1
    )
)

echo Python rilevato: %PYTHON_EXE%
echo Controllo moduli...
"%PYTHON_EXE%" -c "import lancedb, fastembed, fitz, tantivy" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installazione dipendenze richieste in corso...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
)

echo.
echo =======================================================================
echo  Avvio del server Puglia Termica (porta 8085)...
echo  Il browser si aprira automaticamente non appena il server sara pronto.
echo.
echo  ATTENZIONE: NON CHIUDERE QUESTA FINESTRA mentre utilizzi l'applicazione!
echo  (Il server deve rimanere attivo in questa finestra)
echo  Per arrestare il server in qualsiasi momento, premi CTRL+C.
echo =======================================================================
echo.

"%PYTHON_EXE%" server_ui.py

echo.
echo [INFO] Processo server terminato.
pause
