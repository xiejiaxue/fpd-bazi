# -*- coding: utf-8 -*-
"""Python 标准库 unittest：换年、换月、换日、时辰、十神、互斥及拒绝猜测；V1.1 起含全年代交节表、区间盘、起运政策与报告。"""
import random
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from bazi_engine import (
    POSITIONS,
    read_json, load_terms, solve, day_pillar, ten_god,
    index_pair, RulebookError, validate_pillar, DEFAULT_TERMS, render_markdown,
    changsheng_stage, renyuan_siling
)

D = Path(__file__).resolve().parent
R = read_json(D/'rules.json')
T = load_terms(D/'terms_2024_example.json')
TF = load_terms(DEFAULT_TERMS)


def run_birth(at: str, **kw):
    req = {'birth_time': at, 'calendar_policy':'solar_jie','day_boundary':'00:00','clock_mode':'civil'}
    req.update(kw)
    return solve(req,R,T)


class CoreTest(unittest.TestCase):
    def test_cycle_60(self):
        self.assertEqual(index_pair(0,R),'甲子')
        self.assertEqual(index_pair(59,R),'癸亥')
        self.assertEqual(index_pair(60,R),'甲子')

    def test_date_anchor_and_external_reference(self):
        self.assertEqual(day_pillar(date(2000,1,1),R)[0],'戊午')
        self.assertEqual(day_pillar(date(2000,1,2),R)[0],'己未')
        self.assertEqual(day_pillar(date(2019,1,27),R)[0],'甲子')

    def test_stem_five_tiger(self):
        expected=['丙','戊','庚','壬','甲','丙','戊','庚','壬','甲']
        self.assertEqual([R['five_tiger_yin_month_start'][s] for s in R['stems']],expected)

    def test_stem_five_rat(self):
        expected=['甲','丙','戊','庚','壬','甲','丙','戊','庚','壬']
        self.assertEqual([R['five_rat_zi_hour_start'][s] for s in R['stems']],expected)

    def test_ten_gods_jia_complete(self):
        expected='比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印'.split()
        self.assertEqual([ten_god('甲',s,R) for s in R['stems']],expected)

    def test_lichun_same_date_diff_year_month(self):
        before=run_birth('2024-02-04T16:20:00+08:00')
        after=run_birth('2024-02-04T16:30:00+08:00')
        self.assertEqual(before['pillars'], dict(year='癸卯',month='乙丑',day='戊戌',hour='庚申'))
        self.assertEqual(after['pillars'], dict(year='甲辰',month='丙寅',day='戊戌',hour='庚申'))

    def test_inclusive_boundary(self):
        x=run_birth('2024-02-04T16:26:53+08:00')
        self.assertEqual(x['pillars']['year'],'甲辰')
        self.assertEqual(x['pillars']['month'],'丙寅')

    def test_jingzhe_month_boundary(self):
        before=run_birth('2024-03-05T10:20:00+08:00')
        after=run_birth('2024-03-05T10:25:00+08:00')
        self.assertEqual(before['pillars']['month'],'丙寅')
        self.assertEqual(after['pillars']['month'],'丁卯')
        self.assertEqual(after['pillars']['year'],'甲辰')

    def test_23_day_boundary_variant(self):
        normal=run_birth('2024-02-04T23:30:00+08:00')
        zishi=run_birth('2024-02-04T23:30:00+08:00',day_boundary='23:00')
        self.assertEqual(normal['pillars']['day'],'戊戌')
        self.assertEqual(normal['pillars']['hour'],'壬子')
        self.assertEqual(zishi['pillars']['day'],'己亥')
        self.assertEqual(zishi['pillars']['hour'],'甲子')
        # 夜子时派：日柱不换，时干按次日（与 lunar_python sect=2 同口径）
        late=run_birth('2024-02-04T23:30:00+08:00',late_zi_hour_stem='next_day')
        self.assertEqual((late['pillars']['day'],late['pillars']['hour']),('戊戌','甲子'))
        with self.assertRaises(RulebookError):
            run_birth('2024-02-04T23:30:00+08:00',late_zi_hour_stem='x')

    def test_case_output_and_uncertainty(self):
        x=run_birth('2024-02-04T16:30:00+08:00')
        self.assertEqual(x['computed']['day_master'],'戊')
        self.assertEqual(x['computed']['visible_ten_gods'],{'year':'七杀','month':'偏印','hour':'食神'})
        self.assertEqual(x['computed']['month_hidden_exposed'],['甲','丙'])
        ids={c['id'] for c in x['traditional_candidates']}
        self.assertIn('G-105',ids)
        self.assertIn('G-109',ids)
        self.assertIn('G-111',ids)
        self.assertTrue(all(not c['final_judgement'] for c in x['traditional_candidates']))
        self.assertGreater(len(x['trace']),10)

    def test_solar_time_year_month_use_real_instant(self):
        raw=run_birth('2024-02-04T16:24:00+08:00')
        adjusted=run_birth('2024-02-04T16:24:00+08:00',clock_mode='mean_solar',longitude_deg_east=121.0,reference_meridian_deg_east=120.0)
        self.assertEqual(raw['pillars']['year'],adjusted['pillars']['year'])
        self.assertEqual(raw['pillars']['month'],adjusted['pillars']['month'])
        self.assertNotEqual(raw['meta']['effective_clock'],adjusted['meta']['effective_clock'])

    def test_reject_incomplete_terms(self):
        with self.assertRaises(RulebookError):
            solve({'birth_time':'2000-01-01T12:00:00+08:00'},R,T)

    def test_reject_naive_time(self):
        with self.assertRaises(RulebookError):
            run_birth('2024-02-04T16:30:00')

    def test_reject_invalid_pillar(self):
        with self.assertRaises(RulebookError):
            validate_pillar('甲丑',R)

    def test_supplied_pillars_matches_computed(self):
        req={'pillars':{'year':'甲辰','month':'丙寅','day':'戊戌','hour':'庚申'}}
        p=solve(req,R,None)
        q=run_birth('2024-02-04T16:30:00+08:00')
        pf, qf = dict(p['computed']['facts']), dict(q['computed']['facts'])
        self.assertIsNone(pf.pop('siling_ten_god'))  # 人元司令需出生时刻
        qf.pop('siling_ten_god')
        self.assertEqual(pf, qf)

    def test_luck_sequence_forward_and_reverse_are_explicit(self):
        from bazi_engine import luck_pillar_sequence
        fw=luck_pillar_sequence('丙寅','forward',3,R)
        rv=luck_pillar_sequence('丙寅','reverse',3,R)
        self.assertEqual([x['pillar'] for x in fw],['丁卯','戊辰','己巳'])
        self.assertEqual([x['pillar'] for x in rv],['乙丑','甲子','癸亥'])
        self.assertEqual(fw[0]['start_age'],'未计算：须先确认起运方向与起运折算规则')
        x=solve({'pillars':{'year':'甲辰','month':'丙寅','day':'戊戌','hour':'庚申'},'luck_direction':'forward'},R)
        self.assertEqual(x['da_yun_sequence'][0]['pillar'],'丁卯')

    def test_all_yang_yin_ten_gods(self):
        # For every day stem, the 10 possible other stems must map bijectively to all 10 deities.
        labels=set('比肩 劫财 食神 伤官 偏财 正财 七杀 正官 偏印 正印'.split())
        for day in R['stems']:
            self.assertEqual({ten_god(day,x,R) for x in R['stems']},labels)


class EphemerisTableTest(unittest.TestCase):
    """terms_1900_2100.json 由 JPL DE440s 生成；与北京市文物局 2024 表的差异须在已知误差内。"""

    def test_agrees_with_published_2024_within_20s(self):
        gen = {(x['name'], x['at'][:10]): x['instant'] for x in TF}
        for ref in T:
            got = gen[(ref['name'], ref['at'][:10])]
            self.assertLessEqual(abs((got - ref['instant']).total_seconds()), 20, ref)

    def test_twelve_jie_per_year_and_continuous(self):
        names = [x['name'] for x in R['month_jie']]
        for a, b in zip(TF, TF[1:]):
            self.assertEqual(names[(names.index(a['name']) + 1) % 12], b['name'])
            self.assertLess((b['instant'] - a['instant']).days, 33)

    def test_full_coverage_month_progression(self):
        # 1900–2100 每 10 天抽样：月支与交节表一致，年柱只在立春后变
        t = datetime.fromisoformat('1900-01-01T12:00:00+08:00')
        end = datetime.fromisoformat('2100-12-31T12:00:00+08:00')
        while t <= end:
            x = solve({'birth_time': t.isoformat()}, R, TF)
            jie = x['meta']['previous_jie']['name']
            branch = next(m['branch'] for m in R['month_jie'] if m['name'] == jie)
            self.assertEqual(x['pillars']['month'][1], branch)
            t += timedelta(days=10)

    def test_default_table_used_without_terms(self):
        x = solve({'birth_time': '1990-05-17T08:30:00+08:00'}, R)
        self.assertEqual(x['pillars'], dict(year='庚午', month='辛巳', day='壬午', hour='甲辰'))

    def test_outside_coverage_refuses(self):
        with self.assertRaises(RulebookError):
            solve({'birth_time': '2101-03-01T12:00:00+08:00'}, R, TF)
        with self.assertRaises(RulebookError):
            solve({'birth_time': '1899-01-01T12:00:00+08:00'}, R, TF)


class BoundaryAndRangeTest(unittest.TestCase):
    def test_near_jie_lists_alternative(self):
        x = solve({'birth_time': '2024-02-04T16:28:00+08:00'}, R, TF)
        alerts = x['meta']['boundary_alerts']
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['alternative_year_month'], {'year': '癸卯', 'month': '乙丑'})
        self.assertIn('贴近交节', x['unresolved'][0])

    def test_far_from_jie_no_alert(self):
        self.assertEqual(solve({'birth_time': '2024-02-10T12:00:00+08:00'}, R, TF)['meta']['boundary_alerts'], [])

    def test_range_enumerates_all_charts(self):
        x = solve({'birth_time_range': {'start': '2024-02-04T15:00:00+08:00', 'end': '2024-02-04T17:30:00+08:00'}}, R, TF)
        self.assertEqual([c['result']['pillars']['hour'] for c in x['charts']], ['庚申', '庚申', '辛酉'])
        self.assertEqual([c['result']['pillars']['year'] for c in x['charts']], ['癸卯', '甲辰', '甲辰'])
        self.assertEqual(x['charts'][1]['interval']['from'], x['charts'][0]['interval']['to_exclusive'])

    def test_range_single_chart(self):
        x = solve({'birth_time_range': {'start': '2024-02-10T13:05:00+08:00', 'end': '2024-02-10T14:55:00+08:00'}}, R, TF)
        self.assertEqual(x['possible_chart_count'], 1)

    def test_range_respects_23_policy(self):
        x = solve({'birth_time_range': {'start': '2024-02-04T22:00:00+08:00', 'end': '2024-02-05T00:30:00+08:00'}, 'day_boundary': '23:00'}, R, TF)
        self.assertEqual([c['result']['pillars']['day'] + c['result']['pillars']['hour'] for c in x['charts']], ['戊戌癸亥', '己亥甲子'])

    def test_range_limits(self):
        with self.assertRaises(RulebookError):
            solve({'birth_time_range': {'start': '2024-02-01T00:00:00+08:00', 'end': '2024-02-05T00:00:00+08:00'}}, R, TF)
        with self.assertRaises(RulebookError):
            solve({'birth_time_range': {'start': '2024-02-05T00:00:00+08:00', 'end': '2024-02-04T00:00:00+08:00'}}, R, TF)


class LuckPolicyTest(unittest.TestCase):
    def test_p1_male_yang_forward_age(self):
        x = solve({'birth_time': '2024-02-04T16:30:00+08:00', 'gender': 'male', 'luck_policy': 'LUCK-P1'}, R, T)
        s = x['da_yun_start']
        self.assertEqual(s['direction'], 'forward')
        self.assertEqual(s['counted_to_jie']['name'], '惊蛰')
        span = (datetime.fromisoformat('2024-03-05T10:22:31+08:00') - datetime.fromisoformat('2024-02-04T16:30:00+08:00')).total_seconds() / 86400
        self.assertAlmostEqual(s['start_age_years'], span / 3, places=3)
        self.assertEqual(x['da_yun_sequence'][0]['pillar'], '丁卯')
        self.assertAlmostEqual(x['da_yun_sequence'][1]['start_age'], round(span / 3 + 10, 2), places=2)

    def test_p1_female_yang_reverse(self):
        x = solve({'birth_time': '2024-02-04T16:30:00+08:00', 'gender': 'female', 'luck_policy': 'LUCK-P1'}, R, T)
        self.assertEqual(x['da_yun_start']['direction'], 'reverse')
        self.assertEqual(x['da_yun_start']['counted_to_jie']['name'], '立春')
        self.assertLess(x['da_yun_start']['start_age_years'], 0.01)
        self.assertEqual(x['da_yun_sequence'][0]['pillar'], '乙丑')

    def test_p1_requires_gender_and_birth_time(self):
        with self.assertRaises(RulebookError):
            solve({'birth_time': '2024-02-04T16:30:00+08:00', 'luck_policy': 'LUCK-P1'}, R, T)
        with self.assertRaises(RulebookError):
            solve({'pillars': {'year': '甲辰', 'month': '丙寅', 'day': '戊戌', 'hour': '庚申'}, 'gender': 'male', 'luck_policy': 'LUCK-P1'}, R)

    def test_conflicting_direction_refused(self):
        with self.assertRaises(RulebookError):
            solve({'birth_time': '2024-02-04T16:30:00+08:00', 'gender': 'male', 'luck_policy': 'LUCK-P1', 'luck_direction': 'reverse'}, R, T)

    def test_unknown_policy_refused(self):
        with self.assertRaises(RulebookError):
            solve({'birth_time': '2024-02-04T16:30:00+08:00', 'gender': 'male', 'luck_policy': 'X'}, R, T)


class RelationsAndRulesTest(unittest.TestCase):
    def chart(self, y, m, d, h):
        return solve({'pillars': {'year': y, 'month': m, 'day': d, 'hour': h}}, R)

    def test_stem_combination_and_dual(self):
        x = self.chart('甲子', '丙子', '己丑', '甲子')
        combos = x['computed']['stem_relations']['five_combinations']
        self.assertEqual([c['positions'] for c in combos], [['year', 'day'], ['day', 'hour']])
        self.assertTrue(all(c['element'] == '土' for c in combos))

    def test_meeting_harm_self_punishment(self):
        x = self.chart('甲寅', '丁卯', '甲辰', '戊辰')
        rel = x['computed']['branch_relations']
        self.assertEqual(rel['three_meetings'][0]['element'], '木')
        self.assertTrue(any(h['branches'] == ['卯', '辰'] for h in rel['six_harms']))
        self.assertTrue(any(p['relation'] == '自刑' and p['positions'] == ['day', 'hour'] for p in rel['punishments']))
        self.assertIn('G-112', {c['id'] for c in x['traditional_candidates']})

    def test_clash_and_combine_conflict(self):
        x = self.chart('乙亥', '戊寅', '甲子', '甲申')
        ids = {c['id'] for c in x['traditional_candidates']}
        self.assertTrue({'G-111', 'G-112', 'G-113'} <= ids)

    def test_unmatched_rule_explains_failed_conditions(self):
        x = run_birth('2024-02-04T16:30:00+08:00')
        g101 = next(t for t in x['trace'] if t['id'] == 'G-101')
        self.assertFalse(g101['matched'])
        failed = [c for c in g101['conditions'] if not c['satisfied']]
        self.assertEqual(failed[0]['fact'], 'month_primary_ten_god')
        self.assertEqual(failed[0]['actual'], '七杀')

    def test_markdown_report_sections(self):
        md = render_markdown(solve({'birth_time': '2024-02-04T16:30:00+08:00', 'gender': 'male', 'luck_policy': 'LUCK-P1'}, R, T))
        for h in 'ABCDEFGH':
            self.assertIn(f'## {h}.', md)
        self.assertIn('G-105', md)
        self.assertIn('暂不判定', md)
        md2 = render_markdown(solve({'pillars': {'year': '甲辰', 'month': '丙寅', 'day': '戊戌', 'hour': '庚申'}}, R))
        self.assertIn('未独立校验出生时刻', md2)


class ClassicalTablesTest(unittest.TestCase):
    CT = R['classical_tables']

    def test_changsheng_death_matches_sanming_quotes(self):
        for stem, quote in self.CT['changsheng']['death_quotes'].items():
            death = next(b for b in R['branches'] if changsheng_stage(stem, b, R) == '死')
            self.assertIn(f'死于{death}', quote, stem)

    def test_changsheng_examples(self):
        self.assertEqual(changsheng_stage('甲', '亥', R), '长生')
        self.assertEqual(changsheng_stage('甲', '卯', R), '帝旺')
        self.assertEqual(changsheng_stage('乙', '午', R), '长生')
        self.assertEqual(changsheng_stage('乙', '寅', R), '帝旺')
        self.assertEqual(changsheng_stage('庚', '酉', R), '帝旺')
        self.assertEqual(changsheng_stage('戊', '巳', R), '临官')
        for st in R['stems']:
            self.assertEqual(len({changsheng_stage(st, b, R) for b in R['branches']}), 12)

    def test_renyuan_each_month_30_days_and_lookup(self):
        for b, segs in self.CT['renyuan_siling']['table'].items():
            self.assertEqual(sum(x['days'] for x in segs), 30, b)
            for x in segs:
                self.assertIn(x['stem'], R['stems'])
        self.assertEqual(renyuan_siling('寅', 0.1, R)['stem'], '戊')
        self.assertEqual(renyuan_siling('寅', 5.0, R)['stem'], '丙')
        self.assertEqual(renyuan_siling('寅', 12, R)['stem'], '甲')
        last = renyuan_siling('巳', 30.9, R)
        self.assertEqual((last['stem'], last['capped']), ('丙', True))

    def test_renyuan_literal_in_source(self):
        src = (D / self.CT['renyuan_siling']['source']['snapshot']).read_text(encoding='utf-8').replace('\n', '')
        for b, segs in self.CT['renyuan_siling']['table'].items():
            for x in segs:
                self.assertIn(x['literal'], src)

    def test_wangxiang_spring_matches_quote(self):
        x = solve({'pillars': {'year': '甲辰', 'month': '丙寅', 'day': '戊戌', 'hour': '庚申'}}, R)
        self.assertEqual(x['computed']['classical']['wangxiang']['by_element'], {'木': '旺', '火': '相', '土': '死', '金': '囚', '水': '休'})

    def test_wangxiang_policies_differ_on_ji_months(self):
        x = solve({'pillars': {'year': '甲辰', 'month': '戊辰', 'day': '甲子', 'hour': '甲子'}}, R)
        self.assertEqual(x['computed']['classical']['wangxiang']['alternatives'], {'WX-SMTH': '旺', 'WX-SIJI': '囚'})
        y = solve({'pillars': {'year': '甲辰', 'month': '戊辰', 'day': '甲子', 'hour': '甲子'}, 'wangxiang_policy': 'WX-SIJI'}, R)
        self.assertEqual(y['computed']['classical']['wangxiang']['season_element'], '土')

    def test_tiaohou_complete_and_traceable(self):
        src = (D / self.CT['tiaohou']['source']['snapshot']).read_text(encoding='utf-8').split('\n')
        table = self.CT['tiaohou']['table']
        self.assertEqual(sorted(table), sorted(R['stems']))
        for stem, months in table.items():
            self.assertEqual(sorted(months), sorted(R['branches']))
            for b, cell in months.items():
                self.assertTrue(cell['primary'], (stem, b))
                line = src[cell['source_line'] - 1]
                self.assertIn(cell['quote'][:20], line.replace("\'\'\'", ''))
                for s_ in cell['primary']:
                    self.assertIn(s_, line, (stem, b, s_))

    def test_case_2005(self):
        x = solve({'birth_time': '2005-06-05T15:00:00+08:00'}, R, TF)
        cl = x['computed']['classical']
        self.assertEqual(cl['renyuan_siling']['stem'], '丙')
        self.assertEqual(cl['tiaohou']['primary'], ['壬'])
        self.assertEqual(cl['tiaohou']['presence']['壬']['visible'], [])
        self.assertEqual(cl['changsheng']['day_master_on']['month'], '长生')
        self.assertEqual(cl['wangxiang']['day_master_state'], '死')


class HypothesisLayerTest(unittest.TestCase):
    def test_hypothesis_isolated_from_rules(self):
        refs = set()
        from bazi_engine import collect_fact_refs
        for rule in R['rules']:
            refs |= collect_fact_refs(rule['when'])
        self.assertFalse(any('strength' in f or 'ratio' in f for f in refs))
        x = run_birth('2024-02-04T16:30:00+08:00')
        h = x['hypotheses']['STRENGTH-H1']
        self.assertEqual(h['layer'], 'hypothesis')
        self.assertEqual(len(h['sensitivity']), 9)
        self.assertEqual(h['stable'], len({g['label'] for g in h['sensitivity']}) == 1)

    def test_report_marks_hypothesis(self):
        md = render_markdown(run_birth('2024-02-04T16:30:00+08:00'))
        self.assertIn('## D2.', md)
        self.assertIn('## G2. 假设层', md)
        self.assertIn('无古籍依据', md)


def _ref_geju(dm, stems, branches):
    """取格参考实现：与 bazi_engine.select_geju 分开独立编写，只依赖原始表，用于交叉校验。"""
    S, B = '甲乙丙丁戊己庚辛壬癸', '子丑寅卯辰巳午未申酉戌亥'
    EL = dict(zip(S, '木木火火土土金金水水'))
    LU = dict(zip(S, '寅卯巳午巳午申酉亥子'))
    REN = {'甲': '卯', '丙': '午', '戊': '午', '庚': '酉', '壬': '子'}
    HID = {'子': '癸', '丑': '己癸辛', '寅': '甲丙戊', '卯': '乙', '辰': '戊乙癸', '巳': '丙庚戊', '午': '丁己',
           '未': '己丁乙', '申': '庚壬戊', '酉': '辛', '戌': '戊辛丁', '亥': '壬甲'}
    def god(x):
        gen = '木火土金水'
        d = (gen.index(EL[x]) - gen.index(EL[dm])) % 5
        same = S.index(x) % 2 == S.index(dm) % 2
        return [['比肩', '劫财'], ['食神', '伤官'], ['偏财', '正财'], ['七杀', '正官'], ['偏印', '正印']][d][0 if same else 1]
    mb = branches[1]
    vis = [stems[0], stems[1], stems[3]]
    hid = HID[mb]
    out = []
    if LU[dm] == mb:
        path = ['G-201']
    elif REN.get(dm) == mb:
        path = ['G-202']
    elif god(hid[0]) in ('比肩', '劫财'):
        path = ['G-203']
    else:
        path = []
    if path:
        out.append(path[0])
        inner = [h for h in hid[1:] if god(h) not in ('比肩', '劫财') and h in vis] if path == ['G-203'] else []
        if inner:
            out += [god(h) for h in inner]
        else:
            seen = []
            for v in vis:
                if god(v) not in ('比肩', '劫财') and v not in seen:
                    seen.append(v)
            out += [god(v) for v in seen] or ['unresolved']
    elif hid[0] in vis:
        path = ['G-204']
        out += [god(hid[0])] + [god(h) for h in hid[1:] if god(h) not in ('比肩', '劫财') and h in vis]
    else:
        ex = [h for h in hid[1:] if god(h) not in ('比肩', '劫财') and h in vis]
        path = ['G-205'] if ex else ['G-206']
        out += [god(h) for h in ex] + [god(hid[0])]
    groups = [('申子辰', '水'), ('亥卯未', '木'), ('寅午戌', '火'), ('巳酉丑', '金'),
              ('寅卯辰', '木'), ('巳午未', '火'), ('申酉戌', '金'), ('亥子丑', '水')]
    for g, el in groups:
        if mb in g and all(x in branches for x in g) and el != EL[hid[0]]:
            path.append('G-207')
            out.append(el)
    return path, out


def _engine_geju_projection(x):
    g = x['computed']['geju']
    out = []
    for c in g['candidates']:
        if c['rule'] in ('G-201', 'G-202', 'G-203') and c['role'] == '月令':
            out.append(c['rule'])
        elif c['status'] == 'unresolved':
            out.append('unresolved')
        elif c['rule'] == 'G-207':
            out.append(c['ge'].split('（')[1][2])  # 局五行
        else:
            out.append(c['ten_god'])
    return g['path'], out


class GejuSelectionTest(unittest.TestCase):
    def ge(self, y, m, d, h):
        x = solve({'pillars': {'year': y, 'month': m, 'day': d, 'hour': h}}, R)
        g = x['computed']['geju']
        return g['path'], [(c.get('ge'), c['status']) for c in g['candidates']]

    def test_golden_cases(self):
        # 建禄：甲日寅月；戊日巳月（戊寄禄于巳，即使巳本气为丙）
        self.assertEqual(self.ge('甲子', '丙寅', '甲子', '甲子')[0], ['G-201'])
        self.assertEqual(self.ge('甲子', '己巳', '戊子', '壬子')[0], ['G-201'])
        # 阳刃：甲日卯月、戊日午月；阴干无刃：乙日寅月 → 月劫
        self.assertEqual(self.ge('甲子', '丁卯', '甲子', '甲子')[0], ['G-202'])
        self.assertEqual(self.ge('甲子', '庚午', '戊子', '壬子')[0], ['G-202'])
        self.assertEqual(self.ge('甲子', '丙寅', '乙丑', '丙子')[0], ['G-203'])
        # 本气透：甲日酉月辛透 → 正官格
        self.assertEqual(self.ge('甲子', '癸酉', '甲子', '辛未'), (['G-204'], [('正官格', 'primary')]))
        # 本气透 + 兼透：癸日寅月，甲（伤官）、丙（正财）皆透
        self.assertEqual(self.ge('甲子', '丙寅', '癸丑', '甲寅')[1], [('伤官格', 'primary'), ('正财格', 'parallel')])
        # 本气不透、余气透：壬日辰月，乙透、戊不透 → 伤官格，七杀保留
        self.assertEqual(self.ge('乙丑', '庚辰', '壬子', '庚子'), (['G-205'], [('伤官格', 'primary'), ('七杀格', 'retained')]))
        # 全不透：本命例 庚日巳月 → 七杀格
        self.assertEqual(self.ge('乙酉', '辛巳', '庚申', '甲申'), (['G-206'], [('七杀格', 'primary_unexposed')]))
        # 会局：甲日亥月见卯未 → 追加木局（比劫）待审
        p, c = self.ge('乙卯', '丁亥', '甲子', '辛未')
        self.assertIn('G-207', p)
        self.assertEqual(c[-1], ('比劫（三合木局）', 'needs_review'))

    def test_matches_independent_reference_all_combinations(self):
        # 日干 10 × 月柱 60 × 年干 10 × 时干 10 = 60000 组；年/日/时支取与干同奇偶的固定支
        S, B = R['stems'], R['branches']
        fixed = {0: '子', 1: '丑'}
        n = 0
        for dm in S:
            for mi in range(60):
                m = index_pair(mi, R)
                for ys in S:
                    for hs in S:
                        y = ys + fixed[S.index(ys) % 2]
                        d = dm + ('午' if S.index(dm) % 2 == 0 else '未')
                        h = hs + ('戌' if S.index(hs) % 2 == 0 else '亥')
                        x = solve({'pillars': {'year': y, 'month': m, 'day': d, 'hour': h}}, R)
                        got = _engine_geju_projection(x)
                        exp = _ref_geju(dm, [ys, m[0], dm, hs], [y[1], m[1], d[1], h[1]])
                        self.assertEqual(got, exp, (y, m, d, h))
                        n += 1
        self.assertEqual(n, 60000)

    def test_random_branches_including_combinations(self):
        rnd = random.Random(7)
        S, B = R['stems'], R['branches']
        for _ in range(20000):
            pil = [index_pair(rnd.randrange(60), R) for _ in range(4)]
            x = solve({'pillars': dict(zip(POSITIONS, pil))}, R)
            exp = _ref_geju(pil[2][0], [p[0] for p in pil], [p[1] for p in pil])
            self.assertEqual(_engine_geju_projection(x), exp, pil)

    def test_si_hidden_order_matches_renyuan(self):
        # 巳：人元司事「戊七日、庚五日、丙十八日」→ 余气戊、中气庚、本气丙
        self.assertEqual(R['hidden_stems_main_first']['巳'], ['丙', '庚', '戊'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
