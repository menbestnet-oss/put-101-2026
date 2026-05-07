@echo off
chcp 65001 > nul
echo ============================================================
echo   Путь 101% 2026 — Обновление журналов
echo ============================================================
echo.

REM Проверяем beautifulsoup4
python -c "import bs4" 2>nul
if errorlevel 1 (
    echo Устанавливаю beautifulsoup4...
    pip install beautifulsoup4 -q
)

echo Запускаю парсер...
python "%~dp0parse_journals.py"

echo.
pause
