#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 JPL DE440s 星历计算十二「节」的交节瞬间，生成 terms_1900_2100.json。

仅生成数据时需要 skyfield 与 de440s.bsp；bazi_engine.py 运行时只读生成的 JSON，仍为纯标准库。

定义：交节瞬间 = 地心视太阳黄经（真春分点、当日黄道）达到 15° 整数倍的时刻。
十二「节」对应黄经 315°(立春)、345°(惊蛰)……285°(小寒)。

用法：
  pip install skyfield
  curl -O https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp
  python generate_terms.py --ephemeris de440s.bsp --start 1900 --end 2100
"""
import argparse
import json
from datetime import timedelta, timezone
from pathlib import Path

import skyfield
from skyfield import almanac
from skyfield.api import load
from skyfield.framelib import ecliptic_frame

O = Path(__file__).resolve().parent
TZ8 = timezone(timedelta(hours=8))
# 黄经 -> 节名；只取十二「节」（月界），中气不参与排盘
JIE = {315: '立春', 345: '惊蛰', 15: '清明', 45: '立夏', 75: '芒种', 105: '小暑',
       135: '立秋', 165: '白露', 195: '寒露', 225: '立冬', 255: '大雪', 285: '小寒'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ephemeris', required=True)
    ap.add_argument('--start', type=int, default=1900)
    ap.add_argument('--end', type=int, default=2100)
    ap.add_argument('--output', default=str(O / 'terms_1900_2100.json'))
    a = ap.parse_args()

    ts = load.timescale()
    eph = load(a.ephemeris)
    earth, sun = eph['earth'], eph['sun']

    def segment(t):
        lon = earth.at(t).observe(sun).apparent().frame_latlon(ecliptic_frame)[1].degrees
        return (lon // 15).astype(int) % 24
    segment.step_days = 5

    # 起点含上一年立春，保证首年立春前出生也能定年柱；终点多取一个月
    t0 = ts.utc(a.start - 1, 1, 20)
    t1 = ts.utc(a.end + 1, 2, 1)
    times, segs = almanac.find_discrete(t0, t1, segment, epsilon=0.001 / 86400)
    terms = []
    for t, s in zip(times, segs):
        deg = int(s) * 15
        if deg not in JIE:
            continue
        dt = t.utc_datetime()
        terms.append({'name': JIE[deg], 'longitude_deg': deg,
                      'at': dt.astimezone(TZ8).replace(microsecond=0).isoformat(),
                      'utc': dt.replace(microsecond=0).isoformat().replace('+00:00', 'Z')})

    out = {
        'schema_version': '1.1.0',
        'display_timezone': 'UTC+08:00',
        'coverage': f'{a.start - 1}-02 立春 至 {a.end + 1}-01 的十二「节」交节瞬间',
        'method': '地心视太阳黄经（真春分点当日黄道，含章动与光行差）达 15°整数倍之时刻；二分法求根，容差 1 ms',
        'ephemeris': 'JPL DE440s (naif.jpl.nasa.gov)',
        'software': f'skyfield {skyfield.__version__}',
        'time_scale_notice': 'UTC 由 TT 经 skyfield 内建 ΔT 表换算；1972 年前 UTC 为近似，未来年份 ΔT 为预测值，可能有数十秒误差。'
                             '交节前后一分钟内出生须另行核对权威机构公布值。',
        'source': 'generated_by generate_terms.py',
        'terms': terms,
    }
    Path(a.output).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'wrote {len(terms)} jie to {a.output}')


if __name__ == '__main__':
    main()
