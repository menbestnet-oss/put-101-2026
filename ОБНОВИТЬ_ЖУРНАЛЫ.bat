@echo off
chcp 65001 > nul
echo ============================================================
echo   Путь 101% 2026 — Обновление журналов (из Telegram)
echo ============================================================
echo.

REM Проверяем telethon
python -c "import telethon" 2>nul
if errorlevel 1 (
    echo Устанавливаю telethon...
    pip install telethon -q
)

echo Забираю сообщения из Telegram и обновляю журналы...
python "%~dp0auto_update.py" --force

echo.
pause
