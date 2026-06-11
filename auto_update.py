#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Путь 101% 2026 — Автообновление журналов

Полный цикл без участия человека:
  1. fetch    — новые сообщения темы из Telegram (fetch_telegram.py)
  2. generate — пересборка журналов (parse_journals.py), только если есть новое
  3. publish  — git commit + push на GitHub Pages, только если есть изменения

Запускается планировщиком Windows (задача PUT101_Journals_Update)
каждые 2 часа с 08:00 до 22:00. Лог: auto_update.log.

Ручной запуск: python auto_update.py            — обычный цикл
               python auto_update.py --force    — пересобрать журналы даже без новых сообщений
"""

import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

LOG_FILE = os.path.join(SCRIPT_DIR, "auto_update.log")

import fetch_telegram
import parse_journals


def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line)
    except Exception:
        pass  # pythonw без консоли
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    force = "--force" in sys.argv
    log("── Запуск автообновления ──")

    # 1. Загрузка сообщений из Telegram
    try:
        has_new, rows = fetch_telegram.fetch(log)
    except Exception as e:
        log(f"ОШИБКА загрузки из Telegram: {e}")
        cache = fetch_telegram.load_cache()
        rows = cache.get("messages", [])
        if not rows:
            log("Кэша нет — обновление невозможно, выходим")
            return 1
        log(f"Продолжаю на старом кэше ({len(rows)} сообщ.)")
        has_new = False

    if not has_new and not force:
        # Журналы могли ещё ни разу не собираться из кэша — проверим
        if os.path.exists(os.path.join(SCRIPT_DIR, "index.html")):
            log("Новых сообщений нет — журналы актуальны")
            return 0

    # 2. Генерация журналов
    try:
        messages = parse_journals.messages_from_cache(rows)
        parse_journals.generate_all(messages, log)
    except Exception as e:
        log(f"ОШИБКА генерации журналов: {e}")
        return 1

    # 3. Публикация
    try:
        parse_journals.publish(log)
    except Exception as e:
        log(f"ОШИБКА публикации: {e}")
        return 1

    log("Готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())
