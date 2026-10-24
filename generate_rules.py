import json
from pathlib import Path
import classic_tables
O=Path(__file__).resolve().parent
S=list('甲乙丙丁戊己庚辛壬癸')
B=list('子丑寅卯辰巳午未申酉戌亥')
E=['木','木','火','火','土','土','金','金','水','水']
hidden={'子':['癸'],'丑':['己','癸','辛'],'寅':['甲','丙','戊'],'卯':['乙'],'辰':['戊','乙','癸'],'巳':['丙','庚','戊'],'午':['丁','己'],'未':['己','丁','乙'],'申':['庚','壬','戊'],'酉':['辛'],'戌':['戊','辛','丁'],'亥':['壬','甲']}
month_terms=[('立春','寅',315),('惊蛰','卯',345),('清明','辰',15),('立夏','巳',45),('芒种','午',75),('小暑','未',105),('立秋','申',135),('白露','酉',165),('寒露','戌',195),('立冬','亥',225),('大雪','子',255),('小寒','丑',285)]
rule_s='https://www.donglishuzhai.net/chapter/'
example=[
('G-101','月令正官见财印（初筛）',{'all':[{'fact':'month_primary_ten_god','op':'eq','value':'正官'},{'fact':'visible_ten_gods','op':'contains_any','values':['正财','偏财','正印','偏印']}]},'support','《子平真诠》〈论用神成败救应〉提到官逢财印等情况；须进一步核查位置、刑冲、破害和救应，不代表已经成格。','3722.html'),
('G-102','月令正官见伤官（初筛）',{'all':[{'fact':'month_primary_ten_god','op':'eq','value':'正官'},{'fact':'visible_ten_gods','op':'contains','value':'伤官'}]},'risk','仅表示《子平真诠》官格见伤的潜在条件；不可跳过制化、救应。','3722.html'),
('G-103','月令食神见财（初筛）',{'all':[{'fact':'month_primary_ten_god','op':'eq','value':'食神'},{'fact':'visible_ten_gods','op':'contains_any','values':['正财','偏财']}]},'support','经典中的「食神生财」结构线索，不等于财运判断。','3722.html'),
('G-104','月令伤官见财（初筛）',{'all':[{'fact':'month_primary_ten_god','op':'eq','value':'伤官'},{'fact':'visible_ten_gods','op':'contains_any','values':['正财','偏财']}]},'support','经典中的「伤官生财」结构线索，身强弱及其他条件未判。','3722.html'),
('G-105','月令七杀见食神（初筛）',{'all':[{'fact':'month_primary_ten_god','op':'eq','value':'七杀'},{'fact':'visible_ten_gods','op':'contains','value':'食神'}]},'support','经典中的「七杀逢制」或「食神制杀」线索；制成与否未判。','3722.html'),
('G-106','月令伤官见印（初筛）',{'all':[{'fact':'month_primary_ten_god','op':'eq','value':'伤官'},{'fact':'visible_ten_gods','op':'contains_any','values':['正印','偏印']}]},'support','经典中的「伤官佩印」线索；是否有效须另判旺衰、位置、通根。','3722.html'),
('G-107','月令财星见官（初筛）',{'all':[{'fact':'month_primary_ten_god','op':'in','values':['正财','偏财']},{'fact':'visible_ten_gods','op':'contains','value':'正官'}]},'support','经典中的「财生官」候选结构，不等于富贵预测。','3722.html'),
('G-108','月令比劫秉令，另行取用',{'fact':'month_primary_ten_god','op':'in','values':['比肩','劫财']},'needs_review','依《子平真诠》关于建禄月劫的论述，应查看其余干支财官煞食等，不能把比劫主气硬判为财官等常格。','3721.html'),
('G-109','月令多藏干透出：并列候选',{'fact':'month_hidden_exposed_count','op':'gte','value':2},'conflict','多种月令藏干透出可能出现格局变化或兼格；V1不得任选其一作为结论。','3723.html'),
('G-110','月令本气未透：保留本气候选',{'fact':'month_primary_exposed','op':'eq','value':False},'needs_review','月令本气未透并不自动排除其作用，仍要比较透出藏干及局部组合。','3723.html'),
('G-111','月支参与六冲：需复核',{'fact':'has_month_branch_clash','op':'eq','value':True},'risk','标注月支受到冲动的结构事实，不直接认定破格；会合解冲仍须研究。','3720.html'),
('G-112','月支参与合会：需复核',{'fact':'has_month_branch_combination','op':'eq','value':True},'needs_review','月支与他支构成六合、三合或三会；《子平真诠》〈论刑冲会合解法〉讨论合可解冲、合可改变月令作用，V1 不判定合化与否。','3720.html'),
('G-113','月支冲合互见：并列待审',{'all':[{'fact':'has_month_branch_clash','op':'eq','value':True},{'fact':'has_month_branch_combination','op':'eq','value':True}]},'conflict','月支同时被冲与被合，涉及「合以解冲」「冲以解合」的先后、远近判断，V1 不选择任一结论。','3720.html'),
]
rules={
 'schema_version':'1.3.0',
 'system':'子平八字_AI_可审计规则集',
 'scope':'公历换算后之四柱、干支、十神、藏干、关系识别及格局初筛。不输出已经证明的个人命运预测。',
 'default_policy':{'year_boundary':'lichun_instant','month_boundary':'12_jie_instant','day_boundary':'00:00','hour_boundaries':'two_hour_zi_23:00','clock':'civil_local_standard','solar_time':'off','unsupported':'return_unresolved'},
 'indexing':'all_indices_zero_based',
 'stems':S,'branches':B,
 'stem_element':dict(zip(S,E)),
 'stem_yinyang':{x:('阳' if i%2==0 else '阴') for i,x in enumerate(S)},
 'producing_cycle':['木','火','土','金','水'],
 'controlling_cycle':['木','土','水','火','金'],
 'hidden_stems_main_first':hidden,
 'month_jie':[{'name':n,'branch':b,'solar_longitude_degrees':d,'month_index_from_yin':i} for i,(n,b,d) in enumerate(month_terms)],
 'five_tiger_yin_month_start':{'甲':'丙','己':'丙','乙':'戊','庚':'戊','丙':'庚','辛':'庚','丁':'壬','壬':'壬','戊':'甲','癸':'甲'},
 'five_rat_zi_hour_start':{'甲':'甲','己':'甲','乙':'丙','庚':'丙','丙':'戊','辛':'戊','丁':'庚','壬':'庚','戊':'壬','癸':'壬'},
 'day_anchor':{'date':'2000-01-01','sexagenary':'戊午','index':54,'calendar':'proleptic_gregorian','policy':'local_date_after_day_boundary'},
 'six_clashes':[['子','午'],['丑','未'],['寅','申'],['卯','酉'],['辰','戌'],['巳','亥']],
 'six_harmonies':[['子','丑'],['寅','亥'],['卯','戌'],['辰','酉'],['巳','申'],['午','未']],
 'three_harmonies':{'水':['申','子','辰'],'木':['亥','卯','未'],'火':['寅','午','戌'],'金':['巳','酉','丑']},
 'three_meetings':{'木':['寅','卯','辰'],'火':['巳','午','未'],'金':['申','酉','戌'],'水':['亥','子','丑']},
 'stem_five_combinations':[['甲','己','土'],['乙','庚','金'],['丙','辛','水'],['丁','壬','木'],['戊','癸','火']],
 'six_harms':[['子','未'],['丑','午'],['寅','巳'],['卯','辰'],['申','亥'],['酉','戌']],
 'punishments':{'无恩之刑':['寅','巳','申'],'恃势之刑':['丑','戌','未'],'无礼之刑':['子','卯'],'自刑':['辰','午','酉','亥']},
 'luck_policies':{
  'LUCK-P1':{'name':'阳男阴女顺行、阴男阳女逆行；出生至相邻「节」的时长按 3 日折 1 年',
             'direction':{'male':{'阳':'forward','阴':'reverse'},'female':{'阳':'reverse','阴':'forward'}},
             'direction_basis':'年干阴阳（以立春换年后的年柱为准）',
             'boundary':'顺行数至下一个节，逆行数至上一个节；中气不计',
             'conversion':{'days_per_year':3,'note':'1 日=4 个月，1 时辰(2小时)=10 日；按精确时长线性折算'},
             'source':'通行《渊海子平》《三命通会》起运法之一；各书折算口径不一，故作为可选政策版本化，不作默认'}
 },
 'ten_god_definition':[
  {'relation':'same','same_polarity':'比肩','different_polarity':'劫财'},
  {'relation':'self_produces_other','same_polarity':'食神','different_polarity':'伤官'},
  {'relation':'self_controls_other','same_polarity':'偏财','different_polarity':'正财'},
  {'relation':'other_controls_self','same_polarity':'七杀','different_polarity':'正官'},
  {'relation':'other_produces_self','same_polarity':'偏印','different_polarity':'正印'},
 ],
 'rules':[
  {'id':rid,'name':name,'layer':'traditional_screening','when':cond,'then':{'type':'candidate_evidence','tag':tag,'text':note,'final_judgement':False},'source':{'book':'子平真诠','section':'论用神成败救应' if rid in [f'G-{i}' for i in range(101,108)] else ('论用神变化' if rid in ('G-109','G-110') else ('论用神' if rid=='G-108' else '论刑冲会合解法')),'url':rule_s+part},'uncertainty':'初筛条件，未覆盖古籍全部前提，不得升级为成败或吉凶结论'}
  for rid,name,cond,tag,note,part in example
 ],
 'classical_tables':classic_tables.build(),
 'geju_selection':{
  'id':'G-200',
  'layer':'traditional_screening',
  'name':'月令取格（按《子平真诠》通行次序编码）',
  'order':[
   {'id':'G-201','when':'月支为日干之禄（L-305）','result':'建禄格；不以月令本身为用，另取天干透出的财、官、杀、食、伤为候选'},
   {'id':'G-202','when':'阳干且月支为日干之羊刃（L-305）','result':'阳刃格；同样另取透干财官杀食伤为候选'},
   {'id':'G-203','when':'月令本气对日主为比肩或劫财（且非 G-201/202）','result':'月劫（比劫秉令）；先取月支中非比劫且透出的藏干，否则另取透干财官杀食伤'},
   {'id':'G-204','when':'月令本气透出（年/月/时干）','result':'以本气十神为格；若其他藏干亦透，列为兼透并列候选'},
   {'id':'G-205','when':'本气不透，而中气/余气（非比劫）有透出','result':'以透出者十神为格；多于一个时并列，不择一'},
   {'id':'G-206','when':'月支藏干全不透','result':'仍以本气十神为格，标「未透」'},
   {'id':'G-207','when':'月支参与完整的三合或三会，且局之五行异于本气五行','result':'追加「会局」候选（局五行对日主之十神），needs_review'}
  ],
  'ten_god_to_ge':{'正官':'正官格','七杀':'七杀格','正财':'正财格','偏财':'偏财格','正印':'正印格','偏印':'偏印格','食神':'食神格','伤官':'伤官格'},
  'source':{'book':'子平真诠','section':'论用神；论用神变化；论建禄月劫；论阳刃','url':rule_s+'3721.html',
            'verification':'本版编码时原文站点无法访问，取格次序依通行版本整理，待以原文快照逐句核对；禄、刃两表已对《三命通会》卷三原文校验'},
  'limits':['只决定「取哪个格」的候选，不判断成格、破格、清浊与救应','「透干会支，取其清者」中的「清」未定义：多候选时一律并列']
 },
 'hypotheses':{
  'STRENGTH-H1':{
   'layer':'hypothesis',
   'status':'编者自定权重，无古籍依据；仅供敏感性观察，不得作为格局、喜忌或任何规则的输入',
   'method':'帮身=比肩、劫财、正印、偏印；耗身=其余六神。统计年/月/时三明干及四支藏干；日主本身不计。ratio=帮身/(帮身+耗身)。',
   'weights':{'visible_stem':1.0,'hidden_by_order':[1.0,0.5,0.3],'month_branch_multiplier':2.0},
   'labels':{'偏强':'ratio>0.55','偏弱':'ratio<0.45','中间':'其余（不作结论）'},
   'sensitivity_grid':{'month_branch_multiplier':[1.0,2.0,3.0],'hidden_by_order':[[1.0,0.5,0.3],[1.0,0.3,0.1],[1.0,1.0,1.0]]},
   'stability_rule':'只有全部 9 组权重给出同一标签时才标 stable=true；否则为 unstable，说明结论依赖于任意权重'
  }
 },
 'non_implemented':['完整旺衰强弱判定','合化成立条件','地支刑害破之消解优先级','成败救应的完整充要条件','《穷通宝鉴》各月条件分支（如「支成火局」「一派庚金」）','旺衰的有文献依据的量化标准（STRENGTH-H1 仅为假设）','神煞取舍','除 LUCK-P1 以外的起运流派（如按日数取整、虚岁口径）；未声明 luck_policy 时不推起运','大运流年事件预测','可校验的现实预测模型'],
 'output_constraints':[
  '十神和藏干必须按表与算法输出，不得凭常识补写。',
  '一个月令同时有多个藏干透出时必须显示全部候选，不能不解释就择一。',
  '刑冲合会害只标为结构事件，合不自动视为化，合不自动解冲。',
  '不得将未经过科学验证的传统格局判断写成事实性人生结论。',
  '若缺少准确节气时刻，程序不能输出自称精确的年柱或月柱。',
  '每个候选判断须保留rule_id、事实依据、原典出处与未覆盖前提。'
 ],
 'sources':[
  {'id':'HKOTERM','name':'香港天文台：二十四节气','url':'https://www.hko.gov.hk/tc/gts/time/24solarterms.htm'},
  {'id':'HKOCALENDAR','name':'香港天文台：今夕是何年','url':'https://www.hko.gov.hk/tc/education/astronomy-and-time/time-service/00506-what-year-is-it-today.html'},
  {'id':'SEXAGENARY','name':'YT Liu: Sexagenary Cycle (六十干支)','url':'https://ytliu0.github.io/ChineseCalendar/sexagenary.html'},
  {'id':'ZP-YONG','name':'子平真诠：论用神','url':'https://www.donglishuzhai.net/chapter/3721.html'},
  {'id':'ZP-CHANGE','name':'子平真诠：论用神变化','url':'https://caipu.donglishuzhai.net/chapter/3723.html'},
  {'id':'ZP-SUCCESS','name':'子平真诠：论用神成败救应','url':'https://www.donglishuzhai.net/chapter/3722.html'},
  {'id':'ZP-CLASH','name':'子平真诠：论刑冲会合解法','url':'https://www.donglishuzhai.net/chapter/3720.html'},
  {'id':'SMTH-2','name':'维基文库：三命通会/卷二（rev 2292392）','url':classic_tables.SMTH_URL},
  {'id':'QTBJ','name':'维基文库：穷通宝鉴（rev 2294674）','url':classic_tables.QTBJ_URL},
  {'id':'BEIJING2024','name':'北京市文物局：2024年二十四节气时刻','url':'https://wwj.beijing.gov.cn/bjww/wwjzzcslm/1729028/1729037/1729027/436356026/index.html'}
 ]
}
(O/'rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
terms=[('2023-02-04T10:42:21+08:00','立春','参考：2023年北京时刻表'),('2023-12-07T17:32:57+08:00','大雪','参考：历法交节时刻表'),
('2024-01-06T04:49:22+08:00','小寒','参考：历法交节时刻表')]
times_2024=[('立春','2024-02-04T16:26:53+08:00'),('惊蛰','2024-03-05T10:22:31+08:00'),('清明','2024-04-04T15:02:03+08:00'),('立夏','2024-05-05T08:09:51+08:00'),('芒种','2024-06-05T12:09:40+08:00'),('小暑','2024-07-06T22:19:49+08:00'),('立秋','2024-08-07T08:09:01+08:00'),('白露','2024-09-07T11:11:06+08:00'),('寒露','2024-10-08T02:59:43+08:00'),('立冬','2024-11-07T06:19:49+08:00'),('大雪','2024-12-06T23:16:47+08:00'),('小寒','2025-01-05T10:32:31+08:00')]
terms.extend((t,n,'北京市文物局公布之2024交节时刻表') for n,t in times_2024)
fixture={'schema_version':'1.0.0','display_timezone':'UTC+08:00','coverage':'2024公历年，含前后必要节气；不适用于其他年份','notice':'2023-02立春与2023-12大雪记录来自注明的参考资料；各机构天文算法可能存在秒级差异。临界出生应核验同一权威数据源。','terms':[{'name':name,'at':t,'source':src} for t,name,src in terms]}
(O/'terms_2024_example.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('created rules.json, terms fixture')
