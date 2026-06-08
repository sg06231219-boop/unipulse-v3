# -*- coding: utf-8 -*-
"""UniPulse v3 就业数据 - 中国高校专业就业信息"""
# 数据来源: 各大学就业质量报告 + 麦可思研究院 + 公开统计数据
# 薪资单位: 人民币/月（毕业生平均起薪），就业率单位: 百分比

UNI_PROGRAMS = [
    # ── 清华大学 ──
    {"uni_id":1,"program_name":"计算机类","salary_avg":32000,"salary_entry":22000,"employment_rate":99.1,"pressure":82,"prospects":95,"description":"清华计算机国内顶尖，毕业生主要去向BAT/字节/海外FAANG，深造率超60%"},
    {"uni_id":1,"program_name":"电子信息类","salary_avg":28000,"salary_entry":20000,"employment_rate":98.8,"pressure":75,"prospects":92,"description":"电子系历史悠久，芯片/通信/AI硬件方向就业强势"},
    {"uni_id":1,"program_name":"自动化类","salary_avg":26000,"salary_entry":18000,"employment_rate":98.5,"pressure":70,"prospects":90,"description":"自动化系培养复合型人才，机器人/控制/智能系统方向"},
    {"uni_id":1,"program_name":"建筑类","salary_avg":22000,"salary_entry":15000,"employment_rate":97.2,"pressure":78,"prospects":82,"description":"建筑老八校之首，但房地产行业下行影响就业前景"},
    {"uni_id":1,"program_name":"经济学类","salary_avg":28000,"salary_entry":18000,"employment_rate":98.2,"pressure":65,"prospects":88,"description":"经管学院五道口金融，毕业生主要去投行/券商/PE/VC"},
    {"uni_id":1,"program_name":"数学类","salary_avg":25000,"salary_entry":17000,"employment_rate":98.0,"pressure":72,"prospects":90,"description":"数学系深造率极高，转CS/量化/金融科技优势明显"},

    # ── 北京大学 ──
    {"uni_id":2,"program_name":"计算机类","salary_avg":30000,"salary_entry":21000,"employment_rate":99.0,"pressure":80,"prospects":94,"description":"北大信科+AI研究院，学术与工业并重，深造率55%+"},
    {"uni_id":2,"program_name":"法学类","salary_avg":20000,"salary_entry":12000,"employment_rate":95.5,"pressure":68,"prospects":85,"description":"北大法学院中国第一，律所/法院/公务员三线并进"},
    {"uni_id":2,"program_name":"经济学类","salary_avg":26000,"salary_entry":17000,"employment_rate":97.8,"pressure":60,"prospects":88,"description":"经济学院+光华管理学院，金融/咨询/互联网全覆盖"},
    {"uni_id":2,"program_name":"临床医学类","salary_avg":15000,"salary_entry":8000,"employment_rate":99.5,"pressure":85,"prospects":88,"description":"北大医学部，8年制+3年规培，长远薪资天花板极高"},
    {"uni_id":2,"program_name":"数学类","salary_avg":24000,"salary_entry":16000,"employment_rate":98.2,"pressure":75,"prospects":92,"description":"北大数院全国第一，丘成桐数学中心，深造率60%+"},
    {"uni_id":2,"program_name":"新闻传播类","salary_avg":18000,"salary_entry":12000,"employment_rate":95.2,"pressure":55,"prospects":78,"description":"新闻与传播学院，传统媒体+新媒体+互联网运营三栖"},

    # ── 浙江大学 ──
    {"uni_id":3,"program_name":"计算机类","salary_avg":28000,"salary_entry":19000,"employment_rate":98.8,"pressure":78,"prospects":93,"description":"浙大CS全国前三，阿里/网易大本营，杭州互联网生态完善"},
    {"uni_id":3,"program_name":"电子信息类","salary_avg":24000,"salary_entry":17000,"employment_rate":98.2,"pressure":72,"prospects":88,"description":"信电学院+微纳电子，海康/大华等本地企业需求大"},
    {"uni_id":3,"program_name":"土木类","salary_avg":16000,"salary_entry":10000,"employment_rate":95.5,"pressure":80,"prospects":65,"description":"土木工程传统强势，但受房地产影响就业质量下滑"},
    {"uni_id":3,"program_name":"临床医学类","salary_avg":14000,"salary_entry":7500,"employment_rate":99.2,"pressure":82,"prospects":85,"description":"浙大医学院+附属医院，浙江医疗体系核心"},
    {"uni_id":3,"program_name":"机械类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.8,"pressure":70,"prospects":78,"description":"机械学院+控制学院，智能制造/机器人方向前景好"},
    {"uni_id":3,"program_name":"金融学类","salary_avg":22000,"salary_entry":14000,"employment_rate":97.5,"pressure":62,"prospects":85,"description":"经济学院+管理学院，杭州金融科技/互联网金融发达"},

    # ── 上海交通大学 ──
    {"uni_id":4,"program_name":"计算机类","salary_avg":29000,"salary_entry":20000,"employment_rate":99.0,"pressure":80,"prospects":94,"description":"上交CS+AI，微软/商汤/拼多多重镇，ACM竞赛全球前三"},
    {"uni_id":4,"program_name":"电子信息类","salary_avg":25000,"salary_entry":18000,"employment_rate":98.5,"pressure":73,"prospects":90,"description":"电院实力雄厚，芯片/通信/信号处理方向强"},
    {"uni_id":4,"program_name":"机械类","salary_avg":20000,"salary_entry":14000,"employment_rate":97.2,"pressure":68,"prospects":80,"description":"机械与动力工程学院，汽车/船舶/航空航天方向"},
    {"uni_id":4,"program_name":"临床医学类","salary_avg":16000,"salary_entry":8500,"employment_rate":99.3,"pressure":84,"prospects":90,"description":"交大医学院（原二医大），瑞金/仁济/九院等顶级三甲"},
    {"uni_id":4,"program_name":"金融学类","salary_avg":25000,"salary_entry":16000,"employment_rate":98.0,"pressure":58,"prospects":88,"description":"高金+安泰，上海金融核心人才输出地"},

    # ── 复旦大学 ──
    {"uni_id":5,"program_name":"经济学类","salary_avg":25000,"salary_entry":16000,"employment_rate":98.2,"pressure":60,"prospects":90,"description":"复旦经院+管院，上海金融圈核心院校"},
    {"uni_id":5,"program_name":"临床医学类","salary_avg":15500,"salary_entry":8000,"employment_rate":99.4,"pressure":83,"prospects":89,"description":"复旦上医（原上医大），中山/华山医院顶级三甲"},
    {"uni_id":5,"program_name":"新闻传播类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.0,"pressure":52,"prospects":80,"description":"复旦新闻学院亚洲第一，媒体/公关/互联网全覆盖"},
    {"uni_id":5,"program_name":"数学类","salary_avg":22000,"salary_entry":15000,"employment_rate":98.0,"pressure":70,"prospects":88,"description":"复旦数学底蕴深厚，苏步青/谷超豪传承，金融量化方向强"},
    {"uni_id":5,"program_name":"金融学类","salary_avg":26000,"salary_entry":17000,"employment_rate":98.5,"pressure":55,"prospects":90,"description":"经济学院+管理学院+数学学院，量化/投行/咨询三线"},

    # ── 南京大学 ──
    {"uni_id":6,"program_name":"计算机类","salary_avg":25000,"salary_entry":17000,"employment_rate":98.5,"pressure":76,"prospects":90,"description":"南大CS+AI，周志华团队LAMDA实验室全球知名，南京软件谷"},
    {"uni_id":6,"program_name":"数学类","salary_avg":20000,"salary_entry":14000,"employment_rate":97.8,"pressure":68,"prospects":85,"description":"南大数学系小而精，基础数学+计算数学特色"},
    {"uni_id":6,"program_name":"物理学类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.5,"pressure":72,"prospects":82,"description":"南大物理全国前三，天文/凝聚态/声学特色鲜明"},
    {"uni_id":6,"program_name":"化学类","salary_avg":16000,"salary_entry":11000,"employment_rate":95.8,"pressure":70,"prospects":78,"description":"南大化学配位化学国家重点实验室，深造率50%+"},
    {"uni_id":6,"program_name":"经济学类","salary_avg":20000,"salary_entry":13000,"employment_rate":97.0,"pressure":58,"prospects":82,"description":"商学院+经济学院，南京/江苏金融体系核心院校"},

    # ── 中国科学技术大学 ──
    {"uni_id":7,"program_name":"计算机类","salary_avg":26000,"salary_entry":18000,"employment_rate":98.5,"pressure":78,"prospects":92,"description":"中科大CS+大数据学院，学术导向强，留学率极高"},
    {"uni_id":7,"program_name":"物理学类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.2,"pressure":75,"prospects":85,"description":"物理学院全国前三，量子信息/核物理/等离子体全球领先"},
    {"uni_id":7,"program_name":"数学类","salary_avg":20000,"salary_entry":14000,"employment_rate":97.5,"pressure":72,"prospects":88,"description":"华罗庚数学班传承，基础数学+计算数学特色"},
    {"uni_id":7,"program_name":"化学类","salary_avg":16000,"salary_entry":11000,"employment_rate":95.5,"pressure":68,"prospects":80,"description":"化学与材料科学学院，纳米/高分子/催化方向强"},
    {"uni_id":7,"program_name":"电子信息类","salary_avg":22000,"salary_entry":16000,"employment_rate":98.0,"pressure":70,"prospects":88,"description":"信息科学技术学院，信号处理/量子通信方向特色"},

    # ── 武汉大学 ──
    {"uni_id":8,"program_name":"法学类","salary_avg":18000,"salary_entry":11000,"employment_rate":95.8,"pressure":65,"prospects":82,"description":"武大法学院全国前三，国际法/环境法特色鲜明"},
    {"uni_id":8,"program_name":"计算机类","salary_avg":22000,"salary_entry":15000,"employment_rate":97.5,"pressure":74,"prospects":88,"description":"武大CS+遥感信息工程，测绘遥感全球第一"},
    {"uni_id":8,"program_name":"土木类","salary_avg":15000,"salary_entry":9500,"employment_rate":95.2,"pressure":78,"prospects":62,"description":"土木建筑工程学院，水利水电特色，但行业下行压力大"},
    {"uni_id":8,"program_name":"新闻传播类","salary_avg":16000,"salary_entry":10000,"employment_rate":95.0,"pressure":50,"prospects":75,"description":"武大新闻学院全国前五，华中地区媒体人才摇篮"},

    # ── 华中科技大学 ──
    {"uni_id":9,"program_name":"计算机类","salary_avg":23000,"salary_entry":16000,"employment_rate":98.2,"pressure":76,"prospects":90,"description":"华科CS+光电，华为'天才少年'最多的学校，光谷核心"},
    {"uni_id":9,"program_name":"机械类","salary_avg":18000,"salary_entry":12000,"employment_rate":97.0,"pressure":68,"prospects":78,"description":"机械学院全国前三，智能制造/机器人/3D打印方向"},
    {"uni_id":9,"program_name":"电子信息类","salary_avg":21000,"salary_entry":15000,"employment_rate":97.8,"pressure":72,"prospects":86,"description":"光电学院+电信学院，光通信/激光/半导体方向强"},
    {"uni_id":9,"program_name":"临床医学类","salary_avg":13000,"salary_entry":7000,"employment_rate":99.0,"pressure":82,"prospects":85,"description":"同济医学院（原同济医科大学），协和/同济医院顶级三甲"},

    # ── 西安交通大学 ──
    {"uni_id":10,"program_name":"自动化类","salary_avg":20000,"salary_entry":14000,"employment_rate":97.5,"pressure":68,"prospects":85,"description":"西交自动化全国前三，系统工程/控制理论特色鲜明"},
    {"uni_id":10,"program_name":"电气类","salary_avg":18000,"salary_entry":13000,"employment_rate":98.0,"pressure":60,"prospects":88,"description":"电气工程学院全国第一，国家电网/南方电网招聘首选"},
    {"uni_id":10,"program_name":"机械类","salary_avg":17000,"salary_entry":11000,"employment_rate":96.5,"pressure":65,"prospects":75,"description":"机械学院传统强势，先进制造/智能制造方向"},
    {"uni_id":10,"program_name":"经济学类","salary_avg":17000,"salary_entry":11000,"employment_rate":95.8,"pressure":55,"prospects":78,"description":"金禾中心+经济学院，西北地区金融核心院校"},
    {"uni_id":10,"program_name":"计算机类","salary_avg":21000,"salary_entry":14000,"employment_rate":97.2,"pressure":74,"prospects":86,"description":"CS+软件学院，华为/中兴招聘重镇，西北IT人才核心输出地"},

    # ── 北京航空航天大学 ──
    {"uni_id":11,"program_name":"计算机类","salary_avg":26000,"salary_entry":18000,"employment_rate":98.8,"pressure":78,"prospects":92,"description":"北航CS+软件，航空/航天/国防信息化领域优势大"},
    {"uni_id":11,"program_name":"自动化类","salary_avg":22000,"salary_entry":16000,"employment_rate":98.2,"pressure":72,"prospects":88,"description":"自动化学院+可靠性与系统工程学院，航天控制特色"},
    {"uni_id":11,"program_name":"电子信息类","salary_avg":23000,"salary_entry":16000,"employment_rate":98.0,"pressure":70,"prospects":88,"description":"电子信息工程学院，雷达/导航/通信方向国防特色"},
    {"uni_id":11,"program_name":"机械类","salary_avg":19000,"salary_entry":13000,"employment_rate":97.5,"pressure":68,"prospects":82,"description":"航空科学与工程学院，飞行器设计/制造全国第一"},

    # ── 中山大学 ──
    {"uni_id":12,"program_name":"临床医学类","salary_avg":14000,"salary_entry":7500,"employment_rate":99.2,"pressure":82,"prospects":86,"description":"中山医学院+附属医院，华南医疗体系核心，广州医疗资源丰富"},
    {"uni_id":12,"program_name":"计算机类","salary_avg":22000,"salary_entry":15000,"employment_rate":97.5,"pressure":74,"prospects":88,"description":"中大CS+AI，深圳校区发展迅速，腾讯/华为南方大本营"},
    {"uni_id":12,"program_name":"金融学类","salary_avg":20000,"salary_entry":13000,"employment_rate":97.0,"pressure":55,"prospects":82,"description":"岭南学院+管理学院，广州/深圳金融圈核心院校"},
    {"uni_id":12,"program_name":"法学类","salary_avg":16000,"salary_entry":10000,"employment_rate":95.2,"pressure":62,"prospects":78,"description":"中大法学院华南第一，广深律所/法院/公务员三线"},

    # ── 北京理工大学 ──
    {"uni_id":13,"program_name":"计算机类","salary_avg":24000,"salary_entry":17000,"employment_rate":98.5,"pressure":76,"prospects":90,"description":"北理工CS+软件，国防信息化+智能无人系统特色"},
    {"uni_id":13,"program_name":"自动化类","salary_avg":21000,"salary_entry":15000,"employment_rate":97.8,"pressure":70,"prospects":86,"description":"自动化学院，智能控制/导航制导特色鲜明"},
    {"uni_id":13,"program_name":"机械类","salary_avg":18000,"salary_entry":12000,"employment_rate":97.0,"pressure":66,"prospects":78,"description":"机械与车辆学院，车辆工程/兵器科学特色"},
    {"uni_id":13,"program_name":"电子信息类","salary_avg":22000,"salary_entry":16000,"employment_rate":98.0,"pressure":72,"prospects":86,"description":"信息与电子学院，雷达/信号处理/电子对抗国防特色"},

    # ── 哈尔滨工业大学 ──
    {"uni_id":14,"program_name":"计算机类","salary_avg":23000,"salary_entry":16000,"employment_rate":98.0,"pressure":76,"prospects":88,"description":"哈工大CS+软件，自然语言处理/机器人/AI特色，深圳校区薪资更高"},
    {"uni_id":14,"program_name":"机械类","salary_avg":17000,"salary_entry":11000,"employment_rate":96.5,"pressure":66,"prospects":76,"description":"机电工程学院，机器人/航天器机构/焊接技术特色"},
    {"uni_id":14,"program_name":"土木类","salary_avg":15000,"salary_entry":9500,"employment_rate":95.0,"pressure":75,"prospects":60,"description":"土木工程学院全国前三，但行业下行压力明显"},
    {"uni_id":14,"program_name":"自动化类","salary_avg":20000,"salary_entry":14000,"employment_rate":97.5,"pressure":68,"prospects":84,"description":"航天学院+控制学科，航天控制/惯性导航全国领先"},

    # ── 四川大学 ──
    {"uni_id":15,"program_name":"口腔医学类","salary_avg":18000,"salary_entry":10000,"employment_rate":99.5,"pressure":70,"prospects":90,"description":"华西口腔亚洲第一，口腔医生收入天花板极高"},
    {"uni_id":15,"program_name":"临床医学类","salary_avg":13500,"salary_entry":7000,"employment_rate":99.0,"pressure":82,"prospects":85,"description":"华西医学中心，华西医院亚洲最大单点医院"},
    {"uni_id":15,"program_name":"计算机类","salary_avg":19000,"salary_entry":13000,"employment_rate":96.5,"pressure":72,"prospects":82,"description":"CS+软件，成都IT生态完善，字节/蚂蚁/美团西部中心"},
    {"uni_id":15,"program_name":"数学类","salary_avg":16000,"salary_entry":11000,"employment_rate":95.8,"pressure":68,"prospects":80,"description":"数学学院+统计学，保险精算/数据分析特色"},

    # ── 东南大学 ──
    {"uni_id":16,"program_name":"建筑类","salary_avg":20000,"salary_entry":13000,"employment_rate":96.5,"pressure":75,"prospects":78,"description":"建筑学院全国前三，但房地产行业下行影响明显"},
    {"uni_id":16,"program_name":"电子信息类","salary_avg":22000,"salary_entry":16000,"employment_rate":98.0,"pressure":72,"prospects":88,"description":"信息科学与工程学院，移动通信/毫米波全国领先"},
    {"uni_id":16,"program_name":"土木类","salary_avg":16000,"salary_entry":10000,"employment_rate":95.8,"pressure":78,"prospects":62,"description":"土木工程学院全国前三，但行业前景不佳"},
    {"uni_id":16,"program_name":"计算机类","salary_avg":22000,"salary_entry":15000,"employment_rate":97.5,"pressure":74,"prospects":86,"description":"CS+软件，网络安全/人工智能方向特色"},
    {"uni_id":16,"program_name":"自动化类","salary_avg":20000,"salary_entry":14000,"employment_rate":97.2,"pressure":68,"prospects":84,"description":"自动化学院，复杂系统/机器人/智能控制特色"},

    # ── 中国人民大学 ──
    {"uni_id":17,"program_name":"金融学类","salary_avg":28000,"salary_entry":18000,"employment_rate":98.5,"pressure":55,"prospects":92,"description":"财金学院+汉青研究院，北京金融圈核心，顶级投行/央行"},
    {"uni_id":17,"program_name":"经济学类","salary_avg":25000,"salary_entry":16000,"employment_rate":98.0,"pressure":58,"prospects":90,"description":"经济学院+国发院，智库/政策研究/学术导向"},
    {"uni_id":17,"program_name":"法学类","salary_avg":22000,"salary_entry":13000,"employment_rate":96.5,"pressure":62,"prospects":88,"description":"人大法学院全国第一，红圈律所/最高法/法务核心"},
    {"uni_id":17,"program_name":"新闻传播类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.0,"pressure":52,"prospects":78,"description":"新闻学院全国第一，新华社/央视/互联网大厂内容岗"},
    {"uni_id":17,"program_name":"计算机类","salary_avg":24000,"salary_entry":16000,"employment_rate":97.5,"pressure":70,"prospects":85,"description":"信息学院+高瓴AI，数据科学/AI+社科交叉特色"},

    # ── 两电一邮 ──
    {"uni_id":47,"program_name":"电子信息类","salary_avg":22000,"salary_entry":15000,"employment_rate":97.5,"pressure":72,"prospects":90,"description":"西安电子科大电信，华为/中兴招聘首选之一"},
    {"uni_id":47,"program_name":"计算机类","salary_avg":23000,"salary_entry":16000,"employment_rate":97.8,"pressure":74,"prospects":88,"description":"CS+网络工程，网络安全/密码学全国领先"},
    {"uni_id":48,"program_name":"电子信息类","salary_avg":24000,"salary_entry":17000,"employment_rate":98.0,"pressure":73,"prospects":92,"description":"电子科大信电，电子科学与技术全国第一，西部硅谷核心"},
    {"uni_id":48,"program_name":"计算机类","salary_avg":25000,"salary_entry":17000,"employment_rate":98.2,"pressure":76,"prospects":90,"description":"CS+AI学院，成电AI+电子信息交叉特色鲜明"},
    {"uni_id":49,"program_name":"计算机类","salary_avg":26000,"salary_entry":18000,"employment_rate":98.5,"pressure":78,"prospects":92,"description":"北邮CS+网络，通信+互联网复合人才，运营商/互联网双栖"},
    {"uni_id":49,"program_name":"电子信息类","salary_avg":23000,"salary_entry":16000,"employment_rate":98.0,"pressure":72,"prospects":90,"description":"信息与通信工程学院，5G/6G/物联网方向全国领先"},

    # ── 211财经院校 ──
    {"uni_id":32,"program_name":"金融学类","salary_avg":25000,"salary_entry":16000,"employment_rate":98.0,"pressure":55,"prospects":90,"description":"上财金融学院，四大会计+券商+基金核心Target School"},
    {"uni_id":32,"program_name":"经济学类","salary_avg":22000,"salary_entry":14000,"employment_rate":97.5,"pressure":58,"prospects":88,"description":"经济学院+商学院，上海金融体系人才核心输出地"},
    {"uni_id":32,"program_name":"会计学","salary_avg":23000,"salary_entry":15000,"employment_rate":98.2,"pressure":52,"prospects":85,"description":"会计学院全国第一，四大/审计/财务总监摇篮"},
    {"uni_id":43,"program_name":"金融学类","salary_avg":24000,"salary_entry":16000,"employment_rate":98.0,"pressure":55,"prospects":90,"description":"对外经贸金融学院，外资银行+外贸企业+国际化特色"},
    {"uni_id":43,"program_name":"经济学类","salary_avg":22000,"salary_entry":14000,"employment_rate":97.5,"pressure":58,"prospects":88,"description":"国际经济贸易学院，国际贸易/国际金融特色鲜明"},
    {"uni_id":43,"program_name":"英语/外语类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.5,"pressure":48,"prospects":82,"description":"外语学院+国际贸易复合，外企/外贸公司/驻外岗位"},

    # ── 211师范院校 ──
    {"uni_id":19,"program_name":"教育学类","salary_avg":14000,"salary_entry":9000,"employment_rate":96.5,"pressure":55,"prospects":80,"description":"北师大教育学院全国第一，北京中小学教师核心来源"},
    {"uni_id":19,"program_name":"数学类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.0,"pressure":65,"prospects":82,"description":"数学科学学院，数学教育+基础数学双线发展"},
    {"uni_id":19,"program_name":"心理学类","salary_avg":16000,"salary_entry":10000,"employment_rate":95.8,"pressure":58,"prospects":82,"description":"心理学部全国第一，心理咨询/用户体验/教育评估"},
    {"uni_id":30,"program_name":"教育学类","salary_avg":13500,"salary_entry":8500,"employment_rate":96.0,"pressure":55,"prospects":78,"description":"华东师大教育学院全国前三，上海中小学教师核心来源"},
    {"uni_id":30,"program_name":"心理学类","salary_avg":15000,"salary_entry":9500,"employment_rate":95.5,"pressure":56,"prospects":80,"description":"心理与认知科学学院，应用心理/教育心理特色"},

    # ── 211政法 ──
    {"uni_id":44,"program_name":"法学类","salary_avg":20000,"salary_entry":12000,"employment_rate":95.5,"pressure":65,"prospects":85,"description":"中国政法大学法学院全国第一，红圈律所+法院+公务员"},
    {"uni_id":44,"program_name":"政治学类","salary_avg":15000,"salary_entry":9000,"employment_rate":94.0,"pressure":55,"prospects":75,"description":"政治与公共管理学院，公务员/事业单位/外交系统"},

    # ── 211外语 ──
    {"uni_id":41,"program_name":"英语/外语类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.8,"pressure":48,"prospects":82,"description":"北外101种语言，外交部/国际贸易/翻译/国际组织核心"},
    {"uni_id":46,"program_name":"英语/外语类","salary_avg":17000,"salary_entry":11000,"employment_rate":96.5,"pressure":48,"prospects":80,"description":"上外多语种+经贸复合，上海外企/外贸/国际组织核心"},

    # ── 重庆大学 ──
    {"uni_id":55,"program_name":"土木类","salary_avg":14000,"salary_entry":9000,"employment_rate":95.0,"pressure":78,"prospects":58,"description":"重大土木全国前五，但房地产行业下行影响就业"},
    {"uni_id":55,"program_name":"机械类","salary_avg":16000,"salary_entry":11000,"employment_rate":96.0,"pressure":65,"prospects":75,"description":"机械工程学院，汽车工程/先进制造特色"},
    {"uni_id":55,"program_name":"建筑类","salary_avg":17000,"salary_entry":11000,"employment_rate":95.5,"pressure":72,"prospects":68,"description":"建筑城规学院，建筑老八校之一，西南建筑行业核心"},

    # ── 更多211 ──
    {"uni_id":34,"program_name":"计算机类","salary_avg":20000,"salary_entry":14000,"employment_rate":97.5,"pressure":72,"prospects":86,"description":"北交大CS+软件，铁路信息化/交通大数据特色"},
    {"uni_id":34,"program_name":"土木类","salary_avg":15000,"salary_entry":9500,"employment_rate":95.5,"pressure":75,"prospects":65,"description":"土木建筑工程学院，铁路/桥梁/隧道工程特色"},
    {"uni_id":54,"program_name":"石油工程类","salary_avg":16000,"salary_entry":10000,"employment_rate":97.0,"pressure":72,"prospects":80,"description":"石油大学王牌，中石油/中石化/中海油招聘首选"},
    {"uni_id":58,"program_name":"土木类","salary_avg":14500,"salary_entry":9000,"employment_rate":95.2,"pressure":76,"prospects":62,"description":"河海水利全国第一，水利水电/港口航道特色"},
    {"uni_id":59,"program_name":"电子信息类","salary_avg":18000,"salary_entry":13000,"employment_rate":96.5,"pressure":70,"prospects":84,"description":"哈工程水声工程全国第一，船舶电子/海洋信息特色"},
    {"uni_id":60,"program_name":"机械类","salary_avg":16000,"salary_entry":11000,"employment_rate":96.0,"pressure":65,"prospects":75,"description":"武汉理工材料+船舶+汽车三驾马车，行业特色鲜明"},
    {"uni_id":71,"program_name":"计算机类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.5,"pressure":70,"prospects":82,"description":"合工大CS，智能制造+管理信息化交叉特色"},
    {"uni_id":80,"program_name":"药学类","salary_avg":18000,"salary_entry":12000,"employment_rate":96.8,"pressure":62,"prospects":88,"description":"中国药科大学药学全国第一，制药/研发/注册/营销四线"},
]
