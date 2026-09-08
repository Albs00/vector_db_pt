@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title Puglia Termica 2026 - Test Suite
cd /d "%~dp0"

echo =======================================================================
echo          PUGLIA TERMICA 2026 - VERIFICA BENCHMARK E TEST SUITE
echo =======================================================================
echo.

set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [1/2] Esecuzione Benchmark di Ricerca (7 Test Case)...
"%PYTHON_EXE%" test_search_benchmark.py

echo.
echo [2/2] Esecuzione Test Combinazioni e Compatibilita Clima (5 Test Case)...
"%PYTHON_EXE%" test_ac_combinations.py

echo.
echo =======================================================================
echo Test completati con successo.
echo =======================================================================
pause
