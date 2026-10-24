# -*- coding: utf-8 -*-
"""十神组合格局（P 系列）的规则定义，由 generate_rules.py 写入 rules.json。

每条规则只描述结构：哪两类十神同时出现、哪些十神出现会加重或化解。
所有引句都在生成时逐字核对 sources/ 下的原文快照；找不到原文依据的救应条件放进
relief_unsourced，只作提示，不参与任何判断。
"""
from pathlib import Path

O = Path(__file__).resolve().parent
SRC = {
    'YH': ('渊海子平', O / 'sources' / '渊海子平_wikisource_rev2593607.txt',
           'https://zh.wikisource.org/w/index.php?title=%E6%B7%B5%E6%B5%B7%E5%AD%90%E5%B9%B3&oldid=2593607'),
    'SM5': ('三命通会·卷五', O / 'sources' / '三命通会_卷五_wikisource_rev2706483.txt',
            'https://zh.wikisource.org/w/index.php?title=%E4%B8%89%E5%91%BD%E9%80%9A%E6%9C%83/%E5%8D%B7%E4%BA%94&oldid=2706483'),
    'SM6': ('三命通会·卷六', O / 'sources' / '三命通会_卷六_wikisource_rev845352.txt',
            'https://zh.wikisource.org/w/index.php?title=%E4%B8%89%E5%91%BD%E9%80%9A%E6%9C%83/%E5%8D%B7%E5%85%AD&oldid=845352'),
}
CAI = ['正财', '偏财']
YIN = ['正印', '偏印']
SHISHANG = ['食神', '伤官']
BIJIE = ['比肩', '劫财']

# kind: pair = A 类与 B 类十神同现；combined_sha = 七杀干被他干五合；yangren_sha = 阳干日主见羊刃支且有七杀
# tag: risk / support / mixed（mixed 表示原文同时有吉凶两说）
PATTERNS = [
    {'id': 'P-101', 'name': '枭神夺食', 'aliases': ['倒食', '吞啗煞'], 'kind': 'pair', 'a': ['偏印'], 'b': ['食神'], 'tag': 'risk',
     'quotes': [('YH', '夫倒食者，冲财神之谓也；一名『吞啗煞』。用财神大忌见之，用食神亦忌见之。倒食者，如甲见壬之类。'),
                ('SM5', '食怕枭，逢枭则夺')],
     'aggravate': [], 'relief': [],
     'relief_unsourced': [{'ten_gods': CAI, 'note': '「以财制枭」为后世通行说法，已归档原文未见'}],
     'unresolved': ['食神或财是否为用神（原文：用财、用食皆忌）', '偏印与食神的力量轻重']},
    {'id': 'P-102', 'name': '印绶伤食', 'aliases': [], 'kind': 'pair', 'a': ['正印'], 'b': ['食神'], 'tag': 'risk',
     'quotes': [('YH', '却喜身旺，不喜印綬，亦恐伤其食神也')],
     'aggravate': [], 'relief': [], 'relief_unsourced': [],
     'unresolved': ['正印克食神弱于偏印，原文未分轻重', '日主强弱（原文：却喜身旺）']},
    {'id': 'P-103', 'name': '伤官见官', 'aliases': [], 'kind': 'pair', 'a': ['伤官'], 'b': ['正官'], 'tag': 'risk',
     'quotes': [('YH', '伤官见官，为祸百端'), ('YH', '伤官务要伤尽；伤之不尽，官来乘旺，其祸不可胜言')],
     'aggravate': [],
     'relief': [{'ten_gods': YIN, 'effect': '印制伤官', 'quote': ('SM6', '伤官若带印，官煞不为刑')},
                {'ten_gods': CAI, 'effect': '伤官生财、财生官，转化', 'quote': ('YH', '如遇伤官者，须见其财为妙；是财能生官也')}],
     'relief_unsourced': [],
     'unresolved': ['伤官是否「伤尽」', '官星轻重与位置']},
    {'id': 'P-104', 'name': '官杀混杂', 'aliases': ['官煞混杂'], 'kind': 'pair', 'a': ['正官'], 'b': ['七杀'], 'tag': 'mixed',
     'quotes': [('YH', '官星要纯，不要杂'), ('SM5', '人命官煞俱有谓之混杂，只取财印为用'), ('SM5', '观三命不可以混杂为贱论')],
     'aggravate': [],
     'relief': [{'ten_gods': ['__combined__'], 'effect': '官或杀被合去（去官留杀/去杀留官）', 'quote': ('YH', '官煞兩停，合煞為貴')},
                {'ten_gods': SHISHANG, 'effect': '食伤制伏', 'quote': ('SM5', '身旺有制亦好')},
                {'ten_gods': YIN, 'effect': '印化官杀', 'quote': ('SM5', '无制，成印局化煞亦可')}],
     'relief_unsourced': [],
     'unresolved': ['日主强弱（原文：身弱官煞混，多夭贫）', '去官还是留杀']},
    {'id': 'P-105', 'name': '食神制杀', 'aliases': ['食神制煞'], 'kind': 'pair', 'a': ['食神'], 'b': ['七杀'], 'tag': 'support',
     'quotes': [('YH', '喜身旺合杀、喜制伏、喜阳刃'), ('YH', '七杀却宜制伏，亦不要制之太过')],
     'aggravate': [{'ten_gods': ['偏印'], 'effect': '枭神夺食，制杀之力被破', 'quote': ('SM6', '食神制煞，逢枭不贫则夭')}],
     'relief': [], 'relief_unsourced': [],
     'unresolved': ['制杀是否太过', '日主强弱']},
    {'id': 'P-106', 'name': '杀印相生', 'aliases': ['煞印相生'], 'kind': 'pair', 'a': ['七杀'], 'b': YIN, 'tag': 'support',
     'quotes': [('SM5', '煞不离印，印不离煞，煞印相生，功名显达')],
     'aggravate': [{'ten_gods': CAI, 'effect': '财坏印', 'quote': ('SM5', '印怕财，贪财则坏')}],
     'relief': [], 'relief_unsourced': [],
     'unresolved': ['杀与印的轻重']},
    {'id': 'P-107', 'name': '官印相生', 'aliases': ['官印两全'], 'kind': 'pair', 'a': ['正官'], 'b': YIN, 'tag': 'support',
     'quotes': [('YH', '有官有印，无破作廊庙之材'), ('YH', '如带印綬，须带官星，谓之官印两全')],
     'aggravate': [{'ten_gods': CAI, 'effect': '财星破印', 'quote': ('YH', '有官有印，畏财兴，助财为祸')}],
     'relief': [], 'relief_unsourced': [],
     'unresolved': ['官印是否「无破」']},
    {'id': 'P-108', 'name': '财官相生', 'aliases': ['财生官'], 'kind': 'pair', 'a': CAI, 'b': ['正官'], 'tag': 'support',
     'quotes': [('YH', '财生官，官生印，印生身，富贵双全')],
     'aggravate': [{'ten_gods': ['伤官'], 'effect': '伤官伤官星', 'quote': ('SM5', '官怕伤，被伤则祸')},
                   {'ten_gods': ['劫财'], 'effect': '劫财分财', 'quote': ('SM5', '财怕劫，被劫则分')}],
     'relief': [], 'relief_unsourced': [],
     'unresolved': ['日主能否任财官']},
    {'id': 'P-109', 'name': '财滋七杀', 'aliases': ['财生杀', '财党杀'], 'kind': 'pair', 'a': CAI, 'b': ['七杀'], 'tag': 'risk',
     'quotes': [('YH', '但忌财旺，财能生杀故也'), ('YH', '干党财，财党杀，杀攻身，凶穷两逼')],
     'aggravate': [],
     'relief': [{'ten_gods': ['食神'], 'effect': '食神制杀', 'quote': ('YH', '喜身旺合杀、喜制伏、喜阳刃')}],
     'relief_unsourced': [],
     'unresolved': ['日主强弱（身强杀浅时财滋弱杀另论）']},
    {'id': 'P-110', 'name': '比劫夺财', 'aliases': ['劫财分财', '群劫争财'], 'kind': 'pair', 'a': ['劫财'], 'b': CAI, 'tag': 'risk',
     'quotes': [('SM5', '财怕劫，被劫则分'), ('YH', '乙以戊己为财，甲见夺己坏戊')],
     'aggravate': [], 'relief': [],
     'relief_unsourced': [{'ten_gods': ['正官', '七杀'], 'note': '「官杀制劫护财」为后世通行说法，已归档原文未见'},
                          {'ten_gods': SHISHANG, 'note': '「食伤通关」为后世通行说法，已归档原文未见'}],
     'unresolved': ['财星轻重与日主强弱']},
    {'id': 'P-111', 'name': '贪财坏印', 'aliases': ['财坏印', '财星破印'], 'kind': 'pair', 'a': CAI, 'b': YIN, 'tag': 'risk',
     'quotes': [('SM5', '印怕财，贪财则坏'), ('YH', '印綬畏财')],
     'aggravate': [],
     'relief': [{'ten_gods': BIJIE, 'effect': '比劫护印、制财', 'quote': ('SM6', '却要见比劫助身')},
                {'ten_gods': ['正官', '七杀'], 'effect': '财生官、官生印，通关', 'quote': ('SM6', '印绶有官有财，则财生官，官生印，印生身')}],
     'relief_unsourced': [],
     'unresolved': ['印是否有根（原文：印绶有根，逢财则发）']},
    {'id': 'P-112', 'name': '伤官佩印', 'aliases': ['伤官带印'], 'kind': 'pair', 'a': ['伤官'], 'b': YIN, 'tag': 'support',
     'quotes': [('SM6', '伤官若带印，官煞不为刑')],
     'aggravate': [{'ten_gods': CAI, 'effect': '财破印', 'quote': ('SM6', '伤官若带印，不宜逢财')}],
     'relief': [], 'relief_unsourced': [],
     'unresolved': ['伤官与印的轻重、日主强弱']},
    {'id': 'P-113', 'name': '伤官生财', 'aliases': ['伤官用财'], 'kind': 'pair', 'a': ['伤官'], 'b': CAI, 'tag': 'support',
     'quotes': [('YH', '伤官用财乃为福'), ('YH', '用伤官格局，见财方可用')],
     'aggravate': [{'ten_gods': YIN, 'effect': '印制伤官、伤官难以生财', 'quote': ('YH', '伤官用财，不宜印乡')}],
     'relief': [], 'relief_unsourced': [],
     'unresolved': ['日主能否任财']},
    {'id': 'P-114', 'name': '食神生财', 'aliases': [], 'kind': 'pair', 'a': ['食神'], 'b': CAI, 'tag': 'support',
     'quotes': [('YH', '恒不喜见官星，忌倒食，恐伤其食神；喜财神相生')],
     'aggravate': [{'ten_gods': ['偏印'], 'effect': '枭神夺食', 'quote': ('YH', '用财神大忌见之，用食神亦忌见之')}],
     'relief': [], 'relief_unsourced': [],
     'unresolved': ['日主强弱（原文：却喜身旺）']},
    {'id': 'P-115', 'name': '合杀', 'aliases': ['贪合忘杀'], 'kind': 'combined_sha', 'a': ['七杀'], 'b': [], 'tag': 'support',
     'quotes': [('YH', '如甲以庚为七杀，喜丙丁制之；乙合之，谓之『贪合忘杀』'), ('YH', '惟其身旺合杀为妙')],
     'aggravate': [], 'relief': [], 'relief_unsourced': [],
     'unresolved': ['合而化否（五合化气需另判）', '日主强弱（原文：身旺合杀为妙）']},
    {'id': 'P-116', 'name': '杀刃相济', 'aliases': ['刃杀俱全', '羊刃驾杀'], 'kind': 'yangren_sha', 'a': ['七杀'], 'b': [], 'tag': 'mixed',
     'quotes': [('YH', '杀无刃不显，刃无杀不威'), ('YH', '若命中元有杀刃，岁运又逢之，其祸非常')],
     'aggravate': [], 'relief': [], 'relief_unsourced': [],
     'unresolved': ['杀刃是否两停（力量相当）', '日主强弱']},
]


def build():
    texts = {k: p.read_text(encoding='utf-8').replace('\n', '') for k, (_, p, _) in SRC.items()}

    def q(ref):
        key, text = ref
        assert text in texts[key], (key, text)
        book, path, url = SRC[key]
        return {'book': book, 'text': text, 'url': url, 'snapshot': 'sources/' + path.name}

    out = []
    for p in PATTERNS:
        rec = {k: v for k, v in p.items() if k not in ('quotes', 'aggravate', 'relief')}
        rec['quotes'] = [q(x) for x in p['quotes']]
        rec['aggravate'] = [{**a, 'quote': q(a['quote'])} for a in p['aggravate']]
        rec['relief'] = [{**a, 'quote': q(a['quote'])} for a in p['relief']]
        out.append(rec)
    return {
        'id': 'P-100',
        'layer': 'traditional_screening',
        'presence': {'formed': '两方都透于年/月/时干', 'partial': '一方透干、一方只藏于地支', 'latent': '两方都只藏于地支'},
        'notes': ['只判断结构是否出现，不判断成败吉凶；每条规则的 unresolved 列出原文成立所需、而引擎无法判定的条件。',
                  '加重/化解只看十神是否透干或藏支；力量轻重不计。',
                  'relief_unsourced 为未在已归档原文中找到出处的通行说法，只作提示。'],
        'patterns': out,
    }
