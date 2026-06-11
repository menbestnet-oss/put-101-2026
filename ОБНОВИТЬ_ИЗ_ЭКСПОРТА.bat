@echo off
chcp 65001 > nul
echo ============================================================
echo   Путь 101% 2026 — Обновление из ручного HTML-экспорта
echo ============================================================
echo Запасной способ: берёт самый свежий экспорт темы «Путь 101»
echo из Downloads\Telegram Desktop (папки ChatExport_*).
echo.

python "%~dp0parse_journals.py"

echo.
pause
