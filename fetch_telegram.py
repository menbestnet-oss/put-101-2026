#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Путь 101% 2026 — Загрузка сообщений из Telegram (Telethon)

Забирает сообщения из темы «Путь 101% 2026» группы «Отдела продаж»
напрямую через аккаунт пользователя (сессия из tg_export).
Хранит результат инкрементально в messages_cache.json.

Запуск отдельно (для отладки): python fetch_telegram.py
Обычно вызывается из auto_update.py.
"""

import asyncio
import json
import os
import sys

from telethon import TelegramClient
from telethon.tl.functions.messages import GetForumTopicsRequest

# ── Настройки ────────────────────────────────────────────────────────────────

API_ID   = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

# Собственная сессия проекта (НЕ общая с tg_export/tg_monitor — общую Telegram
# отозвал 11.06.2026 из-за одновременного использования с двух IP).
# Создаётся один раз через СОЗДАТЬ_СЕССИЮ.bat
SESSION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "put101")

GROUP_TITLE = "Отдел продаж📈🔥💰"
TOPIC_TITLE = "Путь 101 % 2026"

# Известные id (найдены 11.06.2026) — используются сразу, поиск по названию это запасной путь
KNOWN_CHAT_ID  = 1758575794
KNOWN_TOPIC_ID = 39074

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, "messages_cache.json")

# Сколько последних сообщений перечитывать при каждом запуске,
# чтобы подхватить редактирования и удаления
EDIT_OVERLAP = 100

if sys.platform == "win32" and sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── Кэш ──────────────────────────────────────────────────────────────────────

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"chat_id": None, "topic_id": None, "messages": []}


def save_cache(cache):
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CACHE_FILE)


# ── Поиск группы и темы ──────────────────────────────────────────────────────

def _norm(s):
    """Нормализация названия: нижний регистр, без пробелов — устойчиво к «101 %» vs «101%»."""
    return "".join((s or "").lower().split())


async def find_group(client, log):
    wanted = _norm(GROUP_TITLE)
    async for dialog in client.iter_dialogs():
        # ищем только форум-группы — обычные чаты с похожим названием не подходят
        if not getattr(dialog.entity, "forum", False):
            continue
        if _norm(dialog.title) == wanted:
            return dialog.entity
    raise RuntimeError(f"Форум-группа «{GROUP_TITLE}» не найдена среди диалогов")


async def find_topic(client, entity, log):
    result = await client(GetForumTopicsRequest(
        peer=entity, offset_date=None, offset_id=0, offset_topic=0, limit=100,
    ))
    wanted = _norm(TOPIC_TITLE)
    titles = []
    for t in result.topics:
        title = (getattr(t, "title", "") or "").strip()
        titles.append(title)
        if _norm(title) == wanted:
            return t.id
    raise RuntimeError(
        f"Тема «{TOPIC_TITLE}» не найдена. Доступные темы: {', '.join(repr(x) for x in titles)}"
    )


# ── Загрузка сообщений ───────────────────────────────────────────────────────

def sender_display_name(msg):
    s = msg.sender
    if s is not None:
        if getattr(s, "first_name", None) or getattr(s, "last_name", None):
            return f"{s.first_name or ''} {s.last_name or ''}".strip()
        if getattr(s, "title", None):
            return s.title
    if getattr(msg, "post_author", None):
        return msg.post_author
    return None


async def fetch_new(client, entity, topic_id, min_id, log):
    """Возвращает список сообщений темы с id > min_id (от старых к новым)."""
    rows = []
    async for msg in client.iter_messages(entity, reply_to=topic_id, min_id=min_id):
        text = msg.text or ""
        if not text.strip():
            continue
        author = sender_display_name(msg)
        if not author:
            continue
        local_dt = msg.date.astimezone()  # UTC → локальное время
        rows.append({
            "msg_id":   msg.id,
            "author":   author,
            "datetime": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "text":     text,
        })
    rows.sort(key=lambda r: r["msg_id"])
    return rows


async def _fetch_async(log):
    cache = load_cache()

    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        known_chat = cache["chat_id"] or KNOWN_CHAT_ID
        try:
            from telethon.tl.types import PeerChannel
            entity = await client.get_entity(PeerChannel(known_chat))
        except Exception:
            entity = await find_group(client, log)

        chat_id = entity.id
        topic_id = cache["topic_id"] or (KNOWN_TOPIC_ID if chat_id == KNOWN_CHAT_ID else None)
        if not topic_id or cache.get("chat_id") not in (None, chat_id):
            topic_id = await find_topic(client, entity, log)
            log(f"Тема найдена: id={topic_id}")

        old_msgs = cache["messages"]
        if old_msgs:
            old_msgs.sort(key=lambda r: r["msg_id"])
            # перечитываем хвост, чтобы подхватить правки/удаления
            overlap_from = old_msgs[-min(EDIT_OVERLAP, len(old_msgs))]["msg_id"] - 1
        else:
            overlap_from = 0

        fetched = await fetch_new(client, entity, topic_id, overlap_from, log)

    # Слияние: всё старое до overlap + свежий хвост
    kept = [r for r in old_msgs if r["msg_id"] <= overlap_from]
    merged = kept + fetched

    old_ids_in_tail = {r["msg_id"]: r for r in old_msgs if r["msg_id"] > overlap_from}
    new_count = sum(1 for r in fetched if r["msg_id"] not in old_ids_in_tail)
    changed_count = sum(
        1 for r in fetched
        if r["msg_id"] in old_ids_in_tail and old_ids_in_tail[r["msg_id"]]["text"] != r["text"]
    )
    deleted_count = len(old_ids_in_tail) - (len(fetched) - new_count)

    has_changes = bool(new_count or changed_count or deleted_count)
    if has_changes or not os.path.exists(CACHE_FILE):
        save_cache({"chat_id": chat_id, "topic_id": topic_id, "messages": merged})

    log(f"Сообщений в кэше: {len(merged)} "
        f"(новых: {new_count}, изменённых: {changed_count}, удалённых: {deleted_count})")
    return has_changes, merged


def fetch(log=print):
    """Синхронная обёртка. Возвращает (есть_ли_изменения, список_сообщений)."""
    if not os.path.exists(SESSION + ".session"):
        raise RuntimeError(
            "Сессия Telegram не создана. Запустите один раз СОЗДАТЬ_СЕССИЮ.bat "
            "(понадобится номер телефона и код из Telegram)"
        )
    return asyncio.run(_fetch_async(log))


if __name__ == "__main__":
    fetch()
