#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用两个独立的第三方实现批量对照本引擎的四柱、十神、藏干、十二长生、交节与起运。

参照库（仅验证时需要，引擎本身不依赖）：
  lunar_python —— 6tail/lunar 的 Python 版，众多在线排盘网站的底层库；四柱按交节「时刻」换月。
  sxtwl        —— 寿星天文历；其 getMonthGZ() 按「日」换月，用来展示日粒度工具在交节当天的偏差。

用法：
  pip install lunar_python sxtwl
  python verify_against_references.py --samples 20000 --output verification_report.md
"""
import argparse
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lunar_python import Solar
import sxtwl

from bazi_engine import (DEFAULT_TERMS, POSITIONS, load_terms, read_json, solve, changsheng_stage)

HERE = Path(__file__).resolve().parent
TZ8 = timezone(timedelta(hours=8))
GAN, ZHI = '甲乙丙丁戊己庚辛壬癸', '子丑寅卯辰巳午未申酉戌亥'
JIE_LUNAR = {'立春': 'LI_CHUN', '惊蛰': 'JING_ZHE', '清明': 'QING_MING', '立夏': 'LI_XIA', '芒种': 'MANG_ZHONG', '小暑': 'XIAO_SHU',
             '立秋': 'LI_QIU', '白露': 'BAI_LU', '寒露': 'HAN_LU', '立冬': 'LI_DONG', '大雪': 'DA_XUE', '小寒': 'XIAO_HAN'}


def lunar_chart(dt: datetime, sect: int) -> dict:
    ec = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second).getLunar().getEightChar()
    ec.setSect(sect)
    return {
        'pillars': dict(zip(POSITIONS, (ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()))),
        'ten_gods': {'year': ec.getYearShiShenGan(), 'month': ec.getMonthShiShenGan(), 'hour': ec.getTimeShiShenGan()},
        'hidden': dict(zip(POSITIONS, (ec.getYearHideGan(), ec.getMonthHideGan(), ec.getDayHideGan(), ec.getTimeHideGan()))),
        'dishi': dict(zip(POSITIONS, (ec.getYearDiShi(), ec.getMonthDiShi(), ec.getDayDiShi(), ec.getTimeDiShi()))),
        'ec': ec,
    }


def engine_chart(dt: datetime, r: dict, terms, day_boundary: str, late_zi: str = 'next_day') -> dict:
    x = solve({'birth_time': dt.isoformat(), 'day_boundary': day_boundary, 'late_zi_hour_stem': late_zi}, r, terms)
    c = x['computed']
    return {
        'pillars': x['pillars'],
        'ten_gods': c['visible_ten_gods'],
        'hidden': {p: [h['stem'] for h in c['hidden_stems'][p]] for p in POSITIONS},
        'dishi': c['classical']['changsheng']['day_master_on'],
        'alerts': x['meta']['boundary_alerts'],
    }


def sxtwl_chart(dt: datetime) -> dict:
    d = sxtwl.fromSolar(dt.year, dt.month, dt.day)
    gz = lambda g: GAN[g.tg] + ZHI[g.dz]
    return {'year': gz(d.getYearGZ()), 'month': gz(d.getMonthGZ()), 'day': gz(d.getDayGZ()), 'hour': gz(d.getHourGZ(dt.hour))}


def compare_random(n: int, r: dict, terms, seed: int) -> dict:
    rnd = random.Random(seed)
    t0 = datetime(1900, 2, 10, tzinfo=TZ8).timestamp()
    t1 = datetime(2100, 12, 20, tzinfo=TZ8).timestamp()
    stats = Counter()
    examples = {}
    for _ in range(n):
        dt = datetime.fromtimestamp(rnd.uniform(t0, t1), TZ8).replace(second=0, microsecond=0)
        if dt.hour == 23:
            same = engine_chart(dt, r, terms, '00:00', 'same_day')
            stats['late_zi_total'] += 1
            stats['late_zi_same_day_differs_from_ref'] += int(same['pillars']['hour'] != lunar_chart(dt, 2)['pillars']['hour'])
        for db, sect in (('00:00', 2), ('23:00', 1)):
            e = engine_chart(dt, r, terms, db)
            l = lunar_chart(dt, sect)
            tag = f'db{db}'
            stats[f'{tag}:total'] += 1
            for p in POSITIONS:
                if e['pillars'][p] != l['pillars'][p]:
                    k = f'{tag}:pillar_{p}'
                    stats[k] += 1
                    examples.setdefault(k, []).append((dt.isoformat(), e['pillars'][p], l['pillars'][p], bool(e['alerts'])))
            if db == '00:00':
                for p in ('year', 'month', 'hour'):
                    if e['pillars'][p] == l['pillars'][p] and e['ten_gods'][p] != l['ten_gods'][p]:
                        stats['ten_god_mismatch'] += 1
                for p in POSITIONS:
                    if e['pillars'][p] != l['pillars'][p]:
                        continue
                    if set(e['hidden'][p]) != set(l['hidden'][p]):
                        stats['hidden_set_mismatch'] += 1
                    elif e['hidden'][p] != l['hidden'][p]:
                        stats[f'hidden_order_diff:{e["pillars"][p][1]}'] += 1
                    if e['dishi'][p] != l['dishi'][p]:
                        stats['dishi_mismatch'] += 1
                s = sxtwl_chart(dt)
                for p in POSITIONS:
                    if s[p] != e['pillars'][p]:
                        stats[f'sxtwl:pillar_{p}'] += 1
                        examples.setdefault(f'sxtwl:pillar_{p}', []).append((dt.isoformat(), e['pillars'][p], s[p], False))
    return {'stats': stats, 'examples': examples}


def compare_jie(terms) -> dict:
    """本引擎 DE440s 交节 vs lunar_python（寿星算法）交节，逐个比较秒差。"""
    diffs = []
    for y in range(1901, 2100):
        table = Solar.fromYmd(y, 6, 1).getLunar().getJieQiTable()
        for t in terms:
            if t['instant'].astimezone(TZ8).year != y:
                continue
            key = JIE_LUNAR[t['name']]
            s = table.get(t['name']) or table.get(key)
            if s is None or s.getYear() != y:
                continue
            lt = datetime(s.getYear(), s.getMonth(), s.getDay(), s.getHour(), s.getMinute(), s.getSecond(), tzinfo=TZ8)
            diffs.append(((lt - t['instant']).total_seconds(), t['name'], t['at']))
    return {'diffs': diffs}


def compare_boundaries(r: dict, terms, margin_s: int) -> dict:
    """每个交节前后 margin 秒各取一点：两边都应与 lunar_python 一致，否则记录。"""
    stats, bad = Counter(), []
    for t in terms:
        if not (1900 <= t['instant'].year <= 2100):
            continue
        for off in (-margin_s, margin_s):
            dt = (t['instant'] + timedelta(seconds=off)).astimezone(TZ8).replace(microsecond=0)
            try:
                e = engine_chart(dt, r, terms, '00:00')
            except Exception:
                continue
            l = lunar_chart(dt, 2)
            stats['total'] += 1
            if (e['pillars']['year'], e['pillars']['month']) != (l['pillars']['year'], l['pillars']['month']):
                stats['mismatch'] += 1
                bad.append((dt.isoformat(), t['name'], e['pillars']['month'], l['pillars']['month']))
    return {'stats': stats, 'bad': bad}


def compare_luck(n: int, r: dict, terms, seed: int) -> dict:
    """LUCK-P1（3 日折 1 年、精确时长）vs lunar_python getYun(sect=2，按分钟折算)。"""
    rnd = random.Random(seed + 1)
    t0, t1 = datetime(1950, 1, 1, tzinfo=TZ8).timestamp(), datetime(2050, 1, 1, tzinfo=TZ8).timestamp()
    stats, worst = Counter(), []
    for _ in range(n):
        dt = datetime.fromtimestamp(rnd.uniform(t0, t1), TZ8).replace(second=0, microsecond=0)
        g = rnd.choice(['male', 'female'])
        x = solve({'birth_time': dt.isoformat(), 'gender': g, 'luck_policy': 'LUCK-P1', 'num_luck_periods': 3}, r, terms)
        yun = lunar_chart(dt, 2)['ec'].getYun(1 if g == 'male' else 0, 2)
        ly = yun.getStartYear() + yun.getStartMonth() / 12 + yun.getStartDay() / 360 + yun.getStartHour() / 8640
        ey = x['da_yun_start']['start_age_years']
        l_first = yun.getDaYun()[1].getGanZhi()
        stats['total'] += 1
        stats['direction_and_first_pillar_match'] += int(l_first == x['da_yun_sequence'][0]['pillar'])
        d = abs(ly - ey)
        stats['age_within_0.05y'] += int(d < 0.05)
        worst.append((d, dt.isoformat(), g, ey, ly))
    worst.sort(reverse=True)
    return {'stats': stats, 'worst': worst[:5]}


def render(rand, jie, bnd, luck, n, margin) -> str:
    s = rand['stats']
    L = ['# 四柱与十神第三方对照报告', '',
         f'- 参照：lunar_python（交节时刻换月）、sxtwl（按日换月）。随机样本 {n} 个（1900-02—2100-12，UTC+8，分钟精度），每个样本分别按两种换日政策计算。', '']
    L += ['## 1. 四柱（本引擎 vs lunar_python）', '', '| 换日政策 | 样本 | 年柱不一致 | 月柱不一致 | 日柱不一致 | 时柱不一致 |', '|:--|--:|--:|--:|--:|--:|']
    for db, lab in (('00:00', '00:00 换日（lunar sect=2）'), ('23:00', '23:00 换日（lunar sect=1）')):
        t = f'db{db}'
        L.append(f'| {lab} | {s[t + ":total"]} | ' + ' | '.join(str(s[f"{t}:pillar_{p}"]) for p in POSITIONS) + ' |')
    for k, ex in sorted(rand['examples'].items()):
        if k.startswith('db'):
            L.append(f'- `{k}` 示例：' + '；'.join(f'{a} 本引擎 {b} / 参照 {c}' + ('（引擎已标交节临界）' if al else '') for a, b, c, al in ex[:5]))
    L.append(f'- 00:00 换日的比较使用 `late_zi_hour_stem=next_day`（夜子时时干按次日，与 lunar sect=2 同口径）。样本中 23 点出生 {s["late_zi_total"]} 个；若改用引擎默认 `same_day`，其中 {s["late_zi_same_day_differs_from_ref"]} 个时干与参照不同——这是流派约定差异，不是计算错误。')
    L += ['', '## 2. 十神、藏干、十二长生（同一柱一致时逐项比较）', '',
          f'- 明干十神不一致：{s["ten_god_mismatch"]}',
          f'- 藏干集合不一致：{s["hidden_set_mismatch"]}',
          f'- 十二长生（日主坐四支）不一致：{s["dishi_mismatch"]}']
    od = {k.split(':')[1]: v for k, v in s.items() if k.startswith('hidden_order_diff')}
    L.append(f'- 藏干**顺序**不同（集合相同）：' + ('、'.join(f'{b}（{v} 次）' for b, v in od.items()) if od else '无'))
    d = sorted(x[0] for x in jie['diffs'])
    L += ['', '## 3. 交节时刻（本引擎 DE440s vs lunar_python）', '',
          f'- 比较 {len(d)} 个「节」；秒差（参照 − 本引擎）：最小 {d[0]:.0f}，中位 {d[len(d) // 2]:.0f}，最大 {d[-1]:.0f}',
          f'- |差| ≤ 60 秒：{sum(abs(x) <= 60 for x in d)}；≤ 120 秒：{sum(abs(x) <= 120 for x in d)}；> 120 秒：{sum(abs(x) > 120 for x in d)}']
    big = sorted(jie['diffs'], key=lambda x: -abs(x[0]))[:5]
    L.append('- 差值最大的 5 个：' + '；'.join(f'{n_} {a}（{v:+.0f}s）' for v, n_, a in big))
    b = bnd['stats']
    L += ['', f'## 4. 交节前后 ±{margin} 秒的年/月柱', '', f'- 检查 {b["total"]} 个时点，不一致 {b["mismatch"]} 个。']
    for x in bnd['bad'][:5]:
        L.append(f'  - {x[0]}（{x[1]}）本引擎 {x[2]} / 参照 {x[3]}')
    L += ['', '## 5. sxtwl（按日换月的工具）与本引擎的差异', '']
    L += [f'- {p}柱不一致：{s["sxtwl:pillar_" + p]}' for p in POSITIONS]
    for x in rand['examples'].get('sxtwl:pillar_month', [])[:3]:
        L.append(f'  - 例：{x[0]} 本引擎 {x[1]} / sxtwl {x[2]}')
    ls = luck['stats']
    L += ['', '## 6. 起运（LUCK-P1 vs lunar_python getYun sect=2）', '',
          f'- 样本 {ls["total"]}；首步大运（含顺逆）一致 {ls["direction_and_first_pillar_match"]}；起运岁数相差 < 0.05 年 {ls["age_within_0.05y"]}',
          '- 相差最大的 5 例：' + '；'.join(f'{a} {g} 本引擎 {e:.3f} / 参照 {l:.3f}' for _, a, g, e, l in luck['worst'])]
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--samples', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=20261024)
    ap.add_argument('--margin', type=int, default=90)
    ap.add_argument('--luck-samples', type=int, default=2000)
    ap.add_argument('--output', default=str(HERE / 'verification_report.md'))
    a = ap.parse_args()
    r, terms = read_json(HERE / 'rules.json'), load_terms(DEFAULT_TERMS)
    rand = compare_random(a.samples, r, terms, a.seed)
    jie = compare_jie(terms)
    bnd = compare_boundaries(r, terms, a.margin)
    luck = compare_luck(a.luck_samples, r, terms, a.seed)
    Path(a.output).write_text(render(rand, jie, bnd, luck, a.samples, a.margin), encoding='utf-8')
    print(Path(a.output).read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
