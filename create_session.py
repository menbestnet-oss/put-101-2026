#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Одноразовое создание Telegram-сессии для журналов «Путь 101% 2026».

Запуск: СОЗДАТЬ_СЕССИЮ.bat (или python create_session.py)
Спросит номер телефона (+7...), затем код, который придёт в Telegram.
После этого auto_update.py работает полностью автоматически.
"""

import asyncio
import sys

from telethon import TelegramClient

from fetch_telegram import API_ID, API_HASH, SESSION

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main():
    print("Создаю сессию Telegram для журналов «Путь 101% 2026»")
    print("Понадобится: номер телефона (+7...) и код, который придёт в Telegram.\n")

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"\n✅ Готово! Вошли как: {me.first_name or ''} {me.last_name or ''} (@{me.username})")
    print("Теперь журналы будут обновляться автоматически по расписанию.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
