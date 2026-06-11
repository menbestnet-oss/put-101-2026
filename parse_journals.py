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

# ── Генерация HTML ─────────────────────────────────────────────────────────────

CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d0d1a;color:#e8e8f0;min-height:100vh}
.hero{background:linear-gradient(135deg,#1a1a3e 0%,#0d0d1a 70%);padding:48px 24px 32px;text-align:center;border-bottom:1px solid rgba(255,255,255,.06)}
.badge{display:inline-block;font-size:11px;font-weight:700;letter-spacing:2px;padding:5px 14px;border-radius:20px;margin-bottom:14px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);text-transform:uppercase}
.avatar{width:72px;height:72px;border-radius:50%;margin:0 auto 14px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#fff}
h1{font-size:clamp(24px,4vw,36px);font-weight:900;color:#fff;margin-bottom:8px}
.hero-sub{font-size:14px;color:#888;margin-bottom:24px}
.stats{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.stat{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px 20px;text-align:center;min-width:100px}
.val{display:block;font-size:20px;font-weight:800;color:#fff}
.val.g{color:#22c55e}.val.a{color:#f5c842}.val.o{color:#f97316}
.lbl{display:block;font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1.5px;margin-top:3px}
.prog-wrap{padding:24px 24px 0;max-width:820px;margin:0 auto}
.prog-card{background:#16162a;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:18px 20px}
.prog-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px}
.prog-title{font-size:13px;font-weight:700;color:#fff}
.prog-pct{font-size:12px;color:#888}
.track{height:10px;background:#1e1e35;border-radius:5px;overflow:hidden;margin-bottom:8px}
.fill{height:100%;border-radius:5px}
.milestones{display:flex;justify-content:space-between;font-size:10px;color:#555}
.main{max-width:820px;margin:0 auto;padding:24px}
.week{display:flex;align-items:center;gap:12px;margin:32px 0 14px}
.week-lbl{font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#555;white-space:nowrap}
.week-line{flex:1;height:1px;background:rgba(255,255,255,.06)}
.card{background:#16162a;border:1px solid rgba(255,255,255,.07);border-radius:14px;margin-bottom:12px;overflow:hidden}
.card-hdr{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;cursor:pointer;gap:12px;user-select:none}
.card-hdr:hover{background:rgba(255,255,255,.02)}
.hdr-l{display:flex;align-items:center;gap:14px;flex:1;min-width:0}
.day-num{text-align:center;min-width:44px}
.day-num .n{display:block;font-size:22px;font-weight:900;color:#fff;line-height:1}
.day-num{font-size:10px;color:#555;text-transform:uppercase}
.card-info h3{font-size:14px;font-weight:700;color:#fff;line-height:1.3}
.card-info .sub{font-size:11px;color:#555;margin-top:2px}
.hdr-r{display:flex;align-items:center;gap:8px;flex-shrink:0}
.fb{font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px}
.fb.z{background:#ef444422;color:#ef4444;border:1px solid #ef444433}
.fb.lo{background:#f9731622;color:#f97316;border:1px solid #f9731633}
.fb.hi{background:#22c55e22;color:#22c55e;border:1px solid #22c55e33}
.fb.done{background:#22c55e11;color:#22c55e;border:2px solid #22c55e}
.tog{font-size:12px;color:#444;transition:.2s;margin-left:4px}
.card-body{padding:0 18px 18px;display:none}
.card.open .card-body{display:block}
.card.open .tog{transform:rotate(180deg)}
.blk{border-radius:10px;padding:14px 16px;margin-bottom:10px}
.blk.mo{background:#1e2a3a;border-left:3px solid #3b82f6}
.blk.ev{background:#1a2a1a;border-left:3px solid #22c55e}
.blk.cn{background:#2a2a1a;border-left:3px solid #f5c842}
.blk.pu{background:#2a1a3a;border-left:3px solid #a855f7}
.blk-lbl{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#555;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block}
.blk.mo .dot{color:#3b82f6}
.blk.ev .dot{color:#22c55e}
.blk.cn .dot{color:#f5c842}
.blk.pu .dot{color:#a855f7}
.msg-item{margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.04);font-size:13px;line-height:1.7;color:#ccc}
.msg-item:last-child{border:none;margin-bottom:0;padding-bottom:0}
.msg-time{display:inline-block;font-size:10px;color:#555;margin-right:8px;font-family:monospace;background:#0d0d1a;padding:1px 6px;border-radius:4px}
.mrow{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.m{background:#0d0d1a;border-radius:8px;padding:8px 12px;min-width:100px}
.ml{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px}
.mv{font-size:14px;font-weight:700;color:#fff}
.mv.a{color:#f5c842}
.final{background:linear-gradient(135deg,#1a1a3e,#0d0d1a);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:28px;margin-top:28px}
.final-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;margin-top:20px}
.fb2{background:#16162a;border-radius:10px;padding:16px}
.fb2 h4{font-size:12px;font-weight:700;color:#fff;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
.fb2 ul{list-style:none;padding:0}
.fb2 li{font-size:12px;color:#888;padding:5px 0;border-bottom:1px solid #111;display:flex;align-items:flex-start;gap:6px}
.fb2 li::before{content:'→';color:#444;flex-shrink:0}
a.back{display:inline-block;margin:20px 24px 0;font-size:12px;color:#555;text-decoration:none;border:1px solid #222;border-radius:8px;padding:6px 14px}
a.back:hover{color:#fff;border-color:#444}
footer{text-align:center;padding:32px;font-size:11px;color:#333}
"""

JS = "function toggle(id){const c=document.getElementById(id);c.classList.toggle('open')}"

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


def make_journal(name, cfg, days_data):
    plan   = cfg['plan']
    grad   = cfg['grad']
    color  = cfg['color']
    emoji  = cfg['emoji']
    all_days = sorted(days_data.keys())
    total_msgs = sum(len(v) for v in days_data.values())

    # Stats
    morning_days = sum(1 for d, ms in days_data.items() if any(classify(m) == 'morning' for m in ms))
    evening_days = sum(1 for d, ms in days_data.items() if any(classify(m) == 'evening' for m in ms))

    # Peak amount
    day_amounts = {}
    for d, ms in days_data.items():
        a = extract_amount([m['text'] for m in ms])
        if a:
            day_amounts[d] = a
    max_fact = max(day_amounts.values()) if day_amounts else 0
    pct_str  = f"{round(max_fact/plan*100,1)}%" if max_fact else "—"
    fill_pct = min(round(max_fact / plan * 100, 1), 130) if max_fact else 0

    # ── Hero ──
    hero = f"""<div class="hero">
  <div class="badge">{emoji} {pct_str} плана</div>
  <div class="avatar" style="background:linear-gradient(135deg,{grad})">{cfg['initials']}</div>
  <h1>{name}</h1>
  <div class="hero-sub">{cfg['role']} · Апрель–Май 2026</div>
  <div class="stats">
    <div class="stat"><span class="val">{fmt(plan)}</span><span class="lbl">План</span></div>
    <div class="stat"><span class="val g">{fmt(max_fact) if max_fact else '—'}</span><span class="lbl">Факт (макс)</span></div>
    <div class="stat"><span class="val {"g" if max_fact >= plan else "o"}">{pct_str}</span><span class="lbl">Выполнение</span></div>
    <div class="stat"><span class="val">{len(all_days)}</span><span class="lbl">Активных дней</span></div>
    <div class="stat"><span class="val">{morning_days}</span><span class="lbl">Утренних отч.</span></div>
    <div class="stat"><span class="val">{evening_days}</span><span class="lbl">Рефлексий</span></div>
  </div>
</div>"""

    # ── Progress ──
    prog = f"""<div class="prog-wrap">
  <div class="prog-card">
    <div class="prog-hdr">
      <span class="prog-title">Прогресс апреля–мая</span>
      <span class="prog-pct">{pct_str} плана · {fmt(max_fact) if max_fact else '—'} при плане {fmt(plan)}</span>
    </div>
    <div class="track"><div class="fill" style="width:{fill_pct}%;background:linear-gradient(90deg,{grad})"></div></div>
    <div class="milestones">
      <span>0 ₽</span><span>{fmt(plan//4)}</span><span>{fmt(plan//2)}</span><span>{fmt(plan)} (план)</span>
    </div>
  </div>
</div>"""

    # ── Day cards ──
    cards = []
    prev_month = None
    cumulative = 0

    for i, day in enumerate(all_days):
        msgs = days_data[day]

        # Month separator
        if day.month != prev_month:
            prev_month = day.month
            cards.append(
                f'<div class="week"><span class="week-lbl">'
                f'{MONTH_FULL[day.month]} {day.year}</span>'
                f'<div class="week-line"></div></div>'
            )

        morning = [m for m in msgs if classify(m) == 'morning']
        evening = [m for m in msgs if classify(m) == 'evening']
        other   = [m for m in msgs if classify(m) == 'other']

        day_amount = day_amounts.get(day)
        if day_amount and day_amount > cumulative:
            growth = day_amount - cumulative
            cumulative = day_amount
        else:
            growth = None

        card_id = f"d{i:03d}"
        mon = MONTH_RU[day.month]
        wd_full = WEEKDAY_FULL[day.weekday()]

        # Metrics row
        mrow = ''
        if day_amount:
            pct_day = round(day_amount / plan * 100, 1)
            g_html = f'<div class="m"><div class="ml">+За день</div><div class="mv a">{fmt(growth)}</div></div>' if growth else ''
            mrow = (
                f'<div class="mrow">'
                f'<div class="m"><div class="ml">Факт</div><div class="mv a">{fmt(day_amount)}</div></div>'
                f'<div class="m"><div class="ml">% плана</div><div class="mv {"a" if pct_day>=100 else ""}">{pct_day}%</div></div>'
                f'{g_html}'
                f'</div>'
            )

        mo_blk = blk('mo', 'Утро для себя', morning)
        ev_blk = blk('ev', 'Рефлексия дня', evening, mrow)
        ot_blk = blk('pu', 'В течение дня', other)

        conclusion_text = auto_conclusion(day, msgs, day_amount, plan, morning, evening)
        cn_blk = (
            f'<div class="blk cn">'
            f'<div class="blk-lbl"><span class="dot"></span>Итоговый вывод</div>'
            f'<div class="msg-item">{conclusion_text}</div>'
            f'</div>'
        )

        checks = f'{"✓ Утро" if morning else "— Утро"} · {"✓ Рефлексия" if evening else "— Рефлексия"} · {len(msgs)} сообщ.'
        open_cls = ' open' if i == 0 else ''

        cards.append(f"""<div class="card{open_cls}" id="{card_id}">
  <div class="card-hdr" onclick="toggle('{card_id}')">
    <div class="hdr-l">
      <div class="day-num"><span class="n">{day.day}</span>{mon}</div>
      <div class="card-info">
        <h3>{wd_full} · {day.strftime('%d.%m.%Y')}</h3>
        <div class="sub">{checks}</div>
      </div>
    </div>
    <div class="hdr-r">{badge_html(day_amount, plan)}<span class="tog">▼</span></div>
  </div>
  <div class="card-body">
    {mo_blk}
    {ev_blk}
    {ot_blk}
    {cn_blk}
  </div>
</div>""")

    # ── Final verdict ──
    best_day = max(day_amounts, key=day_amounts.get) if day_amounts else None
    streak = morning_days

    final = f"""<div class="final">
  <div style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:{color};margin-bottom:8px">Итоговый вывод по менеджеру</div>
  <div style="font-size:22px;font-weight:800;color:#fff;margin-bottom:22px;line-height:1.3">
    {name} — апрель–май 2026<br>
    {emoji} {pct_str} · {fmt(max_fact) if max_fact else '—'}
  </div>
  <div class="final-grid">
    <div class="fb2"><h4>Статистика</h4><ul>
      <li>Активных дней: {len(all_days)}</li>
      <li>Всего сообщений: {total_msgs}</li>
      <li>Утренних отчётов: {morning_days} из {len(all_days)}</li>
      <li>Вечерних рефлексий: {evening_days} из {len(all_days)}</li>
      {f'<li>Лучший день: {best_day.strftime("%d.%m")} — {fmt(day_amounts[best_day])}</li>' if best_day else ''}
    </ul></div>
    <div class="fb2"><h4>Результаты</h4><ul>
      <li>План: {fmt(plan)}</li>
      <li>Факт (макс): {fmt(max_fact) if max_fact else '—'}</li>
      <li>Выполнение: {pct_str}</li>
      {'<li>✅ ПЛАН ЗАКРЫТ</li>' if max_fact >= plan else '<li>⚠ До плана: ' + fmt(plan - max_fact) + '</li>'}
    </ul></div>
  </div>
</div>"""

    updated = datetime.now().strftime('%d.%m.%Y %H:%M')
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} · Путь 101% 2026</title>
<style>{CSS}</style>
</head>
<body>
<a href="index.html" class="back">← Все менеджеры</a>
{hero}
{prog}
<div class="main">
{''.join(cards)}
{final}
</div>
<footer>Журнал обновлён {updated} · Путь 101% 2026</footer>
<script>{JS}</script>
</body>
</html>"""


# ── Главная страница ───────────────────────────────────────────────────────────

def make_index(managers_stats):
    """Генерирует index.html с карточками всех менеджеров"""
    COLORS = {
        'Ната Ковтун':      ('#f5c842','#e8a000','НК','🥇'),
        'Сергей Кириллов':  ('#aab0c0','#7a8090','СК','🥈'),
        'Диана Тагирова':   ('#cd7f32','#a05a1a','ДТ','🥉'),
        'Динара Катунина':  ('#22c55e','#16a34a','ДК','🎯'),
        'Савелий Потапов':  ('#3b82f6','#1d4ed8','СП','📘'),
        'Анна Антонова':    ('#f97316','#c2410c','АА','🔥'),
        'Анна Кириллова':   ('#00c9a7','#007a65','АК','✨'),
        'Анастасия Фомина': ('#a855f7','#7c3aed','АФ','⭐'),
        'Оксана Панченкова':('#64748b','#334155','ОП','📊'),
    }
    cards = []
    for name, cfg in MANAGERS.items():
        stats = managers_stats.get(name, {})
        c1, c2, ini, emo = COLORS.get(name, ('#666','#333','??','•'))
        fact = stats.get('max_fact', 0)
        plan = cfg['plan']
        pct  = round(fact / plan * 100, 1) if fact else 0
        days = stats.get('days', 0)
        file = cfg['file']

        fill = min(pct, 130)
        fact_html = fmt(fact) if fact else '—'
        pct_html  = f"{pct}%" if pct else '—'

        cards.append(f"""<a class="card" href="{file}">
  <div class="card-top">
    <div class="av" style="background:linear-gradient(135deg,{c1},{c2})">{ini}</div>
    <div class="card-meta">
      <div class="card-name">{name}</div>
      <div class="card-role">{cfg['role']}</div>
      <span class="badge-sm" style="background:{c1}22;color:{c1};border:1px solid {c1}44">{emo} {pct_html}</span>
    </div>
  </div>
  <div class="card-body">
    <div class="card-nums">
      <div class="cn-item"><div class="cn-val">{fmt(plan)}</div><div class="cn-lbl">План</div></div>
      <div class="cn-item"><div class="cn-val" style="color:{c1}">{fact_html}</div><div class="cn-lbl">Факт</div></div>
    </div>
    <div class="prog-bar"><div class="prog-fill" style="width:{fill}%;background:linear-gradient(90deg,{c1},{c2})"></div></div>
    <div class="prog-info"><span>{days} дней активности</span><span style="color:{c1}">{pct_html}</span></div>
  </div>
</a>""")

    updated = datetime.now().strftime('%d.%m.%Y %H:%M')
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Путь 101% 2026 — Команда</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0d0d1a;color:#e8e8f0;min-height:100vh}}
.hero{{background:linear-gradient(135deg,#1a1a3e 0%,#0d0d1a 60%,#1a0d2e 100%);padding:56px 24px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,.07)}}
.hero-tag{{font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#7b7bff;margin-bottom:12px}}
.hero h1{{font-size:clamp(28px,5vw,48px);font-weight:900;color:#fff;line-height:1.15;margin-bottom:10px}}
.hero-sub{{font-size:16px;color:#9999cc;margin-bottom:32px}}
.hero-stats{{display:flex;gap:32px;justify-content:center;flex-wrap:wrap}}
.hs .v{{font-size:28px;font-weight:800;color:#fff;display:block}}
.hs .l{{font-size:11px;color:#666;text-transform:uppercase;letter-spacing:1.5px;margin-top:2px;display:block}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px;padding:40px 24px;max-width:1200px;margin:0 auto}}
.card{{background:#16162a;border:1px solid rgba(255,255,255,.07);border-radius:16px;overflow:hidden;transition:transform .2s,box-shadow .2s;text-decoration:none;display:block;color:inherit}}
.card:hover{{transform:translateY(-4px);box-shadow:0 12px 40px rgba(0,0,0,.4)}}
.card-top{{padding:22px 20px 14px;display:flex;align-items:flex-start;gap:14px}}
.av{{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;color:#fff;flex-shrink:0}}
.card-meta{{flex:1}}
.card-name{{font-size:17px;font-weight:700;color:#fff;line-height:1.2;margin-bottom:4px}}
.card-role{{font-size:12px;color:#555;margin-bottom:8px}}
.badge-sm{{display:inline-block;font-size:10px;font-weight:700;letter-spacing:1px;padding:3px 8px;border-radius:20px;text-transform:uppercase}}
.card-body{{padding:0 20px 20px}}
.card-nums{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}}
.cn-item{{background:#0d0d1a;border-radius:8px;padding:8px 10px}}
.cn-val{{font-size:14px;font-weight:800;color:#fff}}
.cn-lbl{{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1px;margin-top:1px}}
.prog-bar{{height:6px;background:#1e1e35;border-radius:3px;overflow:hidden;margin-bottom:6px}}
.prog-fill{{height:100%;border-radius:3px}}
.prog-info{{display:flex;justify-content:space-between;font-size:11px;color:#555}}
footer{{text-align:center;padding:32px 24px;font-size:12px;color:#333;border-top:1px solid #111}}
</style>
</head>
<body>
<div class="hero">
  <div class="hero-tag">Апрель–Май 2026</div>
  <h1>Путь 101% 2026</h1>
  <div class="hero-sub">Личные журналы команды менеджеров</div>
  <div class="hero-stats">
    <div class="hs"><span class="v">9</span><span class="l">Менеджеров</span></div>
    <div class="hs"><span class="v">101%</span><span class="l">Цель</span></div>
    <div class="hs"><span class="v">{updated}</span><span class="l">Обновлено</span></div>
  </div>
</div>
<div class="grid">{''.join(cards)}</div>
<footer>Путь 101% 2026 · Журналы команды · Апрель–Май 2026</footer>
</body>
</html>"""


# ── Главный запуск ─────────────────────────────────────────────────────────────

def generate_all(messages, log=print):
    """Группирует сообщения, генерирует все журналы + index.html.

    Возвращает (managers_stats, unmatched) — статистику и авторов без совпадения.
    """
    grouped = defaultdict(lambda: defaultdict(list))
    unmatched = set()
    for msg in messages:
        name = find_manager(msg['author'])
        if name:
            grouped[name][msg['date']].append(msg)
        else:
            unmatched.add(msg['author'])

    if unmatched:
        log(f"Авторы без совпадения (пропущены): {', '.join(sorted(unmatched))}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    managers_stats = {}

    for name, cfg in MANAGERS.items():
        days_data = dict(grouped.get(name, {}))
        if not days_data:
            log(f"!! {name}: сообщений не найдено — пропускаю")
            continue

        total = sum(len(v) for v in days_data.values())
        day_amounts = {}
        for d, ms in days_data.items():
            a = extract_amount([m['text'] for m in ms])
            if a:
                day_amounts[d] = a
        max_fact = max(day_amounts.values()) if day_amounts else 0

        managers_stats[name] = {'days': len(days_data), 'total': total, 'max_fact': max_fact}
        log(f"OK {name}: {len(days_data)} дней, {total} сообщ., факт {fmt(max_fact) if max_fact else '---'}")

        html = make_journal(name, cfg, days_data)
        with open(os.path.join(OUTPUT_DIR, cfg['file']), 'w', encoding='utf-8') as f:
            f.write(html)

    index_html = make_index(managers_stats)
    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)
    log("OK index.html обновлён")

    return managers_stats, unmatched


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
