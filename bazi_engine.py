#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""子平八字 AI 公式书的可复核参考实现（Python 3.9+，仅标准库）。

本程序实现四柱的约定性历法计算与古典格局线索的初筛；
不是对现实人生预测准确性的证明，不计算寿夭、病症、风险或人生财富。
"""
from __future__ import annotations

import argparse
import bisect
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_TERMS = HERE / "terms_1900_2100.json"
POSITIONS = ["year", "month", "day", "hour"]
POS_CN = {"year": "年", "month": "月", "day": "日", "hour": "时"}
ENGINE_VERSION = "1.4.0"
DEFAULT_BOUNDARY_MARGIN_S = 120
MAX_RANGE_HOURS = 48
TROPICAL_YEAR_DAYS = 365.2422


class RulebookError(ValueError):
    """Inputs or rules insufficient for a reproducible result."""


def read_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_aware(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as e:
        raise RulebookError(f"时间必须是带时区偏移的 ISO-8601 字符串: {s!r}") from e
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise RulebookError("拒绝无时区偏移的出生时刻。请提供例如 2024-02-04T16:30:00+08:00")
    return dt


def index_pair(idx: int, rules: dict) -> str:
    """Sexagenary index is zero-based; 0=甲子; 54=戊午."""
    return rules["stems"][idx % 10] + rules["branches"][idx % 12]


def pair_index(pillar: str, rules: dict) -> int:
    return next(i for i in range(60) if index_pair(i, rules) == pillar)


def validate_pillar(pillar: str, rules: dict) -> None:
    if not isinstance(pillar, str) or len(pillar) != 2:
        raise RulebookError(f"非法干支：{pillar!r}")
    st, br = pillar[0], pillar[1]
    if st not in rules["stems"] or br not in rules["branches"]:
        raise RulebookError(f"非法干支：{pillar!r}")
    if rules["stems"].index(st) % 2 != rules["branches"].index(br) % 2:
        raise RulebookError(f"阴阳奇偶不匹配，不属于六十甲子：{pillar}")


def stem_element(stem: str, r: dict) -> str:
    return r["stem_element"][stem]


def ten_god(day_stem: str, other_stem: str, r: dict) -> str:
    """Strict five-phase graph + yin-yang mapping. No interpretive heuristics."""
    elements = r["producing_cycle"]
    s = stem_element(day_stem, r)
    o = stem_element(other_stem, r)
    i, j = elements.index(s), elements.index(o)
    same = r["stem_yinyang"][day_stem] == r["stem_yinyang"][other_stem]
    if i == j:
        relation = "same"
    elif (i + 1) % 5 == j:
        relation = "self_produces_other"
    elif (i + 2) % 5 == j:
        relation = "self_controls_other"
    elif (j + 2) % 5 == i:
        relation = "other_controls_self"
    elif (j + 1) % 5 == i:
        relation = "other_produces_self"
    else:
        raise RulebookError("五行关系表不完整")
    rec = next(x for x in r["ten_god_definition"] if x["relation"] == relation)
    return rec["same_polarity" if same else "different_polarity"]


def day_pillar(local_date: date, r: dict) -> tuple[str, int]:
    anchor = r["day_anchor"]
    d0 = date.fromisoformat(anchor["date"])
    idx = (anchor["index"] + (local_date - d0).days) % 60
    return index_pair(idx, r), idx


def hour_pillar(clock: datetime, day_stem: str, r: dict) -> tuple[str, int]:
    # 23:00-00:59 = 子 hour. At 1:00-2:59 = 丑, etc.
    hidx = ((clock.hour + 1) // 2) % 12
    zistart = r["five_rat_zi_hour_start"][day_stem]
    stem_idx = (r["stems"].index(zistart) + hidx) % 10
    return r["stems"][stem_idx] + r["branches"][hidx], hidx


class TermTable(list):
    """Sorted jie records plus table-level provenance."""
    meta: dict = {}


def load_terms(path: str | Path) -> TermTable:
    data = read_json(path)
    terms = TermTable(sorted(
        ({**rec, "instant": parse_aware(rec["at"]).astimezone(timezone.utc)} for rec in data.get("terms", [])),
        key=lambda x: x["instant"]))
    if not terms:
        raise RulebookError("缺失已核对的交节时刻；不能准确算年、月柱")
    terms.meta = {k: v for k, v in data.items() if k != "terms"}
    terms.meta["path"] = Path(path).name
    return terms


def _bracketing_jie(utc: datetime, terms: list[dict], r: dict) -> tuple[list[dict], int]:
    jie_names = [x["name"] for x in r["month_jie"]]
    month_terms = [x for x in terms if x["name"] in jie_names]
    pos = bisect.bisect_right([x["instant"] for x in month_terms], utc)
    return month_terms, pos


def _solar_term_month_and_year(birth: datetime, terms: list[dict], r: dict) -> tuple[int, int, dict, dict]:
    utc = birth.astimezone(timezone.utc)
    jie_names = [x["name"] for x in r["month_jie"]]
    month_terms, pos = _bracketing_jie(utc, terms, r)
    if pos == 0 or pos == len(month_terms):
        raise RulebookError("此出生时刻不在交节资料覆盖区间（需要前后连续的两个「节」）")
    last_jie, next_jie = month_terms[pos - 1], month_terms[pos]
    seq = jie_names.index(last_jie["name"])
    if jie_names[(seq + 1) % 12] != next_jie["name"]:
        raise RulebookError("交节资料不连续：缺失相邻节气，不能默默跨节")
    if (next_jie["instant"] - last_jie["instant"]).total_seconds() > 40 * 86400:
        raise RulebookError("交节时刻相距超过40天，疑似缺失/错误数据")
    springs = [x for x in month_terms[:pos] if x["name"] == "立春"]
    if not springs:
        raise RulebookError("缺少之前的立春，不能准确算年柱")
    last_spring = springs[-1]
    if (utc - last_spring["instant"]).total_seconds() > 370 * 86400:
        raise RulebookError("前次立春距出生超过370天：交节表年份资料可能缺失")
    # Note: year/month boundaries are real astronomical instants, not civil dates.
    # 以东八区判年份：立春总在公历 2 月 3–5 日，任何时区下年份都不会因此跨年。
    return last_spring["instant"].astimezone(birth.tzinfo).year, seq, last_jie, next_jie


def _clock(request: dict, birth: datetime) -> tuple[datetime, str]:
    clock_mode = request.get("clock_mode", "civil")
    if clock_mode == "mean_solar":
        if request.get("daylight_saving_active", False):
            raise RulebookError("真/平太阳时要求先校正夏令时；本参考实现拒绝在夏令时下直接计算")
        if "longitude_deg_east" not in request or "reference_meridian_deg_east" not in request:
            raise RulebookError("mean_solar 需要经度与标准时区的参考子午线")
        correction_minutes = 4.0 * (float(request["longitude_deg_east"]) - float(request["reference_meridian_deg_east"]))
        return birth + timedelta(minutes=correction_minutes), clock_mode
    if clock_mode != "civil":
        raise RulebookError("clock_mode 仅允许 civil 或 mean_solar；视太阳时还需要均时差资料")
    return birth, clock_mode


def _pillars_at(birth: datetime, request: dict, r: dict, terms: list[dict]) -> tuple[dict, dict]:
    """Pure calendar step: returns pillars and the intermediate values needed for the trace."""
    policy = request.get("day_boundary", "00:00")
    if policy not in ("00:00", "23:00"):
        raise RulebookError("day_boundary 仅允许 00:00 或 23:00")
    clock, clock_mode = _clock(request, birth)
    effective_year, seq, last_jie, next_jie = _solar_term_month_and_year(birth, terms, r)
    yidx = (effective_year - 1984) % 60
    year = index_pair(yidx, r)
    yin_start = r["five_tiger_yin_month_start"][year[0]]
    month = r["stems"][(r["stems"].index(yin_start) + seq) % 10] + r["month_jie"][seq]["branch"]
    d = clock.date() + (timedelta(days=1) if policy == "23:00" and clock.hour == 23 else timedelta())
    day, _ = day_pillar(d, r)
    # 夜子时（00:00 换日下的 23:00–23:59）：日柱不换；时干按当日（公式书 C-103 默认）或按次日（夜子时派、lunar_python sect=2）
    late_zi = request.get("late_zi_hour_stem", "same_day")
    if late_zi not in ("same_day", "next_day"):
        raise RulebookError("late_zi_hour_stem 仅允许 same_day 或 next_day")
    stem_day = day
    if policy == "00:00" and clock.hour == 23 and late_zi == "next_day":
        stem_day, _ = day_pillar(d + timedelta(days=1), r)
    hour, hidx = hour_pillar(clock, stem_day[0], r)
    pillars = dict(zip(POSITIONS, (year, month, day, hour)))
    for v in pillars.values():
        validate_pillar(v, r)
    ctx = {"clock": clock, "clock_mode": clock_mode, "policy": policy, "late_zi": late_zi, "hour_stem_day": stem_day, "effective_year": effective_year,
           "yidx": yidx, "seq": seq, "last_jie": last_jie, "next_jie": next_jie, "date": d, "hidx": hidx}
    return pillars, ctx


def compute_pillars(request: dict, r: dict, terms: list[dict]) -> tuple[dict, list[dict], dict]:
    if request.get("calendar_policy", "solar_jie") != "solar_jie":
        raise RulebookError("排盘引擎仅支持以立春/十二节换年月；农历年算法与之不同")
    birth = parse_aware(request["birth_time"])
    pillars, c = _pillars_at(birth, request, r, terms)
    year, month, day, hour = (pillars[p] for p in POSITIONS)
    last_jie, next_jie, d = c["last_jie"], c["next_jie"], c["date"]
    trace = [
        {"id": "C-101", "type": "computed", "result": year, "method": f"上一个立春对应公历年={c['effective_year']}，(年-1984) mod 60={c['yidx']}", "inputs": {"last_lichun_year": c["effective_year"]}},
        {"id": "C-102", "type": "computed", "result": month, "method": "上一个节确定月支，五虎遁由年干推寅月再顺推月份", "inputs": {"previous_jie": last_jie["name"], "previous_jie_at": last_jie["at"], "next_jie": next_jie["name"], "next_jie_at": next_jie["at"], "month_index_from_yin": c["seq"]}},
        {"id": "C-103", "type": "computed", "result": day, "method": "2000-01-01=戊午(index54)，日数差加54再模60", "inputs": {"effective_date": d.isoformat(), "date_delta_days": (d - date(2000, 1, 1)).days, "day_boundary": c["policy"]}},
        {"id": "C-104", "type": "computed", "result": hour, "method": "子时23:00起，每2小时一支，五鼠遁推时干", "inputs": {"effective_clock": c["clock"].isoformat(), "hour_branch_index": c["hidx"], "hour_stem_from_day": c["hour_stem_day"], "late_zi_hour_stem": c["late_zi"]}},
    ]
    meta = {"input_birth": birth.isoformat(), "effective_clock": c["clock"].isoformat(), "clock_mode": c["clock_mode"],
            "day_boundary": c["policy"], "late_zi_hour_stem": c["late_zi"], "term_source": _term_source(terms),
            "previous_jie": {"name": last_jie["name"], "at": last_jie["at"]},
            "next_jie": {"name": next_jie["name"], "at": next_jie["at"]}}
    meta["boundary_alerts"] = _boundary_alerts(birth, request, r, terms, c)
    return pillars, trace, meta


def _term_source(terms: list[dict]) -> str:
    m = getattr(terms, "meta", {})
    if m.get("ephemeris"):
        return f"{m.get('path')}：{m.get('ephemeris')}，{m.get('software')}；{m.get('time_scale_notice', '')}"
    return f"{m.get('path', '外部交节表')}（需自行核对版本和来源）"


def _boundary_alerts(birth: datetime, request: dict, r: dict, terms: list[dict], c: dict) -> list[dict]:
    """出生距交节不足 margin 秒时，交节表本身的误差可能改变年/月柱：给出另一侧的盘，不择一。"""
    margin = float(request.get("boundary_margin_seconds", DEFAULT_BOUNDARY_MARGIN_S))
    alerts = []
    for side, jie in (("previous", c["last_jie"]), ("next", c["next_jie"])):
        gap = (birth.astimezone(timezone.utc) - jie["instant"]).total_seconds()
        if abs(gap) >= margin:
            continue
        other_instant = jie["instant"] - timedelta(seconds=1) if side == "previous" else jie["instant"]
        alt, _ = _pillars_at(other_instant.astimezone(birth.tzinfo), request, r, terms)
        alerts.append({"type": "unresolved", "jie": jie["name"], "jie_at": jie["at"], "seconds_from_jie": round(gap, 1),
                       "margin_seconds": margin,
                       "alternative_year_month": {"year": alt["year"], "month": alt["month"]},
                       "note": "出生与交节瞬间相距小于容差；不同星历/ΔT 口径的交节时刻可差数十秒，年/月柱须以同一权威数据复核"})
    return alerts


def _pairs_in(branches: dict, table: list, relation: str, status: str) -> list[dict]:
    out = []
    for i in range(len(POSITIONS)):
        for j in range(i + 1, len(POSITIONS)):
            a, b = POSITIONS[i], POSITIONS[j]
            x, y = branches[a], branches[b]
            if any({x, y} == set(pair[:2]) and x != y for pair in table):
                out.append({"positions": [a, b], "branches": [x, y], "relation": relation, "status": status})
    return out


def _groups_in(branches: dict, table: dict, relation: str, status: str) -> list[dict]:
    out = []
    for element, combo in table.items():
        if all(x in branches.values() for x in combo):
            pos = [p for p in POSITIONS if branches[p] in combo]
            out.append({"element": element, "branches": combo, "positions": pos, "relation": relation, "status": status})
    return out


def _punishments(branches: dict, r: dict) -> list[dict]:
    out = []
    present = list(branches.values())
    for name, members in r["punishments"].items():
        if name == "自刑":
            for b in members:
                pos = [p for p in POSITIONS if branches[p] == b]
                if len(pos) >= 2:
                    out.append({"relation": name, "branches": [b] * len(pos), "positions": pos, "completeness": "完整", "status": "只标注结构"})
            continue
        hit = [b for b in members if b in present]
        if len(hit) >= 2:
            pos = [p for p in POSITIONS if branches[p] in hit]
            full = len(hit) == len(members)
            out.append({"relation": name, "branches": hit, "positions": pos, "completeness": "完整" if full else "部分",
                        "status": "只标注结构；部分三刑是否论刑依流派而异" if not full else "只标注结构"})
    return out


def analyze_structure(pillars: dict, r: dict) -> tuple[dict, list[dict]]:
    for pos in POSITIONS:
        if pos not in pillars:
            raise RulebookError(f"四柱缺少: {pos}")
        validate_pillar(pillars[pos], r)
    day_master = pillars["day"][0]
    stems = {p: pillars[p][0] for p in POSITIONS}
    branches = {p: pillars[p][1] for p in POSITIONS}
    visible = {p: ten_god(day_master, stems[p], r) for p in ("year", "month", "hour")}
    hidden = {p: [{"stem": s, "ten_god": ten_god(day_master, s, r), "status": "本气" if i == 0 else "余气/中气"} for i, s in enumerate(r["hidden_stems_main_first"][b])] for p, b in branches.items()}
    month_hidden = r["hidden_stems_main_first"][branches["month"]]
    exposed = [s for s in month_hidden if s in visible_stems(stems)]
    clashes = _pairs_in(branches, r["six_clashes"], "六冲", "只标注结构，不等于冲破成立")
    harmonies = _pairs_in(branches, r["six_harmonies"], "六合", "只标注合象，不表示合化成功")
    triads = _groups_in(branches, r["three_harmonies"], "三合", "不自动认定化气")
    meetings = _groups_in(branches, r["three_meetings"], "三会", "不自动认定成方")
    harms = _pairs_in(branches, r["six_harms"], "六害", "只标注结构")
    punish = _punishments(branches, r)
    stem_combos = []
    for i in range(len(POSITIONS)):
        for j in range(i + 1, len(POSITIONS)):
            a, b = POSITIONS[i], POSITIONS[j]
            for x, y, el in r["stem_five_combinations"]:
                if {stems[a], stems[b]} == {x, y}:
                    stem_combos.append({"positions": [a, b], "stems": [stems[a], stems[b]], "relation": "天干五合", "element": el,
                                        "involves_day_master": "day" in (a, b), "status": "只标注合象，不表示合化成功"})
    month_combined = any("month" in x["positions"] for x in harmonies + triads + meetings)
    facts = {
        "day_master": day_master,
        "day_master_element": stem_element(day_master, r),
        "visible_ten_gods": list(visible.values()),
        "month_primary_hidden_stem": month_hidden[0],
        "month_primary_ten_god": ten_god(day_master, month_hidden[0], r),
        "month_hidden_exposed": exposed,
        "month_hidden_exposed_count": len(exposed),
        "month_primary_exposed": month_hidden[0] in exposed,
        "has_month_branch_clash": any("month" in c["positions"] for c in clashes),
        "has_month_branch_combination": month_combined,
    }
    relations = {"six_clashes": clashes, "six_harmonies": harmonies, "three_harmonies": triads,
                 "three_meetings": meetings, "six_harms": harms, "punishments": punish}
    detail = {"day_master": day_master, "stems": stems, "branches": branches, "visible_ten_gods": visible, "hidden_stems": hidden,
              "month_main_qi": {"stem": month_hidden[0], "ten_god": facts["month_primary_ten_god"]}, "month_hidden_exposed": exposed,
              "branch_relations": relations, "stem_relations": {"five_combinations": stem_combos}, "facts": facts}
    audit = [
        {"id": "D-101", "type": "computed", "result": visible, "method": "由日干与年/月/时干之五行生克、阴阳同异精确映射十神"},
        {"id": "D-102", "type": "lookup", "result": hidden, "method": "按约定藏干表查本气、中气、余气并逐项取十神"},
        {"id": "D-103", "type": "observed_structure", "result": {"month_hidden_exposed": exposed, "month_primary": month_hidden[0]}, "method": "只检查年/月/时干是否出现月支藏干；日干不算透干"},
        {"id": "D-104", "type": "observed_structure", "result": relations, "method": "只识别六冲、六合、三合、三会、六害、刑的存在；不判断合化或解冲"},
        {"id": "D-105", "type": "observed_structure", "result": stem_combos, "method": "四柱天干两两比对五合表；不判断合化"},
    ]
    return detail, audit


def _element_relation_state(season_el: str, el: str, r: dict) -> str:
    cyc = r["producing_cycle"]
    i, j = cyc.index(season_el), cyc.index(el)
    return {0: "旺", 1: "相", 4: "休", 3: "囚", 2: "死"}[(j - i) % 5]


def changsheng_stage(stem: str, branch: str, r: dict) -> str:
    cs = r["classical_tables"]["changsheng"]
    start = r["branches"].index(cs["start"][stem])
    step = 1 if cs["direction"][r["stem_yinyang"][stem]] == "forward" else -1
    return cs["stages"][(step * (r["branches"].index(branch) - start)) % 12]


def renyuan_siling(month_branch: str, days_since_jie: float, r: dict) -> dict:
    segs = r["classical_tables"]["renyuan_siling"]["table"][month_branch]
    acc = 0
    for i, seg in enumerate(segs):
        acc += seg["days"]
        if days_since_jie < acc or i == len(segs) - 1:
            return {"stem": seg["stem"], "literal": seg["literal"], "segment": i + 1, "segment_end_day": acc,
                    "capped": days_since_jie >= acc}


def classical_lookup(detail: dict, r: dict, days_since_jie: float | None, wx_policy: str | None = None) -> tuple[dict, list[dict]]:
    """L-301–L-304：四张有出处的古籍表，纯查表，不做加权。"""
    ct = r["classical_tables"]
    dm, mb = detail["day_master"], detail["branches"]["month"]
    stems, branches = detail["stems"], detail["branches"]
    # L-301 人元司令
    if days_since_jie is None:
        siling = {"status": "unresolved", "reason": "需出生时刻与交节时刻；仅给四柱时无法定司令天数"}
    else:
        hit = renyuan_siling(mb, days_since_jie, r)
        siling = {**hit, "ten_god": ten_god(dm, hit["stem"], r), "days_since_jie": round(days_since_jie, 3),
                  "month_segments": ct["renyuan_siling"]["table"][mb]}
    # L-302 旺相休囚死
    pid = wx_policy or ct["wangxiang"]["default_policy"]
    if pid not in ct["wangxiang"]["policies"]:
        raise RulebookError(f"未定义的旺相休囚死政策: {pid}")
    season_el = ct["wangxiang"]["policies"][pid]["season_element"][mb]
    wx = {"policy": pid, "season_element": season_el,
          "by_element": {el: _element_relation_state(season_el, el, r) for el in r["producing_cycle"]}}
    wx["day_master_state"] = wx["by_element"][stem_element(dm, r)]
    wx["alternatives"] = {k: _element_relation_state(v["season_element"][mb], stem_element(dm, r), r)
                          for k, v in ct["wangxiang"]["policies"].items()}
    # L-303 十二长生：日主及各明干坐四支
    cs = {"day_master_on": {p: changsheng_stage(dm, branches[p], r) for p in POSITIONS},
          "stem_on_own_branch": {p: changsheng_stage(stems[p], branches[p], r) for p in POSITIONS}}
    # L-304 穷通宝鉴调候
    cell = ct["tiaohou"]["table"][dm][mb]
    vis = {p: stems[p] for p in ("year", "month", "hour")}

    def where(s):
        return {"visible": [p for p, x in vis.items() if x == s],
                "hidden": [p for p in POSITIONS if s in r["hidden_stems_main_first"][branches[p]]],
                "ten_god": ten_god(dm, s, r)}
    th = {**cell, "presence": {s: where(s) for s in cell["primary"] + cell["secondary"]}}
    th["primary_visible"] = any(th["presence"][s]["visible"] for s in cell["primary"])
    out = {"renyuan_siling": siling, "wangxiang": wx, "changsheng": cs, "tiaohou": th}
    audit = [
        {"id": "L-301", "type": "lookup", "result": siling, "method": "按交节后经过天数查《三命通会》人元司事分日表", "source": ct["renyuan_siling"]["source"]},
        {"id": "L-302", "type": "lookup", "result": wx, "method": "以月支定当令五行，按生克关系得旺相休囚死", "source": ct["wangxiang"]["source"]},
        {"id": "L-303", "type": "lookup", "result": cs, "method": "阳干自长生位顺行、阴干逆行十二宫", "source": ct["changsheng"]["source"]},
        {"id": "L-304", "type": "lookup", "result": th, "method": "日干×月支查《穷通宝鉴》首段用神，并检查其在四柱中的明见/藏支", "source": ct["tiaohou"]["source"]},
    ]
    return out, audit


def select_geju(detail: dict, r: dict) -> dict:
    """G-200 月令取格：按 rules.json geju_selection.order 的固定次序产生格局候选，不判成败。"""
    gs = r["geju_selection"]
    ge = gs["ten_god_to_ge"]
    lr = r["classical_tables"]["lu_yangren"]
    dm, mb = detail["day_master"], detail["branches"]["month"]
    stems = detail["stems"]
    vis_pos = ("year", "month", "hour")
    hidden = r["hidden_stems_main_first"][mb]
    main = hidden[0]
    tg = lambda s: ten_god(dm, s, r)
    bijie = {"比肩", "劫财"}

    def exposed_at(s):
        return [p for p in vis_pos if stems[p] == s]

    def cand(rule_id, stem, role, status, positions=None):
        t = tg(stem)
        return {"ge": ge.get(t, t), "ten_god": t, "stem": stem, "rule": rule_id, "role": role, "status": status,
                "exposed_at": positions if positions is not None else exposed_at(stem)}

    def other_visible(rule_id):
        # 建禄、月刃、月劫的「另取」：天干透出的财官杀食伤，按年→月→时
        out = []
        for p in vis_pos:
            if tg(stems[p]) not in bijie and not any(c["stem"] == stems[p] for c in out):
                out.append(cand(rule_id, stems[p], "另取", "candidate", [p]))
        return out

    path, candidates = [], []
    if mb == lr["lu"][dm]:
        path.append("G-201")
        head = {"ge": "建禄格", "rule": "G-201", "role": "月令", "status": "classified"}
    elif lr["yangren"].get(dm) == mb:
        path.append("G-202")
        head = {"ge": "阳刃格", "rule": "G-202", "role": "月令", "status": "classified"}
    elif tg(main) in bijie:
        path.append("G-203")
        head = {"ge": "月劫（比劫秉令）", "rule": "G-203", "role": "月令", "status": "classified"}
    else:
        head = None
    if head:
        candidates.append(head)
        inner = [cand("G-203", s, "月中透出", "candidate") for s in hidden[1:] if tg(s) not in bijie and exposed_at(s)] if path == ["G-203"] else []
        extra = inner or other_visible(path[0])
        candidates += extra
        if not extra:
            candidates.append({"ge": None, "rule": path[0], "role": "另取", "status": "unresolved", "reason": "天干无透出之财官杀食伤"})
    else:
        if exposed_at(main):
            path.append("G-204")
            candidates.append(cand("G-204", main, "本气透出", "primary"))
            candidates += [cand("G-204", s, "兼透", "parallel") for s in hidden[1:] if tg(s) not in bijie and exposed_at(s)]
        else:
            others = [s for s in hidden[1:] if tg(s) not in bijie and exposed_at(s)]
            if others:
                path.append("G-205")
                candidates += [cand("G-205", s, "中余气透出", "parallel" if len(others) > 1 else "primary") for s in others]
                candidates.append(cand("G-205", main, "本气（未透，保留）", "retained", []))
            else:
                path.append("G-206")
                candidates.append(cand("G-206", main, "本气（藏干全不透）", "primary_unexposed", []))
    # G-207 会局：月支参与完整三合/三会，且局五行异于本气五行
    rel = detail["branch_relations"]
    for g in rel["three_harmonies"] + rel["three_meetings"]:
        if "month" in g["positions"] and g["element"] != stem_element(main, r):
            # 局只有五行、没有阴阳，只给出十神类别（如「食伤」），不虚构正偏
            cat = {"比肩": "比劫", "劫财": "比劫", "食神": "食伤", "伤官": "食伤", "偏财": "财", "正财": "财",
                   "七杀": "官杀", "正官": "官杀", "偏印": "印", "正印": "印"}[tg(next(x for x in r["stems"] if stem_element(x, r) == g["element"]))]
            path.append("G-207")
            candidates.append({"ge": f"{cat}（{g['relation']}{g['element']}局）", "ten_god": cat, "stem": None, "rule": "G-207",
                               "role": f"{g['relation']}{''.join(g['branches'])}", "status": "needs_review", "exposed_at": []})
    named = [c for c in candidates if c.get("ge") and c["status"] in ("primary", "primary_unexposed", "classified", "parallel")]
    status = "single" if len(named) == 1 and len(candidates) == 1 else "parallel_or_review"
    return {"id": gs["id"], "path": path, "candidates": candidates, "status": status,
            "limits": gs["limits"], "source": gs["source"]}


def _ten_god_presence(detail: dict) -> dict:
    """每个十神：透于哪些天干位、藏于哪些地支（含是否本气）。日主自身不计。"""
    pres: dict = {}
    for p, t in detail["visible_ten_gods"].items():
        pres.setdefault(t, {"visible": [], "hidden": []})["visible"].append(p)
    for p in POSITIONS:
        for i, h in enumerate(detail["hidden_stems"][p]):
            pres.setdefault(h["ten_god"], {"visible": [], "hidden": []})["hidden"].append({"position": p, "stem": h["stem"], "main_qi": i == 0})
    return pres


def eval_patterns(detail: dict, r: dict) -> list[dict]:
    """P-100 十神组合格局：只判断结构出现的程度（formed/partial/latent/absent），附加重、化解与未判条件。"""
    cp = r["combination_patterns"]
    pres = _ten_god_presence(detail)
    vis_idx = {"year": 0, "month": 1, "hour": 3}
    combos = detail["stem_relations"]["five_combinations"]
    combined_pos = {q for c in combos for q in c["positions"] if q != "day"}

    def side(tgs):
        v = sorted({p for t in tgs for p in pres.get(t, {}).get("visible", [])}, key=vis_idx.get)
        h = [x for t in tgs for x in pres.get(t, {}).get("hidden", [])]
        return {"ten_gods": tgs, "visible": v, "hidden": h}

    def level(a, b):
        if a["visible"] and b["visible"]:
            return "formed"
        if (a["visible"] or a["hidden"]) and (b["visible"] or b["hidden"]):
            return "partial" if (a["visible"] or b["visible"]) else "latent"
        return "absent"

    def factors(items, exclude):
        out = []
        for f in items:
            if f["ten_gods"] == ["__combined__"]:
                hit = sorted(exclude & combined_pos, key=vis_idx.get)
                out.append({**f, "present": bool(hit), "visible": hit, "hidden": []})
                continue
            s = side(f["ten_gods"])
            out.append({**f, "present": bool(s["visible"] or s["hidden"]), "visible": s["visible"], "hidden": s["hidden"]})
        return out

    results = []
    for pat in cp["patterns"]:
        a = side(pat["a"])
        if pat["kind"] == "pair":
            b = side(pat["b"])
            lv = level(a, b)
            parties = {"a": a, "b": b}
            dist = min((abs(vis_idx[x] - vis_idx[y]) for x in a["visible"] for y in b["visible"]), default=None)
        elif pat["kind"] == "combined_sha":
            hits = [c for c in combos if any(q in a["visible"] for q in c["positions"])]
            lv = "formed" if hits else "absent"
            parties = {"a": a, "combinations": hits}
            dist = None
        else:  # yangren_sha
            ren = r["classical_tables"]["lu_yangren"]["yangren"].get(detail["day_master"])
            ren_pos = [p for p in POSITIONS if ren and detail["branches"][p] == ren]
            has_sha = bool(a["visible"] or a["hidden"])
            lv = ("formed" if a["visible"] else "partial") if ren_pos and has_sha else "absent"
            parties = {"a": a, "yangren_branch": ren, "yangren_positions": ren_pos}
            dist = None
        party_pos = set(a["visible"]) | set(parties.get("b", {}).get("visible", []))
        rec = {"id": pat["id"], "name": pat["name"], "aliases": pat["aliases"], "tag": pat["tag"], "level": lv, "parties": parties,
               "visible_distance": dist, "adjacent": dist == 1 if dist is not None else None,
               "combined_parties": sorted(party_pos & combined_pos, key=vis_idx.get),
               "aggravate": factors(pat["aggravate"], party_pos), "relief": factors(pat["relief"], party_pos),
               "relief_unsourced": [{**f, "present": any(side([t])["visible"] or side([t])["hidden"] for t in f["ten_gods"])} for f in pat["relief_unsourced"]],
               "unresolved": pat["unresolved"], "quotes": pat["quotes"], "final_judgement": False}
        results.append(rec)
    return results


def strength_hypothesis(detail: dict, r: dict, hid: str = "STRENGTH-H1") -> dict:
    """假设层：编者自定权重的帮身/耗身比，附 9 组权重的敏感性检验。不进入任何规则。"""
    h = r["hypotheses"][hid]
    support = {"比肩", "劫财", "正印", "偏印"}

    def ratio(w_vis, hidden_w, month_mul):
        sup = tot = 0.0
        for p in ("year", "month", "hour"):
            tot += w_vis
            sup += w_vis if detail["visible_ten_gods"][p] in support else 0
        for p in POSITIONS:
            mul = month_mul if p == "month" else 1.0
            for i, hs in enumerate(detail["hidden_stems"][p]):
                w = hidden_w[min(i, len(hidden_w) - 1)] * mul
                tot += w
                sup += w if hs["ten_god"] in support else 0
        return sup / tot

    def label(x):
        return "偏强" if x > 0.55 else ("偏弱" if x < 0.45 else "中间")
    w = h["weights"]
    base = ratio(w["visible_stem"], w["hidden_by_order"], w["month_branch_multiplier"])
    grid = []
    for m in h["sensitivity_grid"]["month_branch_multiplier"]:
        for hw in h["sensitivity_grid"]["hidden_by_order"]:
            x = ratio(w["visible_stem"], hw, m)
            grid.append({"month_branch_multiplier": m, "hidden_by_order": hw, "ratio": round(x, 3), "label": label(x)})
    labels = {g["label"] for g in grid}
    return {"id": hid, "layer": "hypothesis", "status": h["status"], "weights": w, "ratio": round(base, 3), "label": label(base),
            "sensitivity": grid, "ratio_range": [min(g["ratio"] for g in grid), max(g["ratio"] for g in grid)],
            "stable": len(labels) == 1,
            "note": "标签只随假设权重而定；stable=false 表示换一组同样任意的权重就会改变结论"}


def visible_stems(stem_map: dict) -> set[str]:
    return {stem_map[p] for p in ("year", "month", "hour")}


def _leaf(expr: dict, facts: dict) -> bool:
    if expr.get("fact") not in facts:
        raise RulebookError(f"规则引用了不存在的事实字段: {expr.get('fact')}")
    a = facts[expr["fact"]]
    op = expr["op"]
    if op == "eq":
        return a == expr["value"]
    if op == "in":
        return a in expr["values"]
    if op == "gte":
        return a >= expr["value"]
    if op == "contains":
        return expr["value"] in a
    if op == "contains_any":
        return any(v in a for v in expr["values"])
    raise RulebookError(f"未知谓词 op: {op}")


def evaluate_expr(expr: dict, facts: dict) -> bool:
    if "all" in expr:
        return all(evaluate_expr(x, facts) for x in expr["all"])
    if "any" in expr:
        return any(evaluate_expr(x, facts) for x in expr["any"])
    if "not" in expr:
        return not evaluate_expr(expr["not"], facts)
    return _leaf(expr, facts)


def explain_expr(expr: dict, facts: dict) -> list[dict]:
    """每个叶子条件的期望值、实际值与是否满足；用于说明未命中规则差在哪里。"""
    if "all" in expr or "any" in expr:
        return [c for x in expr.get("all", expr.get("any")) for c in explain_expr(x, facts)]
    if "not" in expr:
        return [{**c, "negated": True} for c in explain_expr(expr["not"], facts)]
    expected = expr.get("value", expr.get("values"))
    return [{"fact": expr["fact"], "op": expr["op"], "expected": expected, "actual": facts[expr["fact"]], "satisfied": _leaf(expr, facts)}]


def collect_fact_refs(expr: dict) -> set[str]:
    if "all" in expr:
        return set().union(*(collect_fact_refs(e) for e in expr["all"]))
    if "any" in expr:
        return set().union(*(collect_fact_refs(e) for e in expr["any"]))
    if "not" in expr:
        return collect_fact_refs(expr["not"])
    return {expr["fact"]}


def screen_rules(facts: dict, r: dict) -> tuple[list[dict], list[dict]]:
    fired, audit = [], []
    for rule in r["rules"]:
        ok = evaluate_expr(rule["when"], facts)
        evidence = {k: facts[k] for k in sorted(collect_fact_refs(rule["when"]))}
        conditions = explain_expr(rule["when"], facts)
        trace = {"id": rule["id"], "type": "traditional_screening", "name": rule["name"], "matched": ok, "evidence": evidence,
                 "conditions": conditions, "source": rule["source"], "limitations": rule["uncertainty"]}
        audit.append(trace)
        if ok:
            fired.append({"id": rule["id"], "name": rule["name"], "tag": rule["then"]["tag"], "note": rule["then"]["text"], "evidence": evidence, "source": rule["source"], "final_judgement": False})
    return fired, audit


def luck_pillar_sequence(month: str, direction: str, count: int, r: dict, start_age: float | None = None) -> list[dict]:
    """Sequence; start age only when an explicit luck policy supplied it."""
    if direction not in ("forward", "reverse"):
        raise RulebookError("大运方向只能显式给定 forward 或 reverse")
    if not isinstance(count, int) or not 1 <= count <= 20:
        raise RulebookError("大运数量须为1至20的整数")
    validate_pillar(month, r)
    base = pair_index(month, r)
    increment = 1 if direction == "forward" else -1
    return [{"ordinal": k, "pillar": index_pair(base + increment * k, r), "period_years": 10,
             "start_age": "未计算：须先确认起运方向与起运折算规则" if start_age is None else round(start_age + 10 * (k - 1), 2)}
            for k in range(1, count + 1)]


def _years_months_days(years: float) -> dict:
    y = int(years)
    months_f = (years - y) * 12
    m = int(months_f)
    d = round((months_f - m) * 30)
    if d == 30:
        m, d = m + 1, 0
    if m == 12:
        y, m = y + 1, 0
    return {"years": y, "months": m, "days": d}


def luck_start(request: dict, pillars: dict, meta: dict, terms: list[dict], r: dict) -> tuple[str, dict]:
    pid = request["luck_policy"]
    policy = r.get("luck_policies", {}).get(pid)
    if policy is None:
        raise RulebookError(f"未定义的起运政策: {pid}；可用: {sorted(r.get('luck_policies', {}))}")
    gender = request.get("gender")
    if gender not in ("male", "female"):
        raise RulebookError(f"{pid} 需要显式 gender: male 或 female")
    if "birth_time" not in request:
        raise RulebookError("起运年龄需要出生时刻与交节表；仅提供四柱时只能排列序列")
    direction = policy["direction"][gender][r["stem_yinyang"][pillars["year"][0]]]
    if request.get("luck_direction") not in (None, direction):
        raise RulebookError(f"luck_direction={request['luck_direction']} 与 {pid} 推得的 {direction} 矛盾；不自动择一")
    birth = parse_aware(request["birth_time"]).astimezone(timezone.utc)
    target_name = meta["next_jie"]["name"] if direction == "forward" else meta["previous_jie"]["name"]
    target = next(x for x in terms if x["name"] == target_name and x["at"] == (meta["next_jie"] if direction == "forward" else meta["previous_jie"])["at"])
    span = abs((target["instant"] - birth).total_seconds())
    years = span / 86400 / policy["conversion"]["days_per_year"]
    start_at = birth + timedelta(days=years * TROPICAL_YEAR_DAYS)
    info = {"policy_id": pid, "policy_name": policy["name"], "gender": gender, "year_stem_polarity": r["stem_yinyang"][pillars["year"][0]],
            "direction": direction, "counted_to_jie": {"name": target["name"], "at": target["at"]}, "span_days": round(span / 86400, 4),
            "start_age_years": round(years, 4), "start_age_ymd": _years_months_days(years),
            "approx_start_date": start_at.astimezone(parse_aware(request["birth_time"]).tzinfo).date().isoformat(),
            "source": policy["source"],
            "note": "起运年龄为所选政策的约定性折算，起运日期按回归年近似换算；不同书籍口径不同"}
    return direction, info


def _resolve_terms(request: dict, terms: list[dict] | None) -> list[dict]:
    if terms is not None:
        return terms
    if DEFAULT_TERMS.exists():
        return load_terms(DEFAULT_TERMS)
    raise RulebookError("birth_time 模式必须提供经过核查的节气交节表")


def solve(request: dict, r: dict, terms: list[dict] | None = None) -> dict:
    if "birth_time_range" in request:
        return solve_range(request, r, _resolve_terms(request, terms))
    trace, meta = [], {"mode": "four_pillars_supplied"}
    if "pillars" in request:
        pillars = request["pillars"]
        if set(pillars.keys()) != set(POSITIONS):
            raise RulebookError("四柱输入必须恰好具有 year、month、day、hour 四个键")
        trace.append({"id": "C-000", "type": "externally_supplied", "result": pillars, "method": "四柱由外部输入；未独立验证其对应出生日期"})
    elif "birth_time" in request:
        terms = _resolve_terms(request, terms)
        pillars, trace, meta = compute_pillars(request, r, terms)
        meta["mode"] = "computed_from_birth_time"
    else:
        raise RulebookError("需要 birth_time、birth_time_range 或 pillars 输入")
    detail, structural_trace = analyze_structure(pillars, r)
    days_since_jie = None
    if meta.get("previous_jie"):
        prev = next(t for t in terms if t["at"] == meta["previous_jie"]["at"])
        days_since_jie = (parse_aware(request["birth_time"]).astimezone(timezone.utc) - prev["instant"]).total_seconds() / 86400
    classical, classical_trace = classical_lookup(detail, r, days_since_jie, request.get("wangxiang_policy"))
    detail["classical"] = classical
    detail["facts"].update({"day_master_season_state": classical["wangxiang"]["day_master_state"],
                            "day_master_changsheng_month": classical["changsheng"]["day_master_on"]["month"],
                            "siling_ten_god": classical["renyuan_siling"].get("ten_god"),
                            "tiaohou_primary_visible": classical["tiaohou"]["primary_visible"]})
    structural_trace += classical_trace
    if "geju_selection" in r:
        detail["geju"] = select_geju(detail, r)
        detail["facts"]["geju_path"] = detail["geju"]["path"]
        structural_trace.append({"id": "G-200", "type": "geju_selection", "result": detail["geju"],
                                 "method": "按 geju_selection.order 固定次序取格；只产生候选，不判成败"})
    if "combination_patterns" in r:
        detail["patterns"] = eval_patterns(detail, r)
        detail["facts"]["patterns_formed"] = [x["id"] for x in detail["patterns"] if x["level"] == "formed"]
        structural_trace.append({"id": "P-100", "type": "combination_patterns",
                                 "result": [{k: x[k] for k in ("id", "name", "level")} for x in detail["patterns"]],
                                 "method": "两类十神同现（透/藏）、七杀被合、羊刃见杀；只判结构程度，不判成败"})
    candidates, rule_trace = screen_rules(detail["facts"], r)
    luck, luck_info = None, None
    direction = request.get("luck_direction")
    if "luck_policy" in request:
        direction, luck_info = luck_start(request, pillars, meta, terms, r)
        rule_trace.append({"id": "C-202", "type": "computed_with_explicit_policy", "method": "按显式起运政策求顺逆与起运年龄", "result": luck_info})
    if direction is not None:
        start_age = luck_info["start_age_years"] if luck_info else None
        luck = luck_pillar_sequence(pillars["month"], direction, request.get("num_luck_periods", 8), r, start_age)
        rule_trace.append({"id": "C-201", "type": "computed_with_explicit_policy", "method": "月柱六十甲子序号按顺逆方向逐项加减1", "result": luck, "policy": {"direction": direction, "count": len(luck)}})
    unresolved = ["格局兼格/变化的最终优先级", "强弱轻重及救应成立条件", "用神最终确认与大运流年解释", "现实事件预测可靠性"]
    if meta.get("boundary_alerts"):
        unresolved.insert(0, "出生时刻贴近交节，年/月柱存在并列可能（见 meta.boundary_alerts）")
    if "pillars" in request:
        unresolved.insert(0, "四柱由用户输入，未独立校验出生时刻")
    return {
        "engine_version": ENGINE_VERSION,
        "rules_version": r.get("schema_version"),
        "model": "子平月令格局法 / 确定性计算 + 传统候选初筛",
        "scope": "文化性、规则性分析；非经科学验证的人生预测",
        "input": request,
        "meta": meta,
        "pillars": pillars,
        "computed": detail,
        "traditional_candidates": candidates,
        "da_yun_start": luck_info,
        "da_yun_sequence": luck,
        "hypotheses": {"STRENGTH-H1": strength_hypothesis(detail, r)} if "hypotheses" in r else {},
        "conclusion_status": "仅有结构信息与初筛提示；完整格局及喜忌尚未判定",
        "unresolved": unresolved,
        "trace": trace + structural_trace + rule_trace,
    }


def _range_boundaries(start: datetime, end: datetime, request: dict, r: dict, terms: list[dict]) -> list[datetime]:
    """区间内所有可能改变四柱的瞬间：交节瞬间 + 钟表整点（时辰/日界都落在整点上）。"""
    pts = {start}
    names = {x["name"] for x in r["month_jie"]}
    s_utc, e_utc = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    for t in terms:
        if t["name"] in names and s_utc < t["instant"] <= e_utc:
            pts.add(t["instant"].astimezone(start.tzinfo))
    clock_start, _ = _clock(request, start)
    offset = clock_start - start
    h = clock_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    while h - offset <= end:
        pts.add(h - offset)
        h += timedelta(hours=1)
    return sorted(pts)


def solve_range(request: dict, r: dict, terms: list[dict]) -> dict:
    """出生时刻只知区间时：枚举区间内全部可能盘，并列输出，不擅自补分钟。"""
    rng = request["birth_time_range"]
    start, end = parse_aware(rng["start"]), parse_aware(rng["end"]).astimezone(parse_aware(rng["start"]).tzinfo)
    if end < start:
        raise RulebookError("birth_time_range.end 早于 start")
    if (end - start) > timedelta(hours=MAX_RANGE_HOURS):
        raise RulebookError(f"时间区间超过 {MAX_RANGE_HOURS} 小时，请缩小范围")
    base = {k: v for k, v in request.items() if k != "birth_time_range"}
    segments: list[dict] = []
    for b in _range_boundaries(start, end, request, r, terms):
        p, _ = _pillars_at(b, base, r, terms)
        if segments and segments[-1]["pillars"] == p:
            continue
        if segments:
            segments[-1]["to"] = b.isoformat()
        segments.append({"from": b.isoformat(), "pillars": p})
    segments[-1]["to"] = end.isoformat()
    charts = []
    for seg in segments:
        res = solve({**base, "birth_time": seg["from"]}, r, terms)
        charts.append({"interval": {"from": seg["from"], "to_exclusive": seg["to"]}, "result": res})
    return {
        "engine_version": ENGINE_VERSION,
        "rules_version": r.get("schema_version"),
        "mode": "birth_time_range",
        "input": request,
        "possible_chart_count": len(charts),
        "charts": charts,
        "conclusion_status": "出生时刻只知区间；以下各盘并列，不择一" if len(charts) > 1 else "区间内四柱唯一",
    }


# ---------------------------------------------------------------- 报告渲染

def _fmt_val(v: Any) -> str:
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, list):
        return "、".join(map(str, v)) if v else "（无）"
    return str(v)


OP_CN = {"eq": "等于", "in": "属于", "gte": "≥", "contains": "包含", "contains_any": "包含任一"}


def _render_classical(cl: dict, stems: dict) -> list[str]:
    L = ["## D2. 古籍查表（L-301–L-304，只查表、不加权）", ""]
    sl = cl["renyuan_siling"]
    if sl.get("status") == "unresolved":
        L.append(f"- L-301 人元司令：暂不判定（{sl['reason']}）")
    else:
        segs = "、".join(f"{x['stem']}{x['days']}日" for x in sl["month_segments"])
        L.append(f"- L-301 人元司令（《三命通会·论人元司事》）：交节后第 {sl['days_since_jie']:.2f} 日，本月分日 {segs} → "
                 f"**{sl['stem']}**司令（原文「{sl['literal']}」，对日主为{sl['ten_god']}）" + ("；已超过 30 日，按末段计" if sl["capped"] else ""))
    wx = cl["wangxiang"]
    states = "、".join(f"{k}{v}" for k, v in wx["by_element"].items())
    alt = "；".join(f"{k}：{v}" for k, v in wx["alternatives"].items())
    L.append(f"- L-302 旺相休囚死（政策 {wx['policy']}）：当令{wx['season_element']}，{states}；日主处**{wx['day_master_state']}**。各政策对照：{alt}")
    cs = cl["changsheng"]
    L.append("- L-303 十二长生：日主坐" + "、".join(f"{POS_CN[p]}支{v}" for p, v in cs["day_master_on"].items())
             + "；各干坐本柱支：" + "、".join(f"{POS_CN[p]}{stems[p]}{v}" for p, v in cs["stem_on_own_branch"].items()))
    th = cl["tiaohou"]

    def pres(s):
        x = th["presence"][s]
        v = "、".join(POS_CN[p] + "干" for p in x["visible"])
        h = "、".join(POS_CN[p] + "支藏" for p in x["hidden"])
        return f"{s}（{x['ten_god']}；" + ("明见于" + v if v else "天干未见") + ("，" + h if h else "，地支不藏") + "）"
    L.append(f"- L-304 穷通宝鉴调候（{th['basis']}，原文第 {th['source_line']} 行）：首用 " + "、".join(pres(s) for s in th["primary"])
             + ("；次用 " + "、".join(pres(s) for s in th["secondary"]) if th["secondary"] else ""))
    L.append(f"  - 原文：「{th['quote']}」")
    if th.get("condition_note"):
        L.append(f"  - 条件：{th['condition_note']}")
    L.append("  - 调候与月令格局是两个体系，此处并列，不合并、不据此定喜忌。")
    return L + [""]


def _render_geju(g: dict | None) -> list[str]:
    if not g:
        return []
    L = [f"## D3. 月令取格（G-200，路径 {' → '.join(g['path'])}）", "", "| 候选 | 十神 | 来源 | 规则 | 状态 | 透于 |", "|:--|:--|:--|:--|:--|:--|"]
    for c in g["candidates"]:
        L.append(f"| {c.get('ge') or '（无）'} | {c.get('ten_god', '')} | {c.get('role', '')} | {c['rule']} | {c['status']} | "
                 f"{'、'.join(POS_CN[p] + '干' for p in c.get('exposed_at', [])) or '—'} |")
    L += ["", f"- 只决定取哪个格的候选，不判成败；{g['source']['verification']}。", ""]
    return L


LEVEL_CN = {"formed": "明见（两方透干）", "partial": "半见（一透一藏）", "latent": "暗藏（两方只在地支）"}


def _render_patterns(pats: list | None) -> list[str]:
    if pats is None:
        return []
    shown = [p for p in pats if p["level"] != "absent"]
    L = ["## D4. 十神组合格局（P-100，只判结构、不判成败）", ""]
    if not shown:
        return L + ["- 16 条组合规则均未出现。", ""]

    def where(side):
        v = "、".join(POS_CN[q] + "干" for q in side.get("visible", []))
        h = "、".join(f"{POS_CN[x['position']]}支藏{x['stem']}" for x in side.get("hidden", []))
        return "；".join(x for x in (v, h) if x) or "—"
    order = {"formed": 0, "partial": 1, "latent": 2}
    for p in sorted(shown, key=lambda x: (order[x["level"]], x["id"])):
        alias = f"（{'、'.join(p['aliases'])}）" if p["aliases"] else ""
        L.append(f"### {p['id']} {p['name']}{alias} · {LEVEL_CN[p['level']]}")
        pa = p["parties"]
        if "b" in pa:
            L.append(f"- {'/'.join(pa['a']['ten_gods'])}：{where(pa['a'])}　｜　{'/'.join(pa['b']['ten_gods'])}：{where(pa['b'])}"
                     + ("（年月相邻）" if p["adjacent"] else ("（隔位）" if p["visible_distance"] else "")))
        elif "combinations" in pa:
            L.append("- " + "；".join(f"{'、'.join(POS_CN[q] for q in c['positions'])}干 {''.join(c['stems'])} 五合" for c in pa["combinations"]))
        else:
            L.append(f"- 七杀：{where(pa['a'])}　｜　羊刃 {pa['yangren_branch']}：在{'、'.join(POS_CN[q] + '支' for q in pa['yangren_positions'])}")
        if p["combined_parties"]:
            L.append(f"- 当事干被合：{'、'.join(POS_CN[q] + '干' for q in p['combined_parties'])}（合而化否未判）")
        for lab, key in (("加重", "aggravate"), ("化解", "relief")):
            for f in p[key]:
                state = ("出现：" + where(f)) if f["present"] else "未出现"
                L.append(f"- {lab}·{f['effect']}：{state}（{f['quote']['book']}「{f['quote']['text']}」）")
        for f in p["relief_unsourced"]:
            L.append(f"- 提示（无原文依据）：{f['note']}；{'/'.join(f['ten_gods'])}{'出现' if f['present'] else '未出现'}")
        L.append("- 原文：" + "；".join(f"{q['book']}「{q['text']}」" for q in p["quotes"]))
        L.append("- 未判：" + "；".join(p["unresolved"]))
        L.append("")
    absent = [p["id"] + p["name"] for p in pats if p["level"] == "absent"]
    L += [f"未出现：{'、'.join(absent)}", ""]
    return L


def _render_hypothesis(hyps: dict) -> list[str]:
    h = hyps.get("STRENGTH-H1")
    if not h:
        return []
    w = h["weights"]
    L = ["", "## G2. 假设层（STRENGTH-H1，非古籍）", "",
         f"- **性质**：{h['status']}。",
         f"- 默认权重：明干 {w['visible_stem']}，藏干按序 {w['hidden_by_order']}，月支 ×{w['month_branch_multiplier']} → 帮身比 {h['ratio']}（{h['label']}）",
         f"- 敏感性：9 组权重下帮身比 {h['ratio_range'][0]}–{h['ratio_range'][1]}，标签" + ("一致（stable）" if h["stable"] else "**不一致（unstable）**，结论依赖任意权重")]
    return L


def render_markdown(result: dict) -> str:
    """按《AI_执行指令》A–H 固定次序输出；所有句子均由模板生成，无自由发挥。"""
    if result.get("mode") == "birth_time_range":
        out = [f"# 八字规则报告（时间区间，共 {result['possible_chart_count']} 个可能盘）", "", result["conclusion_status"], ""]
        for i, ch in enumerate(result["charts"], 1):
            iv = ch["interval"]
            out += [f"---", "", f"# 可能盘 {i}：{iv['from']} 起，至 {iv['to_exclusive']} 前", ""]
            out += render_markdown(ch["result"]).split("\n")[1:]
        return "\n".join(out)
    m, c, p = result["meta"], result["computed"], result["pillars"]
    L = ["# 八字规则报告", ""]
    L += ["## A. 输入与时间政策", ""]
    if m["mode"] == "four_pillars_supplied":
        L.append("- 四柱由用户输入，未独立校验出生时刻。")
    else:
        L += [f"- 出生时刻：{m['input_birth']}", f"- 钟表政策：{m['clock_mode']}；用于日/时柱的有效钟表时刻：{m['effective_clock']}",
              f"- 换日政策：{m['day_boundary']}；年界：立春交节瞬间；月界：十二节交节瞬间", f"- 交节数据：{m['term_source']}"]
    L += ["", "## B. 四柱", "", "| 年 | 月 | 日 | 时 |", "|:-:|:-:|:-:|:-:|", "| " + " | ".join(p[x] for x in POSITIONS) + " |", ""]
    if m["mode"] != "four_pillars_supplied":
        L.append(f"- 节气依据：上一节 {m['previous_jie']['name']} {m['previous_jie']['at']}；下一节 {m['next_jie']['name']} {m['next_jie']['at']}")
        for a in m.get("boundary_alerts", []):
            L.append(f"- **交节临界**：距 {a['jie']}（{a['jie_at']}）{a['seconds_from_jie']} 秒，小于容差 {a['margin_seconds']} 秒；"
                     f"另一侧为 {a['alternative_year_month']['year']}年 {a['alternative_year_month']['month']}月，两者并列待复核。")
    vt = c["visible_ten_gods"]
    L += ["", "## C. 日主与明干十神", "", f"- 日主：{c['day_master']}（{c['facts']['day_master_element']}）",
          f"- 年干 {c['stems']['year']}：{vt['year']}；月干 {c['stems']['month']}：{vt['month']}；时干 {c['stems']['hour']}：{vt['hour']}", ""]
    L += ["## D. 藏干、月令本气与透干", "", "| 柱 | 地支 | 藏干（十神） |", "|:-:|:-:|:--|"]
    for pos in POSITIONS:
        hs = "、".join(f"{h['stem']}（{h['ten_god']}{'·本气' if h['status'] == '本气' else ''}）" for h in c["hidden_stems"][pos])
        L.append(f"| {POS_CN[pos]} | {c['branches'][pos]} | {hs} |")
    mq = c["month_main_qi"]
    L += ["", f"- 月令本气：{mq['stem']}，对日主为{mq['ten_god']}；本气{'已' if c['facts']['month_primary_exposed'] else '未'}透出",
          f"- 月令透出藏干：{_fmt_val(c['month_hidden_exposed'])}", ""]
    L += _render_classical(c["classical"], c["stems"])
    L += _render_geju(c.get("geju"))
    L += _render_patterns(c.get("patterns"))
    L += ["## E. 干支关系（仅结构事实）", ""]
    rel_lines = []
    for x in c["stem_relations"]["five_combinations"]:
        rel_lines.append(f"- 天干五合：{'、'.join(POS_CN[q] for q in x['positions'])}干 {''.join(x['stems'])}（合{x['element']}）— {x['status']}")
    for key in ("six_clashes", "six_harmonies", "six_harms"):
        for x in c["branch_relations"][key]:
            rel_lines.append(f"- {x['relation']}：{'、'.join(POS_CN[q] for q in x['positions'])}支 {''.join(x['branches'])} — {x['status']}")
    for key in ("three_harmonies", "three_meetings"):
        for x in c["branch_relations"][key]:
            rel_lines.append(f"- {x['relation']}{x['element']}：{''.join(x['branches'])} — {x['status']}")
    for x in c["branch_relations"]["punishments"]:
        rel_lines.append(f"- 刑（{x['relation']}，{x['completeness']}）：{''.join(x['branches'])} — {x['status']}")
    L += rel_lines or ["- 未发现表中所列关系。"]
    L += ["", "## F. 经典规则候选", ""]
    rule_trace = [t for t in result["trace"] if t.get("type") == "traditional_screening"]
    matched = [t for t in rule_trace if t["matched"]]
    if matched:
        L += ["| 规则 | 名称 | 触发事实 | 出处 |", "|:--|:--|:--|:--|"]
        for t in matched:
            ev = "；".join(f"{k}={_fmt_val(v)}" for k, v in t["evidence"].items())
            L.append(f"| {t['id']} | {t['name']} | {ev} | 《{t['source']['book']}》〈{t['source']['section']}〉 |")
        L.append("")
        for cnd in result["traditional_candidates"]:
            L.append(f"- {cnd['id']}（{cnd['tag']}）：{cnd['note']}")
    else:
        L.append("- 无规则命中。")
    L += ["", "未命中规则及未满足条件：", ""]
    for t in rule_trace:
        if t["matched"]:
            continue
        miss = [f"{x['fact']} {OP_CN.get(x['op'], x['op'])} {_fmt_val(x['expected'])}（实际 {_fmt_val(x['actual'])}）"
                for x in t["conditions"] if not x["satisfied"]]
        L.append(f"- {t['id']} {t['name']}：" + ("；".join(miss) if miss else "条件组合不成立"))
    if result.get("da_yun_sequence"):
        L += ["", "### 大运序列", ""]
        s = result.get("da_yun_start")
        if s:
            ymd = s["start_age_ymd"]
            L.append(f"- 政策 {s['policy_id']}：{s['policy_name']}。年干{s['year_stem_polarity']}、{'男' if s['gender'] == 'male' else '女'} → "
                     f"{'顺行' if s['direction'] == 'forward' else '逆行'}；数至 {s['counted_to_jie']['name']}（{s['counted_to_jie']['at']}），"
                     f"相距 {s['span_days']} 日 → 起运约 {ymd['years']} 岁 {ymd['months']} 个月 {ymd['days']} 日（约 {s['approx_start_date']}）。")
        else:
            L.append("- 方向由输入显式指定；未声明起运政策，不计算起运年龄。")
        L.append("- " + " → ".join(f"{x['pillar']}" + (f"({x['start_age']}岁)" if isinstance(x['start_age'], (int, float)) else "") for x in result["da_yun_sequence"]))
    L += ["", "## G. 尚未判断的冲突与缺失条件", ""]
    conflicts = [cnd for cnd in result["traditional_candidates"] if cnd["tag"] in ("conflict", "needs_review", "risk")]
    for cnd in conflicts:
        L.append(f"- {cnd['id']} {cnd['name']}：待人工审校。")
    L += [f"- {u}：暂不判定。" for u in result["unresolved"]]
    L += _render_hypothesis(result.get("hypotheses", {}))
    L += ["", "## H. 结论性质与适用边界", "", f"- {result['conclusion_status']}。",
          "- 以上为按规则表执行的历法计算与传统结构初筛；所有候选 final_judgement=false。",
          "- 传统命理未被证明能预测现实事件；本报告不对职业、财富、健康、婚姻、寿命作任何事实性结论。",
          f"- 引擎 {result['engine_version']}，规则表 {result['rules_version']}。", ""]
    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser(description="子平八字 AI 规则引擎，输出可审计 JSON 或报告（非命运预测）")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", help="带 birth_time / birth_time_range / pillars 的 JSON 输入文件")
    src.add_argument("--birth", help="出生时刻，如 1990-05-17T08:30:00+08:00")
    src.add_argument("--pillars", help="四柱，逗号分隔，如 甲辰,丙寅,戊戌,庚申")
    parser.add_argument("--gender", choices=["male", "female"], help="配合 --luck-policy 推起运")
    parser.add_argument("--luck-policy", help="起运政策 ID，如 LUCK-P1")
    parser.add_argument("--day-boundary", choices=["00:00", "23:00"])
    parser.add_argument("--rules", default=str(HERE / "rules.json"))
    parser.add_argument("--terms", help=f"交节时刻 JSON；默认 {DEFAULT_TERMS.name}")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--output", help="结果文件；不提供则打印到终端")
    args = parser.parse_args()
    if args.input:
        request = read_json(args.input)
    elif args.birth:
        request = {"birth_time": args.birth, "calendar_policy": "solar_jie", "day_boundary": "00:00", "clock_mode": "civil"}
    else:
        parts = [x.strip() for x in args.pillars.replace("，", ",").split(",")]
        if len(parts) != 4:
            raise RulebookError("--pillars 需要恰好四柱")
        request = {"pillars": dict(zip(POSITIONS, parts))}
    if args.gender:
        request["gender"] = args.gender
    if args.luck_policy:
        request["luck_policy"] = args.luck_policy
    if args.day_boundary:
        request["day_boundary"] = args.day_boundary
    result = solve(request, read_json(args.rules), load_terms(args.terms) if args.terms else None)
    rendered = render_markdown(result) if args.format == "markdown" else json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    try:
        main()
    except RulebookError as e:
        raise SystemExit(f"INVALID_INPUT_OR_RULES: {e}")
