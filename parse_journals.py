#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Путь 101% 2026 — Генератор журналов
Парсит экспорт Telegram → создаёт HTML-журналы → публикует на GitHub Pages

Запуск: python parse_journals.py
После нового экспорта чата из Telegram — запусти снова, всё обновится.
"""

import glob
import re
import os
import subprocess
import sys
from datetime import datetime
from collections import defaultdict
from html import escape

# Fix Windows console encoding
if sys.platform == 'win32' and sys.stdout is not None:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── Пути ─────────────────────────────────────────────────────────────────────

EXPORTS_DIR = r"C:\Users\Мансур\Downloads\Telegram Desktop"
OUTPUT_DIR  = r"C:\Users\Мансур\put-101-2026"

# ── Менеджеры ─────────────────────────────────────────────────────────────────

MANAGERS = {
    'Савелий Потапов': {
        'file': 'journal_potapov.html', 'initials': 'СП', 'plan': 458000,
        'color': '#3b82f6', 'grad': '#3b82f6,#1d4ed8',
        'role': 'Менеджер по продажам', 'emoji': '📘',
    },
    'Ната Ковтун': {
        'file': 'journal_nata.html', 'initials': 'НК', 'plan': 1400000,
        'color': '#f5c842', 'grad': '#f5c842,#e8a000',
        'role': 'Менеджер по продажам', 'emoji': '🥇',
    },
    'Сергей Кириллов': {
        'file': 'journal_sergei.html', 'initials': 'СК', 'plan': 1000000,
        'color': '#aab0c0', 'grad': '#aab0c0,#7a8090',
        'role': 'Менеджер по продажам', 'emoji': '🥈',
    },
    'Диана Тагирова': {
        'file': 'journal_diana.html', 'initials': 'ДТ', 'plan': 300000,
        'color': '#cd7f32', 'grad': '#cd7f32,#a05a1a',
        'role': 'Куратор + Менеджер', 'emoji': '🥉',
    },
    'Динара Катунина': {
        'file': 'journal_dinara.html', 'initials': 'ДК', 'plan': 100000,
        'color': '#22c55e', 'grad': '#22c55e,#16a34a',
        'role': 'Менеджер по продажам', 'emoji': '🎯',
    },
    'Оксана Панченкова': {
        'file': 'journal_oksana.html', 'initials': 'ОП', 'plan': 1100000,
        'color': '#64748b', 'grad': '#64748b,#334155',
        'role': 'Менеджер по продажам', 'emoji': '📊',
    },
    'Анастасия Фомина': {
        'file': 'journal_anastasia.html', 'initials': 'АФ', 'plan': 350000,
        'color': '#a855f7', 'grad': '#a855f7,#7c3aed',
        'role': 'Менеджер по продажам', 'emoji': '⭐',
    },
    'Анна Антонова': {
        'file': 'journal_anna_a.html', 'initials': 'АА', 'plan': 300000,
        'color': '#f97316', 'grad': '#f97316,#c2410c',
        'role': 'Менеджер по продажам', 'emoji': '🔥',
    },
    'Анна Кириллова': {
        'file': 'journal_anna_k.html', 'initials': 'АК', 'plan': 200000,
        'color': '#00c9a7', 'grad': '#00c9a7,#007a65',
        'role': 'Менеджер по продажам', 'emoji': '✨',
    },
}

MONTH_RU   = {1:'янв',2:'фев',3:'мар',4:'апр',5:'май',6:'июн',
               7:'июл',8:'авг',9:'сен',10:'окт',11:'ноя',12:'дек'}
MONTH_FULL = {1:'Январь',2:'Февраль',3:'Март',4:'Апрель',5:'Май',6:'Июнь',
               7:'Июль',8:'Август',9:'Сентябрь',10:'Октябрь',11:'Ноябрь',12:'Декабрь'}
WEEKDAY_RU = {0:'Пн',1:'Вт',2:'Ср',3:'Чт',4:'Пт',5:'Сб',6:'Вс'}
WEEKDAY_FULL = {0:'Понедельник',1:'Вторник',2:'Среда',3:'Четверг',
                4:'Пятница',5:'Суббота',6:'Воскресенье'}

# ── Парсинг ───────────────────────────────────────────────────────────────────

def find_latest_export():
    """Самый свежий экспорт именно темы «Путь 101...» в Downloads\\Telegram Desktop."""
    candidates = []
    for folder in glob.glob(os.path.join(EXPORTS_DIR, 'ChatExport_*')):
        path = os.path.join(folder, 'messages.html')
        if not os.path.isfile(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            head = f.read(50_000)
        if 'Путь 101' in head:
            candidates.append(path)
    if not candidates:
        raise FileNotFoundError(
            f"В {EXPORTS_DIR} нет экспортов темы «Путь 101...» (папки ChatExport_* с messages.html)")
    return max(candidates, key=os.path.getmtime)


def messages_from_cache(rows):
    """Конвертирует записи messages_cache.json в формат сообщений парсера."""
    messages = []
    for r in rows:
        dt = datetime.strptime(r['datetime'], '%Y-%m-%d %H:%M:%S')
        messages.append({
            'author':   r['author'],
            'date':     dt.date(),
            'hour':     dt.hour,
            'time_str': dt.strftime('%H:%M'),
            'datetime': dt,
            'text':     r['text'],
        })
    return messages


def parse_export(path):
    """Парсит экспорт. Подхватывает продолжения messages2.html, messages3.html и т.д."""
    folder = os.path.dirname(path)
    parts = sorted(
        glob.glob(os.path.join(folder, 'messages*.html')),
        key=lambda p: int(re.search(r'messages(\d*)\.html', os.path.basename(p)).group(1) or 1),
    )
    messages = []
    for part in parts:
        messages.extend(_parse_export_file(part))
    print(f"  Всего сообщений: {len(messages)}")
    return messages


def _parse_export_file(path):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("Install: pip install beautifulsoup4")
        sys.exit(1)

    print(f"  Читаю: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    messages, current_author = [], None

    for div in soup.find_all('div', class_='message'):
        name_tag = div.find('div', class_='from_name')
        if name_tag:
            current_author = name_tag.get_text(strip=True)
        if not current_author:
            continue

        date_tag = div.find('div', class_='date')
        if not date_tag or not date_tag.get('title'):
            continue
        try:
            raw = re.sub(r'\s*UTC.*', '', date_tag['title']).strip()
            dt  = datetime.strptime(raw, '%d.%m.%Y %H:%M:%S')
        except Exception:
            continue

        text_tag = div.find('div', class_='text')
        if not text_tag:
            continue
        text = text_tag.get_text(separator='\n', strip=True)
        if not text.strip():
            continue

        messages.append({
            'author':   current_author,
            'date':     dt.date(),
            'hour':     dt.hour,
            'time_str': dt.strftime('%H:%M'),
            'datetime': dt,
            'text':     text,
        })

    print(f"  Найдено сообщений: {len(messages)}")
    return messages

# Написания имён, которые не ловятся обычным сопоставлением (латиница и т.п.)
ALIASES = {
    'panchenkova': 'Оксана Панченкова',
}


def find_manager(author):
    author_lo = author.lower().strip()

    # 0. Алиасы (латиница, особые написания)
    for alias, name in ALIASES.items():
        if alias in author_lo:
            return name

    # 1. Точное совпадение
    for name in MANAGERS:
        if name.lower() == author_lo:
            return name

    # 2. Обе части имени присутствуют (защита от "Анна А." vs "Анна К.")
    for name in MANAGERS:
        parts = name.lower().split()
        if len(parts) >= 2 and all(p in author_lo for p in parts):
            return name

    # 3. По фамилии (уникальный идентификатор)
    for name in MANAGERS:
        parts = name.lower().split()
        surname = parts[-1]  # последнее слово = фамилия
        if len(surname) > 4 and surname in author_lo:
            return name

    return None

def classify(msg):
    """morning | evening | other"""
    t  = msg['text'].lower()
    h  = msg['hour']
    MORNING = ['утро для себя', 'утром для себя', 'доброе утро', 'утренн',
                'просыпа', 'зарядк', 'медитац', 'прогулк', 'настрой дня',
                'встала', 'встал', 'подъём', 'вышла', 'вышел']
    EVENING = ['рефлексия', 'итог дня', 'план/факт', 'факт:', 'план факт',
                'результат дня', 'закрыл', 'закрыла', 'подписали',
                'оплатил', 'оплатила', 'итого за день', 'вечерн']

    if any(k in t for k in MORNING) and h < 15:
        return 'morning'
    if any(k in t for k in EVENING):
        return 'evening'
    if h < 11:
        return 'morning'
    if h >= 19:
        return 'evening'
    return 'other'

def extract_amount(texts):
    """Возвращает максимальную сумму из текстов (₽, тыс, к)."""
    amounts = []
    combined = '\n'.join(texts)
    for m in re.finditer(r'(\d[\d\s]{0,9})\s*(?:₽|руб\.?)', combined):
        try:
            v = int(re.sub(r'\s', '', m.group(1)))
            if 1_000 <= v <= 10_000_000:
                amounts.append(v)
        except Exception:
            pass
    for m in re.finditer(r'(\d+(?:[.,]\d+)?)\s*тыс', combined, re.IGNORECASE):
        try:
            v = int(float(m.group(1).replace(',', '.')) * 1000)
            if 1_000 <= v <= 10_000_000:
                amounts.append(v)
        except Exception:
            pass
    for m in re.finditer(r'(?<!\d)(\d{2,4})[кk](?!\w)', combined, re.IGNORECASE):
        try:
            v = int(m.group(1)) * 1000
            if 10_000 <= v <= 10_000_000:
                amounts.append(v)
        except Exception:
            pass
    return max(amounts) if amounts else None

def fmt(v):
    return f"{v:,}".replace(',', ' ') + ' ₽'


def badge_html(amount, plan):
    if not amount:
        return '<span class="fb lo">—</span>'
    p = amount / plan * 100
    s = fmt(amount)
    if p >= 100:
        return f'<span class="fb done">{s} ✓</span>'
    if p >= 15:
        return f'<span class="fb hi">{s}</span>'
    return f'<span class="fb lo">{s}</span>'


def render_msgs(msgs_list):
    parts = []
    for m in msgs_list:
        text_escaped = escape(m['text']).replace('\n', '<br>')
        parts.append(
            f'<div class="msg-item"><span class="msg-time">{m["time_str"]}</span>{text_escaped}</div>'
        )
    return '\n'.join(parts)


def blk(cls, label, msgs_list, extra=''):
    if not msgs_list:
        return ''
    first_time = msgs_list[0]['time_str']
    last_time  = msgs_list[-1]['time_str']
    time_label = first_time if first_time == last_time else f'{first_time}–{last_time}'
    return (
        f'<div class="blk {cls}">'
        f'<div class="blk-lbl"><span class="dot"></span>{label} · {time_label}</div>'
        f'{extra}'
        f'{render_msgs(msgs_list)}'
        f'</div>'
    )


def auto_conclusion(day, msgs, day_amount, plan, morning, evening):
    parts = []
    wd = WEEKDAY_FULL[day.weekday()]
    mon = MONTH_RU[day.month]

    # Morning check
    if morning:
        parts.append('Утренний отчёт сдан вовремя.')
    else:
        parts.append('Утренний отчёт в этот день не зафиксирован.')

    # Evening check
    if evening:
        parts.append('Вечерняя рефлексия есть.')
    else:
        parts.append('Вечерняя рефлексия не зафиксирована.')

    # Money
    if day_amount:
        pct = round(day_amount / plan * 100, 1)
        if pct >= 100:
            parts.append(f'План ЗАКРЫТ — {fmt(day_amount)} ({pct}%). Цель достигнута.')
        elif pct >= 50:
            parts.append(f'Зафиксировано {fmt(day_amount)} ({pct}% плана) — уверенный прогресс.')
        elif pct >= 10:
            parts.append(f'Результат {fmt(day_amount)} ({pct}% плана) — есть задел, нужно ускоряться.')
        else:
            parts.append(f'Зафиксирована сумма {fmt(day_amount)} — небольшой старт.')
    else:
        parts.append('Денежный результат в сообщениях этого дня явно не указан.')

    # Activity
    total = len(msgs)
    if total >= 4:
        parts.append(f'{total} сообщений за день — высокая активность.')
    elif total == 1:
        parts.append('Одно сообщение — краткий контакт с командой.')

    return ' '.join(parts)


# ── Главный запуск ─────────────────────────────────────────────────────────────

def generate_all(messages, log=print, game=None):
    """Генерирует весь сайт «Сезоны»: дашборд, страницы месяцев, журналы.

    game — данные игровой таблицы (game_table.read_game_table);
    если не переданы, читаются здесь.
    """
    import game_table
    import generate_site
    if game is None:
        game = game_table.read_game_table(log)
    return generate_site.build_site(messages, game, log)


def publish(log=print):
    """Коммит и пуш на GitHub — только если есть реальные изменения.

    Возвращает True, если пуш состоялся.
    """
    def git(*args, **kw):
        return subprocess.run(['git', *args], cwd=OUTPUT_DIR, capture_output=True,
                              text=True, encoding='utf-8', errors='replace', **kw)

    status = git('status', '--porcelain')
    if not status.stdout.strip():
        log("Изменений нет — пуш не нужен")
        return False

    git('add', '-A')
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    commit = git('commit', '-m', f'Journals update {ts}')
    if commit.returncode != 0:
        log(f"git commit не прошёл: {commit.stdout} {commit.stderr}")
        return False

    push = git('push')
    if push.returncode != 0:
        log(f"git push не прошёл: {push.stderr}")
        return False

    log("Опубликовано: https://menbestnet-oss.github.io/put-101-2026/ (Pages обновится за 1–2 мин)")
    return True


def main():
    """Запасной путь: генерация из ручного HTML-экспорта Telegram Desktop."""
    print("=" * 60)
    print("  Путь 101% 2026 — Генератор журналов (из HTML-экспорта)")
    print("=" * 60)

    messages = parse_export(find_latest_export())
    if not messages:
        print("  !! Сообщений не найдено (экспорт пустой или ещё не дописан) — ничего не трогаю")
        return
    generate_all(messages)
    publish()


if __name__ == '__main__':
    main()
