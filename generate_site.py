#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Путь 101% 2026 — Генерация сайта «Сезоны»

Три уровня страниц:
  index.html        — живой дашборд: текущий месяц, лидерборд, тревоги, архив сезонов
  month_YYYY-MM.html — страница месяца: подиум, полная таблица, рекорды
  journal_*.html    — журнал менеджера с переключателем месяцев (дневник сохраняется)

Источники данных:
  - messages (Telegram, через fetch_telegram) — дневники, деньги, активность
  - game (Excel «Игра Путь 101%», через game_table) — баллы, официальные итоги
"""

import calendar
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, date

from parse_journals import (
    MANAGERS, MONTH_RU, MONTH_FULL, WEEKDAY_FULL, OUTPUT_DIR,
    find_manager, classify, extract_amount, fmt, blk, badge_html, auto_conclusion,
)

SITE_URL = "https://menbestnet-oss.github.io/put-101-2026/"


# ── Подготовка данных ─────────────────────────────────────────────────────────

def month_key(d):
    return f"{d.year}-{d.month:02d}"


def month_title(mk):
    y, m = mk.split('-')
    return f"{MONTH_FULL[int(m)]} {y}"


MONTH_GEN = {1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
             7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'}


def month_gen(mk):
    return MONTH_GEN[int(mk.split('-')[1])]


def short(name):
    """Короткое имя; если имена совпадают (две Анны) — добавляем инициал фамилии."""
    parts = name.split()
    twins = [n for n in MANAGERS if n != name and n.split()[0] == parts[0]]
    return f"{parts[0]} {parts[-1][0]}." if twins and len(parts) > 1 else parts[0]


# ── Планы месяца из сообщений ─────────────────────────────────────────────────
# Менеджеры объявляют план в утренних отчётах: «План месяца: 450к», «План: 500.000»

PLAN_LINE = re.compile(r'^\s*план(?:\s+месяца|\s+на\s+месяц)?\s*[:\-–—]?\s*(.*)', re.IGNORECASE)
PLAN_SKIP = re.compile(r'день|дня|дню|недел|нед\b', re.IGNORECASE)


def parse_plan_amount(s):
    mln = re.match(r'(\d+(?:[.,]\d+)?)\s*(?:млн|миллион)', s, re.IGNORECASE)
    if mln:
        v = int(float(mln.group(1).replace(',', '.')) * 1_000_000)
        return v if 10_000 <= v <= 20_000_000 else None
    m = re.match(r'(\d[\d\s .,]*)\s*(к|k|тыс)?', s, re.IGNORECASE)
    if not m:
        return None
    digits = re.sub(r'[\s .,]', '', m.group(1))
    if not digits:
        return None
    v = int(digits)
    if m.group(2) and v < 10_000:
        v *= 1000
    return v if 10_000 <= v <= 20_000_000 else None


def plan_from_msgs(msgs):
    """Самый часто объявляемый план месяца в сообщениях (None, если не объявлен)."""
    counter = Counter()
    for msg in msgs:
        for line in msg['text'].split('\n'):
            mm = PLAN_LINE.match(line)
            if not mm or PLAN_SKIP.search(line):
                continue
            v = parse_plan_amount(mm.group(1))
            if v:
                counter[v] += 1
    return counter.most_common(1)[0][0] if counter else None


def fmt_mln(v):
    if v >= 1_000_000:
        s = f"{v / 1_000_000:.1f}".rstrip('0').rstrip('.').replace('.', ',')
        return f"{s} млн ₽"
    return fmt(v)


def prep_data(messages, game):
    """Сводит Telegram и Excel в одну структуру по менеджерам и месяцам."""
    # game: {'2026-04': {'Ковтун Ната': {...}}} → канонические имена
    game_by_name = defaultdict(dict)   # name -> month -> {total, days, plan_bonus}
    for mk, managers in game.items():
        for raw, info in managers.items():
            name = find_manager(raw)
            if name:
                game_by_name[name][mk] = info

    # Сезоны = месяцы из игровой таблицы; ранние «чужие» сообщения
    # (например, 30-31 марта — старт игры) приклеиваются к ближайшему сезону.
    # Месяцы ПОЗЖЕ последнего листа Excel становятся сезонами сами
    # (иначе июльские сообщения попадали бы в июнь, пока нет листа «Июль»).
    msg_months = {month_key(m['date']) for m in messages}
    game_months = sorted(game.keys())
    if game_months:
        months = sorted(set(game_months) | {mk for mk in msg_months if mk > game_months[-1]})
    else:
        months = sorted(msg_months)

    def season_of(mk):
        if mk in months:
            return mk
        later = [m for m in months if m > mk]
        return later[0] if later else months[-1]

    msgs_by_name = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    unmatched = set()
    for msg in messages:
        name = find_manager(msg['author'])
        if not name:
            unmatched.add(msg['author'])
            continue
        msgs_by_name[name][season_of(month_key(msg['date']))][msg['date']].append(msg)

    data = {}  # name -> month -> info
    for name in MANAGERS:
        data[name] = {}
        for mk in months:
            days = dict(msgs_by_name.get(name, {}).get(mk, {}))
            money_by_day = {}
            for d, ms in days.items():
                a = extract_amount([m['text'] for m in ms])
                if a:
                    money_by_day[d] = a
            g = game_by_name.get(name, {}).get(mk, {})
            all_msgs = [m for ms in days.values() for m in ms]
            data[name][mk] = {
                'days': days,
                'money_by_day': money_by_day,
                'money': max(money_by_day.values()) if money_by_day else 0,
                'points': g.get('total', 0.0),
                'points_by_day': g.get('days', {}),
                'plan_bonus': bool(g.get('plan_bonus')),
                'plan': plan_from_msgs(all_msgs),
            }

        # План не объявлен → берём из прошлого месяца, в крайнем случае из конфига
        carry = None
        for mk in months:
            info = data[name][mk]
            if info['plan']:
                carry = info['plan']
                info['plan_source'] = 'chat'
            elif carry:
                info['plan'] = carry
                info['plan_source'] = 'prev'
            else:
                info['plan'] = MANAGERS[name]['plan']
                info['plan_source'] = 'config'

    # Места по баллам в каждом месяце
    boards = {}  # month -> [(name, points)]
    for mk in months:
        board = sorted(
            ((n, data[n][mk]['points']) for n in MANAGERS),
            key=lambda x: -x[1],
        )
        boards[mk] = board
        for place, (n, pts) in enumerate(board, 1):
            data[n][mk]['place'] = place if pts > 0 else None

    return data, months, boards, unmatched


def month_team_stats(data, mk):
    points_total = sum(data[n][mk]['points'] for n in MANAGERS)
    money_total = sum(data[n][mk]['money'] for n in MANAGERS)
    active = sum(1 for n in MANAGERS if data[n][mk]['days'] or data[n][mk]['points'])
    return points_total, money_total, active


def best_money_day(data, mk):
    best = None
    for n in MANAGERS:
        for d, v in data[n][mk]['money_by_day'].items():
            if not best or v > best[2]:
                best = (n, d, v)
    return best


def morning_streak(day_set, upto):
    """Сколько дней подряд (заканчивая вчера/сегодня) менеджер был активен."""
    streak, d = 0, upto
    while d in day_set or (streak == 0 and d == upto):
        if d in day_set:
            streak += 1
        elif streak == 0:
            d = date.fromordinal(d.toordinal() - 1)
            if d not in day_set:
                break
            continue
        d = date.fromordinal(d.toordinal() - 1)
    return streak


def build_alerts(data, mk, today):
    """Тревоги и стрики текущего месяца."""
    alerts, streaks = [], []
    for n in MANAGERS:
        all_days = set()
        for mk2 in data[n]:
            all_days |= set(data[n][mk2]['days'].keys())
        if not all_days:
            continue
        last = max(all_days)
        silent = (today - last).days
        if silent >= 2:
            alerts.append((silent, f"{short(n)}: {silent} дн. без сообщений"))
        else:
            s = morning_streak(all_days, today)
            if s >= 3:
                streaks.append((s, f"{short(n)}: стрик {s} дн."))
    alerts.sort(reverse=True)
    streaks.sort(reverse=True)
    return [a[1] for a in alerts], [s[1] for s in streaks[:2]]


# ── Стили ─────────────────────────────────────────────────────────────────────

CSS = """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d0d1a;color:#e8e8f0;min-height:100vh}
a{color:inherit;text-decoration:none}
.nav{display:flex;gap:8px;flex-wrap:wrap;padding:16px 24px;border-bottom:1px solid rgba(255,255,255,.06);align-items:center}
.nav a{font-size:12px;color:#888;border:1px solid #222;border-radius:8px;padding:6px 14px}
.nav a:hover{color:#fff;border-color:#444}
.nav a.act{color:#fff;background:#1e1e3a;border-color:#3b3b6a}
.hero{background:linear-gradient(135deg,#1a1a3e 0%,#0d0d1a 70%);padding:40px 24px 28px;text-align:center;border-bottom:1px solid rgba(255,255,255,.06)}
.hero-tag{font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:#7b7bff;margin-bottom:10px}
h1{font-size:clamp(24px,4vw,38px);font-weight:900;color:#fff;margin-bottom:8px}
.hero-sub{font-size:14px;color:#9999cc}
.wrap{max-width:980px;margin:0 auto;padding:24px}
.sect{font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#555;margin:28px 0 12px;display:flex;align-items:center;gap:10px}
.sect::after{content:'';flex:1;height:1px;background:rgba(255,255,255,.06)}
.cards4{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.mcard{background:#16162a;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px 16px}
.mcard .l{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1.5px}
.mcard .v{font-size:21px;font-weight:800;color:#fff;margin-top:3px}
.mcard .v.g{color:#22c55e}.mcard .v.a{color:#f5c842}.mcard .v.o{color:#f97316}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.chip{font-size:12px;padding:5px 12px;border-radius:20px;font-weight:600}
.chip.red{background:#ef444418;color:#ef4444;border:1px solid #ef444433}
.chip.grn{background:#22c55e18;color:#22c55e;border:1px solid #22c55e33}
.board{background:#16162a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:18px 20px}
.brow{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:13px}
.brow:last-child{border:none}
.brow .pl{width:26px;text-align:center;font-weight:800;color:#555}
.brow .pl.p1{color:#f5c842}.brow .pl.p2{color:#aab0c0}.brow .pl.p3{color:#cd7f32}
.brow .nm{width:170px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.brow .bar{flex:1;height:8px;background:#1e1e35;border-radius:4px;overflow:hidden}
.brow .bar i{display:block;height:100%;border-radius:4px}
.brow .pts{width:120px;text-align:right;color:#aaa;font-variant-numeric:tabular-nums}
.brow .bn{font-size:10px;background:#f5c84218;color:#f5c842;border:1px solid #f5c84233;border-radius:10px;padding:2px 8px;white-space:nowrap}
.seasons{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.season{background:#16162a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:18px 20px;display:block;transition:transform .15s}
.season:hover{transform:translateY(-3px);border-color:rgba(255,255,255,.18)}
.season .hd{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px}
.season .ttl{font-size:16px;font-weight:800;color:#fff}
.season .st{font-size:10px;padding:3px 9px;border-radius:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase}
.season .st.done{background:#22c55e18;color:#22c55e;border:1px solid #22c55e33}
.season .st.live{background:#7b7bff18;color:#7b7bff;border:1px solid #7b7bff33}
.season .pod{font-size:13px;color:#ccc;line-height:2}
.season .ft{font-size:11px;color:#555;margin-top:10px;border-top:1px solid rgba(255,255,255,.05);padding-top:10px}
.medal{display:inline-block;width:18px;text-align:center}
.podium{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:8px}
.pcard{border-radius:14px;padding:22px 18px;text-align:center;background:#16162a;border:1px solid rgba(255,255,255,.07)}
.pcard.p1{border-color:#f5c84266;background:linear-gradient(180deg,#f5c84212,#16162a)}
.pcard.p2{border-color:#aab0c044}
.pcard.p3{border-color:#cd7f3244}
.pcard .pm{font-size:30px}
.pcard .pn{font-size:15px;font-weight:800;color:#fff;margin:8px 0 2px}
.pcard .pp{font-size:12px;color:#888}
.pcard .pv{font-size:22px;font-weight:900;margin-top:8px}
.pcard.p1 .pv{color:#f5c842}.pcard.p2 .pv{color:#aab0c0}.pcard.p3 .pv{color:#cd7f32}
table.mt{width:100%;border-collapse:collapse;font-size:13px}
table.mt th{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#555;text-align:left;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.08)}
table.mt td{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.04);color:#ccc}
table.mt tr:last-child td{border:none}
table.mt .r{text-align:right;font-variant-numeric:tabular-nums}
.mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.mg{background:#16162a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:16px;display:block;transition:transform .15s}
.mg:hover{transform:translateY(-3px);border-color:rgba(255,255,255,.18)}
.mg .top{display:flex;gap:12px;align-items:center;margin-bottom:10px}
.mg .av{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;color:#fff;flex-shrink:0}
.mg .nm{font-size:14px;font-weight:700;color:#fff}
.mg .rl{font-size:11px;color:#555}
.mg .row{display:flex;justify-content:space-between;font-size:12px;color:#888;padding:3px 0}
.mg .row b{color:#fff}
.tabs{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin:18px 0 6px}
.tab{font-size:13px;font-weight:600;color:#888;border:1px solid #222;border-radius:10px;padding:8px 18px;cursor:pointer;user-select:none}
.tab:hover{color:#fff;border-color:#444}
.tab.act{color:#fff;background:#1e1e3a;border-color:#3b3b6a}
.msec{display:none}
.msec.act{display:block}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}
.bdg{font-size:11px;font-weight:700;padding:4px 11px;border-radius:14px}
.bdg.gold{background:#f5c84218;color:#f5c842;border:1px solid #f5c84244}
.bdg.grn{background:#22c55e18;color:#22c55e;border:1px solid #22c55e44}
.bdg.pur{background:#a855f718;color:#a855f7;border:1px solid #a855f744}
.avatar{width:72px;height:72px;border-radius:50%;margin:0 auto 14px;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:#fff}
.stats{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-top:18px}
.stat{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:12px 18px;text-align:center;min-width:96px}
.val{display:block;font-size:19px;font-weight:800;color:#fff}
.val.g{color:#22c55e}.val.a{color:#f5c842}
.lbl{display:block;font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1.5px;margin-top:3px}
.week{display:flex;align-items:center;gap:12px;margin:26px 0 12px}
.week-lbl{font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#555;white-space:nowrap}
.week-line{flex:1;height:1px;background:rgba(255,255,255,.06)}
.card{background:#16162a;border:1px solid rgba(255,255,255,.07);border-radius:14px;margin-bottom:12px;overflow:hidden}
.card-hdr{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;cursor:pointer;gap:12px;user-select:none}
.card-hdr:hover{background:rgba(255,255,255,.02)}
.hdr-l{display:flex;align-items:center;gap:14px;flex:1;min-width:0}
.day-num{text-align:center;min-width:44px;font-size:10px;color:#555;text-transform:uppercase}
.day-num .n{display:block;font-size:21px;font-weight:900;color:#fff;line-height:1}
.card-info h3{font-size:14px;font-weight:700;color:#fff;line-height:1.3}
.card-info .sub{font-size:11px;color:#555;margin-top:2px}
.hdr-r{display:flex;align-items:center;gap:8px;flex-shrink:0;flex-wrap:wrap;justify-content:flex-end}
.fb{font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px}
.fb.z{background:#ef444422;color:#ef4444;border:1px solid #ef444433}
.fb.lo{background:#f9731622;color:#f97316;border:1px solid #f9731633}
.fb.hi{background:#22c55e22;color:#22c55e;border:1px solid #22c55e33}
.fb.done{background:#22c55e11;color:#22c55e;border:2px solid #22c55e}
.fb.pts{background:#7b7bff18;color:#9b9bff;border:1px solid #7b7bff33}
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
.blk.mo .dot{color:#3b82f6}.blk.ev .dot{color:#22c55e}.blk.cn .dot{color:#f5c842}.blk.pu .dot{color:#a855f7}
.msg-item{margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.04);font-size:13px;line-height:1.7;color:#ccc}
.msg-item:last-child{border:none;margin-bottom:0;padding-bottom:0}
.msg-time{display:inline-block;font-size:10px;color:#555;margin-right:8px;font-family:monospace;background:#0d0d1a;padding:1px 6px;border-radius:4px}
.mrow{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
.m{background:#0d0d1a;border-radius:8px;padding:8px 12px;min-width:100px}
.ml{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px}
.mv{font-size:14px;font-weight:700;color:#fff}
.mv.a{color:#f5c842}
footer{text-align:center;padding:32px;font-size:11px;color:#333}
@media(max-width:640px){.brow .nm{width:110px}.brow .pts{width:90px}}
"""

JS_ACCORDION = "function toggle(id){document.getElementById(id).classList.toggle('open')}"

JS_TABS = """\
function showMonth(mk){
  document.querySelectorAll('.msec').forEach(function(s){s.classList.remove('act')});
  document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('act')});
  var sec=document.getElementById('m'+mk); if(sec)sec.classList.add('act');
  var tab=document.getElementById('t'+mk); if(tab)tab.classList.add('act');
}
(function(){
  var h=location.hash.replace('#m','');
  if(h && document.getElementById('m'+h)) showMonth(h);
})();
"""


def page(title, body, nav_html='', extra_js=''):
    updated = datetime.now().strftime('%d.%m.%Y %H:%M')
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
{nav_html}
{body}
<footer>Обновлено {updated} · Путь 101% 2026 · обновляется автоматически</footer>
<script>{JS_ACCORDION}
{extra_js}</script>
</body>
</html>"""


def nav(months, active=''):
    links = [f'<a href="index.html"{" class=act" if active == "index" else ""}>Главная</a>']
    for mk in months:
        cls = ' class=act' if active == mk else ''
        links.append(f'<a href="month_{mk}.html"{cls}>{month_title(mk)}</a>')
    return '<div class="nav">' + ''.join(links) + '</div>'


MEDALS = {1: '🥇', 2: '🥈', 3: '🥉'}


# ── Главная: дашборд ──────────────────────────────────────────────────────────

def make_index(data, months, boards, today):
    cur = months[-1]
    board = boards[cur]
    leader_pts = board[0][1] or 1
    points_total, money_total, _ = month_team_stats(data, cur)
    days_in_month = calendar.monthrange(*[int(x) for x in cur.split('-')])[1]
    days_left = max(0, days_in_month - today.day) if month_key(today) == cur else 0
    alerts, streaks = build_alerts(data, cur, today) if month_key(today) == cur else ([], [])

    # Лидерборд текущего месяца
    rows = []
    for place, (n, pts) in enumerate(board, 1):
        cfg = MANAGERS[n]
        info = data[n][cur]
        w = round(pts / leader_pts * 100) if pts else 0
        pl_cls = f' p{place}' if place <= 3 else ''
        bonus = '<span class="bn">+101 план</span>' if info['plan_bonus'] else ''
        money = f" · {fmt(info['money'])}" if info['money'] else ''
        rows.append(
            f'<a class="brow" href="{cfg["file"]}#m{cur}">'
            f'<span class="pl{pl_cls}">{MEDALS.get(place, place)}</span>'
            f'<span class="nm">{n}</span>'
            f'<span class="bar"><i style="width:{w}%;background:linear-gradient(90deg,{cfg["grad"]})"></i></span>'
            f'{bonus}'
            f'<span class="pts">{pts:.0f} б.{money}</span>'
            f'</a>'
        )

    chips = ''.join(f'<span class="chip red">⚠ {a}</span>' for a in alerts)
    chips += ''.join(f'<span class="chip grn">🔥 {s}</span>' for s in streaks)
    chips_html = f'<div class="chips">{chips}</div>' if chips else ''

    # Архив сезонов
    seasons = []
    for mk in reversed(months):
        b = boards[mk]
        pts_total, mon_total, _ = month_team_stats(data, mk)
        live = mk == month_key(today)
        st = '<span class="st live">идёт сейчас</span>' if live else '<span class="st done">завершён</span>'
        pod = ''.join(
            f'<div><span class="medal">{MEDALS[i+1]}</span> {n} — <b style="color:#fff">{p:.0f} б.</b></div>'
            for i, (n, p) in enumerate(b[:3]) if p > 0
        ) or '<div style="color:#555">пока нет баллов</div>'
        bd = best_money_day(data, mk)
        rec = f"рекорд дня: {short(bd[0])}, {fmt(bd[2])} ({bd[1].strftime('%d.%m')})" if bd else 'денежных рекордов нет'
        seasons.append(f"""<a class="season" href="month_{mk}.html">
  <div class="hd"><span class="ttl">{month_title(mk)}</span>{st}</div>
  <div class="pod">{pod}</div>
  <div class="ft">Команда: {pts_total:.0f} баллов · деньги: {fmt(mon_total)} · {rec}</div>
</a>""")

    # Менеджеры
    mcards = []
    for n, cfg in MANAGERS.items():
        info = data[n][cur]
        total_days = sum(len(data[n][mk]['days']) for mk in months)
        mcards.append(f"""<a class="mg" href="{cfg['file']}">
  <div class="top">
    <div class="av" style="background:linear-gradient(135deg,{cfg['grad']})">{cfg['initials']}</div>
    <div><div class="nm">{n}</div><div class="rl">{cfg['role']}</div></div>
  </div>
  <div class="row"><span>{month_title(cur).split()[0]}: баллы</span><b>{info['points']:.0f}{f" · {MEDALS.get(info['place'], '')}" if info.get('place') and info['place'] <= 3 else ''}</b></div>
  <div class="row"><span>Деньги месяца</span><b>{fmt(info['money']) if info['money'] else '—'}</b></div>
  <div class="row"><span>Дней в дневнике</span><b>{total_days}</b></div>
</a>""")

    body = f"""<div class="hero">
  <div class="hero-tag">Игра отдела продаж</div>
  <h1>Путь 101% 2026</h1>
  <div class="hero-sub">Журналы команды · баллы, дневники и победы по месяцам</div>
</div>
<div class="wrap">
  <div class="sect">{month_title(cur)} — текущее положение</div>
  <div class="cards4">
    <div class="mcard"><div class="l">Лидер месяца</div><div class="v a">{short(board[0][0])} · {board[0][1]:.0f} б.</div></div>
    <div class="mcard"><div class="l">Баллы команды</div><div class="v">{points_total:.0f}</div></div>
    <div class="mcard"><div class="l">Деньги: факт / план</div><div class="v g">{fmt_mln(money_total) if money_total else '—'} <span style="color:#555;font-size:14px">/ {fmt_mln(sum(data[n][cur]['plan'] or 0 for n in MANAGERS))}</span></div></div>
    <div class="mcard"><div class="l">До конца месяца</div><div class="v">{days_left} дн.</div></div>
  </div>
  {chips_html}
  <div class="sect">Лидерборд {month_gen(cur)} · по баллам игры</div>
  <div class="board">{''.join(rows)}</div>
  <div class="sect">Сезоны</div>
  <div class="seasons">{''.join(seasons)}</div>
  <div class="sect">Журналы менеджеров</div>
  <div class="mgrid">{''.join(mcards)}</div>
</div>"""
    return page('Путь 101% 2026 — Команда', body, nav(months, 'index'))


# ── Страница месяца ───────────────────────────────────────────────────────────

def make_month_page(data, months, boards, mk, today):
    board = boards[mk]
    live = mk == month_key(today)
    pts_total, mon_total, _ = month_team_stats(data, mk)

    podium = []
    for i, (n, pts) in enumerate(board[:3]):
        if pts <= 0:
            continue
        cfg = MANAGERS[n]
        place = i + 1
        podium.append(f"""<div class="pcard p{place}">
  <div class="pm">{MEDALS[place]}</div>
  <div class="pn">{n}</div>
  <div class="pp">{cfg['role']}</div>
  <div class="pv">{pts:.0f} баллов</div>
</div>""")

    trows = []
    for place, (n, pts) in enumerate(board, 1):
        info = data[n][mk]
        cfg = MANAGERS[n]
        bonus = ' <span class="bn">+101</span>' if info['plan_bonus'] else ''
        plan_m = info['plan']
        pct = round(info['money'] / plan_m * 100) if info['money'] and plan_m else 0
        pct_html = f'<span style="color:{"#22c55e" if pct >= 100 else "#888"}">{pct}%</span>' if pct else '—'
        trows.append(
            f'<tr><td>{MEDALS.get(place, place)}</td>'
            f'<td><a href="{cfg["file"]}#m{mk}" style="color:#fff;font-weight:600">{n}</a></td>'
            f'<td class="r">{pts:.0f}{bonus}</td>'
            f'<td class="r">{fmt(info["money"]) if info["money"] else "—"}</td>'
            f'<td class="r">{fmt(plan_m) if plan_m else "—"}</td>'
            f'<td class="r">{pct_html}</td>'
            f'<td class="r">{len(info["days"])}</td></tr>'
        )

    bd = best_money_day(data, mk)
    recs = []
    if bd:
        recs.append(f'<div class="mcard"><div class="l">Лучший денежный день</div><div class="v a">{short(bd[0])} · {fmt(bd[2])}</div></div>')
    most_active = max(MANAGERS, key=lambda n: len(data[n][mk]['days']))
    if data[most_active][mk]['days']:
        recs.append(f'<div class="mcard"><div class="l">Самый активный дневник</div><div class="v">{short(most_active)} · {len(data[most_active][mk]["days"])} дн.</div></div>')
    bonus_names = [short(n) for n in MANAGERS if data[n][mk]['plan_bonus']]
    if bonus_names:
        recs.append(f'<div class="mcard"><div class="l">Закрыли план месяца</div><div class="v g">{", ".join(bonus_names)}</div></div>')
    recs.append(f'<div class="mcard"><div class="l">Команда за месяц</div><div class="v">{pts_total:.0f} б. · {fmt(mon_total) if mon_total else "—"}</div></div>')

    status = 'идёт сейчас — итоги не финальные' if live else 'месяц завершён'
    body = f"""<div class="hero">
  <div class="hero-tag">Сезон · {status}</div>
  <h1>{month_title(mk)}</h1>
  <div class="hero-sub">Итоги месяца по баллам игры и дневникам команды</div>
</div>
<div class="wrap">
  <div class="sect">Подиум</div>
  <div class="podium">{''.join(podium) or '<div style="color:#555;font-size:13px">Баллы за месяц ещё не начислены</div>'}</div>
  <div class="sect">Полная таблица</div>
  <div class="board" style="padding:8px 20px">
    <table class="mt">
      <tr><th></th><th>Менеджер</th><th class="r">Баллы</th><th class="r">Деньги</th><th class="r">План (из чата)</th><th class="r">%</th><th class="r">Дней</th></tr>
      {''.join(trows)}
    </table>
  </div>
  <div class="sect">Рекорды месяца</div>
  <div class="cards4">{''.join(recs)}</div>
</div>"""
    return page(f'{month_title(mk)} · Путь 101% 2026', body, nav(months, mk))


# ── Журнал менеджера ──────────────────────────────────────────────────────────

def make_journal(name, cfg, data, months, boards, today):
    grad = cfg['grad']

    month_tabs, month_secs = [], []
    active_months = [mk for mk in months if data[name][mk]['days'] or data[name][mk]['points']]
    if not active_months:
        active_months = months[-1:]
    default_mk = active_months[-1]

    for mk in active_months:
        info = data[name][mk]
        days_data = info['days']
        all_days = sorted(days_data.keys())
        total_msgs = sum(len(v) for v in days_data.values())
        morning_days = sum(1 for d, ms in days_data.items() if any(classify(m) == 'morning' for m in ms))
        evening_days = sum(1 for d, ms in days_data.items() if any(classify(m) == 'evening' for m in ms))
        money = info['money']
        place = info.get('place')
        plan = info['plan']
        plan_lbl = 'План месяца' if info.get('plan_source') == 'chat' else 'План (не объявлен)'
        money_pct = round(money / plan * 100) if money and plan else 0

        badges = []
        if place == 1 and mk != month_key(today):
            badges.append(f'<span class="bdg gold">🏆 Победитель {month_gen(mk)}</span>')
        elif place == 1:
            badges.append(f'<span class="bdg gold">🥇 Лидер {month_gen(mk)}</span>')
        elif place and place <= 3:
            badges.append(f'<span class="bdg gold">{MEDALS[place]} {place} место {month_gen(mk)}</span>')
        if info['plan_bonus']:
            badges.append('<span class="bdg grn">✓ План месяца закрыт · +101 балл</span>')
        if morning_days >= 15:
            badges.append(f'<span class="bdg pur">🔥 {morning_days} утренних отчётов</span>')
        badges_html = f'<div class="badges" style="justify-content:center">{"".join(badges)}</div>' if badges else ''

        # Карточки дней
        cards = []
        for i, day in enumerate(all_days):
            msgs = days_data[day]
            morning = [m for m in msgs if classify(m) == 'morning']
            evening = [m for m in msgs if classify(m) == 'evening']
            other = [m for m in msgs if classify(m) == 'other']
            day_amount = info['money_by_day'].get(day)

            day_pts = info['points_by_day'].get(day.isoformat())
            pts_sum = sum(day_pts.values()) if day_pts else 0
            pts_badge = f'<span class="fb pts">+{pts_sum:.0f} б.</span>' if pts_sum else ''

            mrow = ''
            if day_amount:
                pct_day = round(day_amount / plan * 100, 1)
                mrow = (
                    f'<div class="mrow">'
                    f'<div class="m"><div class="ml">Факт</div><div class="mv a">{fmt(day_amount)}</div></div>'
                    f'<div class="m"><div class="ml">% плана</div><div class="mv">{pct_day}%</div></div>'
                    f'</div>'
                )

            mo_blk = blk('mo', 'Утро для себя', morning)
            ev_blk = blk('ev', 'Рефлексия дня', evening, mrow)
            ot_blk = blk('pu', 'В течение дня', other)
            conclusion = auto_conclusion(day, msgs, day_amount, plan, morning, evening)
            cn_blk = (
                f'<div class="blk cn"><div class="blk-lbl"><span class="dot"></span>Итоговый вывод</div>'
                f'<div class="msg-item">{conclusion}</div></div>'
            )

            checks = f'{"✓ Утро" if morning else "— Утро"} · {"✓ Рефлексия" if evening else "— Рефлексия"} · {len(msgs)} сообщ.'
            card_id = f"d{mk.replace('-', '')}{i:03d}"
            open_cls = ' open' if i == len(all_days) - 1 and mk == default_mk else ''
            cards.append(f"""<div class="card{open_cls}" id="{card_id}">
  <div class="card-hdr" onclick="toggle('{card_id}')">
    <div class="hdr-l">
      <div class="day-num"><span class="n">{day.day}</span>{MONTH_RU[day.month]}</div>
      <div class="card-info"><h3>{WEEKDAY_FULL[day.weekday()]} · {day.strftime('%d.%m.%Y')}</h3><div class="sub">{checks}</div></div>
    </div>
    <div class="hdr-r">{pts_badge}{badge_html(day_amount, plan)}<span class="tog">▼</span></div>
  </div>
  <div class="card-body">{mo_blk}{ev_blk}{ot_blk}{cn_blk}</div>
</div>""")

        month_tabs.append(
            f'<span class="tab{" act" if mk == default_mk else ""}" id="t{mk}" onclick="showMonth(\'{mk}\')">{month_title(mk).split()[0]}</span>'
        )
        month_secs.append(f"""<div class="msec{' act' if mk == default_mk else ''}" id="m{mk}">
  <div class="stats">
    <div class="stat"><span class="val a">{info['points']:.0f}</span><span class="lbl">Баллы</span></div>
    <div class="stat"><span class="val">{f"{place} из 9" if place else "—"}</span><span class="lbl">Место</span></div>
    <div class="stat"><span class="val g">{fmt(money) if money else '—'}</span><span class="lbl">Деньги</span></div>
    <div class="stat"><span class="val">{fmt(plan) if plan else '—'}</span><span class="lbl">{plan_lbl}</span></div>
    <div class="stat"><span class="val{' g' if money_pct >= 100 else ''}">{f"{money_pct}%" if money_pct else '—'}</span><span class="lbl">% ден. плана</span></div>
    <div class="stat"><span class="val">{len(all_days)}</span><span class="lbl">Дней</span></div>
    <div class="stat"><span class="val">{morning_days}</span><span class="lbl">Утренних</span></div>
    <div class="stat"><span class="val">{evening_days}</span><span class="lbl">Рефлексий</span></div>
  </div>
  {badges_html}
  <div style="margin-top:18px">{''.join(cards) or '<div style="color:#555;font-size:13px;text-align:center;padding:20px">В этом месяце записей в дневнике нет — только баллы из таблицы игры</div>'}</div>
</div>""")

    body = f"""<div class="hero">
  <div class="avatar" style="background:linear-gradient(135deg,{grad})">{cfg['initials']}</div>
  <h1>{name}</h1>
  <div class="hero-sub">{cfg['role']}</div>
  <div class="tabs">{''.join(month_tabs)}</div>
</div>
<div class="wrap">
{''.join(month_secs)}
</div>"""
    return page(f'{name} · Путь 101% 2026', body, nav(months), JS_TABS)


# ── Сборка всего сайта ────────────────────────────────────────────────────────

def build_site(messages, game, log=print):
    today = date.today()
    data, months, boards, unmatched = prep_data(messages, game)
    if unmatched:
        log(f"Авторы без совпадения (пропущены): {', '.join(sorted(unmatched))}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(make_index(data, months, boards, today))
    log("OK index.html (дашборд)")

    for mk in months:
        fname = f'month_{mk}.html'
        with open(os.path.join(OUTPUT_DIR, fname), 'w', encoding='utf-8') as f:
            f.write(make_month_page(data, months, boards, mk, today))
        log(f"OK {fname}")

    for name, cfg in MANAGERS.items():
        html = make_journal(name, cfg, data, months, boards, today)
        with open(os.path.join(OUTPUT_DIR, cfg['file']), 'w', encoding='utf-8') as f:
            f.write(html)
        cur_pts = data[name][months[-1]]['points']
        log(f"OK {name}: {sum(len(data[name][mk]['days']) for mk in months)} дн. дневника, {cur_pts:.0f} б. в тек. месяце")

    return data, months
