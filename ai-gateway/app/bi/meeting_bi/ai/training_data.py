# 需要训练的表名列表，DDL 会从数据库自动获取
TABLES = [
    "meeting_registration",
    "meeting_customer_analysis",
    "meeting_schedule_stats",
    "meeting_transaction_details",
    "meeting_region_transaction_targets",
    "meeting_region_proposal_targets",
]

# ---------------------------------------------------------------------------
# 业务文档训练（Documentation Training）
# 向 Vanna 注入业务语义、字段含义、计算公式、数据清洗规则等领域知识
# ---------------------------------------------------------------------------
BUSINESS_DOCS = [
    # ── 表级说明 ──
    (
        "meeting_registration 表是报名签到表，存储客户的报名和签到信息，共约 1250 条记录。"
        "关键字段：sign_in_status 表示签到状态，取值为 '已签到' 或 '未签到'；"
        "customer_category 表示客户类别，取值为 '新顾客'、'老顾客'、'陪同'；"
        "attendee_role 表示参会角色，取值为 '终端顾客'、'市场人员'、'店铺陪同'、'百万VIP贵宾'、'千万VIP贵宾'、'千万家属'、'百万家属'；"
        "customer_level_name 表示客户金额等级名称，取值包括 '千万客户'、'千万家属'、'千万朋友'、'千万总裁'、"
        "'300万以上客户'、'300万以上家属'、'300万以上总裁'、'百万客户'、'百万家属'、'百万朋友'、'百万总裁'、"
        "'累计百万'、'百万累计'，也可能为 NULL（未分类）；"
        "market_service_attribution 表示市场服务归属，格式为 '大区名,分公司名'，例如 '蒋晓莹大区,XX分公司'；"
        "提取大区名称时使用 SUBSTRING_INDEX(market_service_attribution, ',', 1)；"
        "customer_unique_id 是客户唯一标识，用于去重和跨表关联；"
        "store_name 表示来源店铺，可用于判断客户来源类型；"
        "sign_in_date_1 是签到日期（date 类型），不是 sign_in_time。"
    ),

    (
        "meeting_customer_analysis 表是客户分析表，存储客户画像和目标客户分析数据，共约 3676 条记录。"
        "关键字段：region 表示大区，取值包括 '蒋晓莹大区'、'田晓静大区'、'王红丽大区'、'段延芳大区'、"
        "'陈秀敏大区'、'黄刚大区'、'李红霞大区'、'李英大区'、'樊明花大区'、'公司直管'、'商务BU'；"
        "customer_level 是金额等级，取值为 '千万客户'、'百万客户'、'普通客户' 或 NULL；"
        "min_deal 是成交低限，max_deal 是成交高限；"
        "consumption_target 是消耗目标；"
        "prep_maturity 是铺垫成熟度；"
        "new_or_old_customer 表示新老客户，取值包括 '老顾客'、'新顾客'、'陪同'、'取消'、'老'、'新客户'、'老客户'、'终端'；"
        "注意：该表的 customer_unique_id 当前全部为 NULL，无法直接用于跨表 JOIN。"
    ),

    (
        "meeting_transaction_details 表是成交明细表，存储客户成交记录，当前约 5 条记录。"
        "关键字段：deal_type 表示成交类型，取值为 '新成交' 或 '消耗'；"
        "new_deal_amount 是新成交金额（单位：元），查询已成交金额时通常不需要过滤 deal_type；"
        "received_amount 是收款金额（单位：元）；consumed_amount 是消耗金额（单位：元）；"
        "region 表示大区；deal_content 是成交内容，例如 '新成交：39.8万四维能量卡'；"
        "plan_type 是方案类型，例如 '100万及以内方案'；"
        "在页面展示时金额除以 10000 换算为万元。"
    ),

    (
        "meeting_schedule_stats 表是运营时段统计表，存储会议期间各时段的人流统计数据，共 88 条记录。"
        "关键字段：scene 表示场景，取值为 '住宿'、'参会/活动'、'在院环节'、'就餐环节'、'未参与环节人员'；"
        "time_period 表示时间段，取值包括 '住宿人数'、'当日新抵达人数'、'理应在场人数'、'离开人数'、"
        "'参加会议.活动-上午'、'参加会议，活动-晚上'、'听课-下午'、'参加率-上午'、'参加率-下午'、'参加率-晚上'、"
        "'体检人数'、'医院人数-医美'、'医院人数合计'、'预约交付'、'预约见诊'、'午餐'、'晚餐'、'未参与环节人员'；"
        "schedule_date 是日期，范围 2024-12-14 至 2024-12-20（共7天）；"
        "people_count 是人数。"
        "注意：查询人数数据时要排除含 '率' 和 '占比' 的 time_period 记录。"
    ),

    (
        "meeting_region_transaction_targets 表是区域成交目标配置表，共 11 条记录。"
        "关键字段：region 表示大区；performance_target 是业绩目标（单位：元）；"
        "min_deal 是成交低限；max_deal 是成交高限；"
        "attendance_target 是到场目标；consumption_target 是消耗目标。"
        "该表与 meeting_transaction_details 通过 region 字段关联。"
    ),

    (
        "meeting_region_proposal_targets 表是区域方案目标配置表，当前为空（0条数据），"
        "待灌入方案目标配置数据后才能使用。"
        "关键字段：region 表示大区；proposal_type 表示方案类型；target_count 是目标数量。"
    ),

    # ── 业务计算规则 ──
    (
        "核心 KPI 计算规则："
        "1. 报名客户 = meeting_registration 中 COUNT(DISTINCT customer_unique_id)，需过滤掉 real_identity 含 '市场' 和 '陪同' 的记录；"
        "2. 已抵达客户 = meeting_registration 中 sign_in_status='已签到' 的 COUNT(DISTINCT customer_unique_id)，同样过滤市场和陪同；"
        "3. 已成交金额 = meeting_transaction_details 中 SUM(new_deal_amount)，展示时除以 10000 换算为万；"
        "4. 新规划消耗（已消耗预算）= meeting_transaction_details 中 SUM(consumed_amount)，展示时除以 10000 换算为万；"
        "5. 已收款金额 = meeting_transaction_details 中 SUM(received_amount)，展示时除以 10000 换算为万；"
        "6. 总投资回报率(ROI) = 固定预算600万 / 已成交金额(万) × 0.4 × 100%。"
    ),

    (
        "区域目标完成率计算规则："
        "达成率 = SUM(new_deal_amount) / NULLIF(performance_target, 0) × 100%，"
        "需要 meeting_transaction_details 和 meeting_region_transaction_targets 两张表通过 region 字段 LEFT JOIN；"
        "查成交时通常过滤 deal_type = '新成交'。"
        "完成度 = SUM(new_deal_amount) / NULLIF(max_deal, 0) × 100%，用的是成交高限作为分母。"
    ),

    (
        "客户来源类型判断规则：基于 meeting_registration.store_name 字段做模糊匹配："
        "CASE WHEN store_name LIKE '%盟主%' THEN '盟主' "
        "WHEN store_name LIKE '%商务%' THEN '商务' ELSE '店铺' END。"
    ),

    (
        "优质目标客户判断规则：meeting_customer_analysis 表中 min_deal >= 100 的记录被视为目标客户。"
        "目标客户抵达需要与 meeting_registration 通过 customer_unique_id 关联，并检查 sign_in_status = '已签到'。"
        "但注意 meeting_customer_analysis.customer_unique_id 当前全部为 NULL，跨表 JOIN 可能返回 0 条结果。"
    ),

    (
        "签到率计算公式：签到率 = 已签到人数 / 总报名人数 × 100%。"
        "SQL：ROUND(SUM(CASE WHEN sign_in_status = '已签到' THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS checkin_rate "
        "FROM meeting_registration。"
    ),

    (
        "运营 KPI 指标计算规则："
        "签到人数 = meeting_registration 中 sign_in_date_1 IS NOT NULL 的去重客户数；"
        "接机人数 = meeting_registration 中 flight_info IS NOT NULL AND sign_in_date_1 IS NOT NULL 的去重客户数；"
        "离开人数 = meeting_schedule_stats 中 time_period = '离开人数' 的 people_count 之和；"
        "到院人数 = meeting_schedule_stats 中 time_period = '医院人数合计' 的 people_count 之和。"
    ),

    # ── 数据清洗与注意事项 ──
    (
        "数据清洗注意事项："
        "1. meeting_customer_analysis.region 字段可能包含无效值如 '细胞。和王艳红夫妻'，需过滤；"
        "2. new_or_old_customer 字段需统一：'老顾客'/'老客户'/'老' → 老客户；'新顾客'/'新客户' → 新客户；'陪同'/'终端' → 其他；'取消' → 过滤；"
        "3. customer_level_name 包含 '%千万%' 的归为千万级，包含 '%百万%' 或 '%300万%' 的归为百万级，其余为普通级；"
        "4. 数据库为 MySQL 5.7，不支持窗口函数如 ROW_NUMBER()，需用 @rownum 变量方式替代；"
        "5. 金额字段默认单位为元，页面展示时需除以 10000 换算为万元。"
    ),

    (
        "大区名称标准取值包括：蒋晓莹大区、田晓静大区、王红丽大区、段延芳大区、"
        "陈秀敏大区、黄刚大区、李红霞大区、李英大区、樊明花大区、公司直管、商务BU、营销铁军。"
        "meeting_registration 表中的大区需通过 SUBSTRING_INDEX(market_service_attribution, ',', 1) 提取。"
        "meeting_customer_analysis 和 meeting_transaction_details 表中直接使用 region 字段。"
    ),

    (
        "时间段与场景映射规则（用于 meeting_schedule_stats 的趋势分析）："
        "时间段映射：time_period LIKE '%上午%' → '上午'；LIKE '%下午%' → '下午'；"
        "LIKE '%午餐%' → '下午'；LIKE '%晚餐%' 或 '%晚上%' → '晚上'；其余 → '全天'。"
        "场景映射：LIKE '%听课%' → '听课'；LIKE '%抵达%' → '抵达'；LIKE '%离开%' → '离开'；"
        "LIKE '%午餐%' 或 '%晚餐%' → '用餐'；LIKE '%医院人数合计%' → '到院'；其余 → '其他'。"
    ),
]

# ---------------------------------------------------------------------------
# QA 训练对 - 覆盖所有业务场景的问答样例
# 包含同义词变体，确保 Vanna 向量检索能匹配用户的多种问法
# ---------------------------------------------------------------------------
QA_PAIRS = [
    # ═══════════════════════════════════════════════════════
    # 一、核心 KPI 指标
    # ═══════════════════════════════════════════════════════
    {
        "question": "报名了多少客户？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS total FROM meeting_registration WHERE real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%'",
    },
    {
        "question": "总共有多少人报名？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS total FROM meeting_registration WHERE real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%'",
    },
    {
        "question": "报名人数是多少？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS total FROM meeting_registration WHERE real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%'",
    },
    {
        "question": "已签到多少客户？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS total FROM meeting_registration WHERE sign_in_status = '已签到' AND real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%'",
    },
    {
        "question": "已抵达客户有多少？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS total FROM meeting_registration WHERE sign_in_status = '已签到' AND real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%'",
    },
    {
        "question": "到了多少人？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS total FROM meeting_registration WHERE sign_in_status = '已签到' AND real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%'",
    },
    {
        "question": "总成交金额是多少？",
        "sql": "SELECT ROUND(SUM(new_deal_amount) / 10000, 2) AS total_deal_wan FROM meeting_transaction_details",
    },
    {
        "question": "已成交金额是多少？",
        "sql": "SELECT ROUND(SUM(new_deal_amount) / 10000, 2) AS total_deal_wan FROM meeting_transaction_details",
    },
    {
        "question": "卖了多少钱？",
        "sql": "SELECT ROUND(SUM(new_deal_amount) / 10000, 2) AS total_deal_wan FROM meeting_transaction_details",
    },
    {
        "question": "收款金额是多少？",
        "sql": "SELECT ROUND(SUM(received_amount) / 10000, 2) AS total_received_wan FROM meeting_transaction_details",
    },
    {
        "question": "已收款多少？",
        "sql": "SELECT ROUND(SUM(received_amount) / 10000, 2) AS total_received_wan FROM meeting_transaction_details",
    },
    {
        "question": "消耗预算是多少？",
        "sql": "SELECT ROUND(SUM(consumed_amount) / 10000, 2) AS total_consumed_wan FROM meeting_transaction_details",
    },
    {
        "question": "新规划消耗是多少？",
        "sql": "SELECT ROUND(SUM(consumed_amount) / 10000, 2) AS total_consumed_wan FROM meeting_transaction_details",
    },
    {
        "question": "投资回报率是多少？",
        "sql": "SELECT ROUND(6000000 / NULLIF(SUM(new_deal_amount), 0) * 0.4 * 100, 2) AS roi_percent FROM meeting_transaction_details",
    },
    {
        "question": "ROI是多少？",
        "sql": "SELECT ROUND(6000000 / NULLIF(SUM(new_deal_amount), 0) * 0.4 * 100, 2) AS roi_percent FROM meeting_transaction_details",
    },

    # ═══════════════════════════════════════════════════════
    # 二、签到率相关
    # ═══════════════════════════════════════════════════════
    {
        "question": "签到率是多少？",
        "sql": "SELECT ROUND(SUM(CASE WHEN sign_in_status = '已签到' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS checkin_rate FROM meeting_registration",
    },
    {
        "question": "到场率是多少？",
        "sql": "SELECT ROUND(SUM(CASE WHEN sign_in_status = '已签到' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS checkin_rate FROM meeting_registration",
    },
    {
        "question": "今天签到了多少人？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS total FROM meeting_registration WHERE sign_in_status = '已签到' AND sign_in_date_1 = CURDATE()",
    },

    # ═══════════════════════════════════════════════════════
    # 三、按大区维度统计
    # ═══════════════════════════════════════════════════════
    {
        "question": "各大区报名人数是多少？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE market_service_attribution IS NOT NULL GROUP BY region ORDER BY cnt DESC",
    },
    {
        "question": "每个大区有多少人报名？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE market_service_attribution IS NOT NULL GROUP BY region ORDER BY cnt DESC",
    },
    {
        "question": "各大区签到人数是多少？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE market_service_attribution IS NOT NULL AND sign_in_status = '已签到' GROUP BY region ORDER BY cnt DESC",
    },
    {
        "question": "每个大区到了多少人？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE market_service_attribution IS NOT NULL AND sign_in_status = '已签到' GROUP BY region ORDER BY cnt DESC",
    },
    {
        "question": "各大区签到率是多少？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, COUNT(DISTINCT customer_unique_id) AS total, COUNT(DISTINCT CASE WHEN sign_in_status = '已签到' THEN customer_unique_id END) AS arrived, ROUND(COUNT(DISTINCT CASE WHEN sign_in_status = '已签到' THEN customer_unique_id END) * 100.0 / COUNT(DISTINCT customer_unique_id), 2) AS checkin_rate FROM meeting_registration WHERE market_service_attribution IS NOT NULL GROUP BY region ORDER BY checkin_rate DESC",
    },

    # ═══════════════════════════════════════════════════════
    # 四、客户画像分析
    # ═══════════════════════════════════════════════════════
    {
        "question": "新老客户比例是多少？",
        "sql": "SELECT customer_category, COUNT(DISTINCT customer_unique_id) AS cnt, ROUND(COUNT(DISTINCT customer_unique_id) * 100.0 / (SELECT COUNT(DISTINCT customer_unique_id) FROM meeting_registration), 2) AS percentage FROM meeting_registration GROUP BY customer_category ORDER BY cnt DESC",
    },
    {
        "question": "新客户有多少？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE customer_category = '新顾客'",
    },
    {
        "question": "老客户有多少？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE customer_category = '老顾客'",
    },
    {
        "question": "客户金额等级分布是什么？",
        "sql": "SELECT COALESCE(customer_level_name, '未分类') AS level_name, COUNT(*) AS customer_count, ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM meeting_registration), 2) AS percentage FROM meeting_registration GROUP BY customer_level_name ORDER BY customer_count DESC",
    },
    {
        "question": "千万客户有多少？",
        "sql": "SELECT COUNT(*) AS cnt FROM meeting_registration WHERE customer_level_name LIKE '%千万%'",
    },
    {
        "question": "百万客户有多少？",
        "sql": "SELECT COUNT(*) AS cnt FROM meeting_registration WHERE customer_level_name LIKE '%百万%' OR customer_level_name LIKE '%300万%'",
    },
    {
        "question": "身份类型分布是什么？",
        "sql": "SELECT attendee_role, COUNT(DISTINCT customer_unique_id) AS person_count, ROUND(COUNT(DISTINCT customer_unique_id) * 100.0 / (SELECT COUNT(DISTINCT customer_unique_id) FROM meeting_registration), 2) AS percentage FROM meeting_registration GROUP BY attendee_role ORDER BY person_count DESC",
    },
    {
        "question": "参会角色分布是什么？",
        "sql": "SELECT attendee_role, COUNT(DISTINCT customer_unique_id) AS person_count, ROUND(COUNT(DISTINCT customer_unique_id) * 100.0 / (SELECT COUNT(DISTINCT customer_unique_id) FROM meeting_registration), 2) AS percentage FROM meeting_registration GROUP BY attendee_role ORDER BY person_count DESC",
    },
    {
        "question": "每个大区有多少千万客户？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, COUNT(*) AS cnt FROM meeting_registration WHERE customer_level_name LIKE '%千万%' AND market_service_attribution IS NOT NULL GROUP BY region ORDER BY cnt DESC",
    },
    {
        "question": "每个大区千万客户数量？",
        "sql": "SELECT region, COUNT(*) AS cnt FROM meeting_customer_analysis WHERE customer_level = '千万客户' AND region IS NOT NULL GROUP BY region ORDER BY cnt DESC",
    },

    # ═══════════════════════════════════════════════════════
    # 五、客户来源分析
    # ═══════════════════════════════════════════════════════
    {
        "question": "各大区客户来源分布？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, CASE WHEN store_name LIKE '%盟主%' THEN '盟主' WHEN store_name LIKE '%商务%' THEN '商务' ELSE '店铺' END AS source_type, COUNT(DISTINCT customer_unique_id) AS customer_count FROM meeting_registration WHERE market_service_attribution IS NOT NULL AND store_name IS NOT NULL GROUP BY region, source_type ORDER BY region, customer_count DESC",
    },
    {
        "question": "盟主渠道贡献了多少客户？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE store_name LIKE '%盟主%'",
    },
    {
        "question": "商务渠道贡献了多少客户？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE store_name LIKE '%商务%'",
    },
    {
        "question": "店铺渠道贡献了多少客户？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE store_name IS NOT NULL AND store_name NOT LIKE '%盟主%' AND store_name NOT LIKE '%商务%'",
    },

    # ═══════════════════════════════════════════════════════
    # 六、区域目标达成
    # ═══════════════════════════════════════════════════════
    {
        "question": "各区域目标完成情况如何？",
        "sql": "SELECT t.region, COALESCE(SUM(d.new_deal_amount), 0) AS deal_amount, t.performance_target, ROUND(COALESCE(SUM(d.new_deal_amount), 0) / NULLIF(t.performance_target, 0) * 100, 2) AS achievement_rate FROM meeting_region_transaction_targets t LEFT JOIN meeting_transaction_details d ON t.region = d.region AND d.deal_type = '新成交' GROUP BY t.region, t.performance_target ORDER BY t.region",
    },
    {
        "question": "各大区达成率是多少？",
        "sql": "SELECT t.region, COALESCE(SUM(d.new_deal_amount), 0) AS deal_amount, t.performance_target, ROUND(COALESCE(SUM(d.new_deal_amount), 0) / NULLIF(t.performance_target, 0) * 100, 2) AS achievement_rate FROM meeting_region_transaction_targets t LEFT JOIN meeting_transaction_details d ON t.region = d.region AND d.deal_type = '新成交' GROUP BY t.region, t.performance_target ORDER BY achievement_rate DESC",
    },
    {
        "question": "哪个大区成交金额最高？",
        "sql": "SELECT region, SUM(new_deal_amount) AS total_amount FROM meeting_transaction_details WHERE deal_type = '新成交' GROUP BY region ORDER BY total_amount DESC LIMIT 1",
    },
    {
        "question": "哪个大区业绩最好？",
        "sql": "SELECT region, SUM(new_deal_amount) AS total_amount FROM meeting_transaction_details WHERE deal_type = '新成交' GROUP BY region ORDER BY total_amount DESC LIMIT 1",
    },
    {
        "question": "各区域完成度排行？",
        "sql": "SELECT t.region, COALESCE(d.deal_amount, 0) AS deal_amount, t.max_deal AS high_limit, ROUND(COALESCE(d.deal_amount, 0) / NULLIF(t.max_deal, 0) * 100, 2) AS completion_rate FROM meeting_region_transaction_targets t LEFT JOIN (SELECT region, SUM(new_deal_amount) AS deal_amount FROM meeting_transaction_details WHERE deal_type = '新成交' GROUP BY region) d ON t.region = d.region ORDER BY completion_rate DESC",
    },
    {
        "question": "各区域目标与达成金额对比？",
        "sql": "SELECT t.region, t.min_deal AS low_limit, t.max_deal AS high_limit, COALESCE(SUM(d.new_deal_amount), 0) AS deal_amount FROM meeting_region_transaction_targets t LEFT JOIN meeting_transaction_details d ON t.region = d.region AND d.deal_type = '新成交' GROUP BY t.region, t.min_deal, t.max_deal ORDER BY t.region",
    },
    {
        "question": "平均完成率是多少？",
        "sql": "SELECT ROUND(AVG(completion_rate), 2) AS avg_completion_rate FROM (SELECT t.region, ROUND(COALESCE(d.deal_amount, 0) / NULLIF(t.max_deal, 0) * 100, 2) AS completion_rate FROM meeting_region_transaction_targets t LEFT JOIN (SELECT region, SUM(new_deal_amount) AS deal_amount FROM meeting_transaction_details WHERE deal_type = '新成交' GROUP BY region) d ON t.region = d.region HAVING completion_rate IS NOT NULL) t",
    },

    # ═══════════════════════════════════════════════════════
    # 七、成交明细
    # ═══════════════════════════════════════════════════════
    {
        "question": "成交明细有哪些？",
        "sql": "SELECT region, customer_name, deal_type, deal_content, new_deal_amount, received_amount, consumed_amount FROM meeting_transaction_details ORDER BY new_deal_amount DESC",
    },
    {
        "question": "有哪些成交记录？",
        "sql": "SELECT region, customer_name, deal_type, deal_content, new_deal_amount, received_amount, consumed_amount FROM meeting_transaction_details ORDER BY new_deal_amount DESC",
    },
    {
        "question": "各大区成交金额分别是多少？",
        "sql": "SELECT region, SUM(new_deal_amount) AS total_amount, SUM(received_amount) AS total_received FROM meeting_transaction_details GROUP BY region ORDER BY total_amount DESC",
    },

    # ═══════════════════════════════════════════════════════
    # 八、报名/签到矩阵
    # ═══════════════════════════════════════════════════════
    {
        "question": "各区域各等级报名和抵达情况？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, SUM(CASE WHEN customer_level_name LIKE '%千万%' THEN 1 ELSE 0 END) AS qianwan_register, SUM(CASE WHEN customer_level_name LIKE '%千万%' AND sign_in_status = '已签到' THEN 1 ELSE 0 END) AS qianwan_arrive, SUM(CASE WHEN customer_level_name LIKE '%百万%' OR customer_level_name LIKE '%300万%' THEN 1 ELSE 0 END) AS baiwan_register, SUM(CASE WHEN (customer_level_name LIKE '%百万%' OR customer_level_name LIKE '%300万%') AND sign_in_status = '已签到' THEN 1 ELSE 0 END) AS baiwan_arrive, COUNT(DISTINCT customer_unique_id) AS total_register, COUNT(DISTINCT CASE WHEN sign_in_status = '已签到' THEN customer_unique_id END) AS total_arrive FROM meeting_registration WHERE market_service_attribution IS NOT NULL GROUP BY region ORDER BY total_register DESC",
    },
    {
        "question": "签席矩阵表数据？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, SUM(CASE WHEN customer_level_name LIKE '%千万%' THEN 1 ELSE 0 END) AS qianwan_register, SUM(CASE WHEN customer_level_name LIKE '%千万%' AND sign_in_status = '已签到' THEN 1 ELSE 0 END) AS qianwan_arrive, SUM(CASE WHEN customer_level_name LIKE '%百万%' OR customer_level_name LIKE '%300万%' THEN 1 ELSE 0 END) AS baiwan_register, SUM(CASE WHEN (customer_level_name LIKE '%百万%' OR customer_level_name LIKE '%300万%') AND sign_in_status = '已签到' THEN 1 ELSE 0 END) AS baiwan_arrive, COUNT(DISTINCT customer_unique_id) AS total_register, COUNT(DISTINCT CASE WHEN sign_in_status = '已签到' THEN customer_unique_id END) AS total_arrive FROM meeting_registration WHERE market_service_attribution IS NOT NULL GROUP BY region ORDER BY total_register DESC",
    },

    # ═══════════════════════════════════════════════════════
    # 九、运营数据
    # ═══════════════════════════════════════════════════════
    {
        "question": "各场景参与人数是多少？",
        "sql": "SELECT scene, SUM(people_count) AS total_people FROM meeting_schedule_stats WHERE time_period NOT LIKE '%率%' AND time_period NOT LIKE '%占比%' GROUP BY scene ORDER BY total_people DESC",
    },
    {
        "question": "各时段人数统计？",
        "sql": "SELECT schedule_date, time_period, SUM(people_count) AS total_people FROM meeting_schedule_stats WHERE time_period NOT LIKE '%率%' AND time_period NOT LIKE '%占比%' GROUP BY schedule_date, time_period ORDER BY schedule_date, time_period",
    },
    {
        "question": "离开了多少人？",
        "sql": "SELECT SUM(people_count) AS total_leave FROM meeting_schedule_stats WHERE time_period = '离开人数'",
    },
    {
        "question": "到院体检多少人？",
        "sql": "SELECT SUM(people_count) AS total_hospital FROM meeting_schedule_stats WHERE time_period = '医院人数合计'",
    },
    {
        "question": "每天签到人数趋势？",
        "sql": "SELECT sign_in_date_1, COUNT(DISTINCT customer_unique_id) AS checkin_count FROM meeting_registration WHERE sign_in_status = '已签到' AND sign_in_date_1 IS NOT NULL GROUP BY sign_in_date_1 ORDER BY sign_in_date_1",
    },
    {
        "question": "听课人数是多少？",
        "sql": "SELECT schedule_date, SUM(people_count) AS total FROM meeting_schedule_stats WHERE time_period LIKE '%听课%' GROUP BY schedule_date ORDER BY schedule_date",
    },
    {
        "question": "用餐人数是多少？",
        "sql": "SELECT schedule_date, time_period, SUM(people_count) AS total FROM meeting_schedule_stats WHERE time_period LIKE '%餐%' GROUP BY schedule_date, time_period ORDER BY schedule_date",
    },
    {
        "question": "接机了多少人？",
        "sql": "SELECT COUNT(DISTINCT customer_unique_id) AS pickup_count FROM meeting_registration WHERE flight_info IS NOT NULL AND sign_in_date_1 IS NOT NULL",
    },

    # ═══════════════════════════════════════════════════════
    # 十、客户分析表相关
    # ═══════════════════════════════════════════════════════
    {
        "question": "各区域客户等级分布？",
        "sql": "SELECT region, customer_level, COUNT(*) AS cnt FROM meeting_customer_analysis WHERE region IS NOT NULL GROUP BY region, customer_level ORDER BY region, cnt DESC",
    },
    {
        "question": "目标客户有多少？",
        "sql": "SELECT COUNT(*) AS target_count FROM meeting_customer_analysis WHERE min_deal >= 100",
    },
    {
        "question": "各区域目标客户数量？",
        "sql": "SELECT region, COUNT(*) AS target_count FROM meeting_customer_analysis WHERE min_deal >= 100 AND region IS NOT NULL GROUP BY region ORDER BY target_count DESC",
    },
    {
        "question": "客户铺垫成熟度分布？",
        "sql": "SELECT prep_maturity, COUNT(*) AS cnt FROM meeting_customer_analysis WHERE prep_maturity IS NOT NULL GROUP BY prep_maturity ORDER BY cnt DESC",
    },

    # ═══════════════════════════════════════════════════════
    # 十一、方案相关
    # ═══════════════════════════════════════════════════════
    {
        "question": "方案概览数据？",
        "sql": "SELECT p.region, p.proposal_type, p.target_count, COUNT(d.id) AS achieved_count FROM meeting_region_proposal_targets p LEFT JOIN meeting_transaction_details d ON p.region = d.region AND d.deal_type LIKE '%新成交%' AND (d.deal_content LIKE CONCAT('%', p.proposal_type, '%') OR (p.proposal_type LIKE '%海心卡%' AND (d.deal_content LIKE '%海心卡%' OR d.deal_content LIKE '%细胞卡%')) OR (p.proposal_type LIKE '%细胞卡%' AND (d.deal_content LIKE '%海心卡%' OR d.deal_content LIKE '%细胞卡%'))) GROUP BY p.region, p.proposal_type, p.target_count ORDER BY p.region, p.proposal_type",
    },
    {
        "question": "各方案成交情况？",
        "sql": "SELECT plan_type, COUNT(*) AS deal_count, SUM(new_deal_amount) AS total_amount FROM meeting_transaction_details WHERE plan_type IS NOT NULL GROUP BY plan_type ORDER BY total_amount DESC",
    },

    # ═══════════════════════════════════════════════════════
    # 十二、综合/汇总查询
    # ═══════════════════════════════════════════════════════
    {
        "question": "给我一个整体数据摘要",
        "sql": "SELECT (SELECT COUNT(DISTINCT customer_unique_id) FROM meeting_registration WHERE real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%') AS registered, (SELECT COUNT(DISTINCT customer_unique_id) FROM meeting_registration WHERE sign_in_status = '已签到' AND real_identity IS NOT NULL AND real_identity NOT LIKE '%市场%' AND real_identity NOT LIKE '%陪同%') AS arrived, (SELECT ROUND(SUM(new_deal_amount) / 10000, 2) FROM meeting_transaction_details) AS deal_amount_wan, (SELECT ROUND(SUM(received_amount) / 10000, 2) FROM meeting_transaction_details) AS received_wan, (SELECT ROUND(SUM(consumed_amount) / 10000, 2) FROM meeting_transaction_details) AS consumed_wan",
    },
    {
        "question": "各大区有多少客户？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, COUNT(DISTINCT customer_unique_id) AS cnt FROM meeting_registration WHERE market_service_attribution IS NOT NULL GROUP BY region ORDER BY cnt DESC",
    },
    {
        "question": "某个大区的详细数据？",
        "sql": "SELECT SUBSTRING_INDEX(market_service_attribution, ',', 1) AS region, COUNT(DISTINCT customer_unique_id) AS total_register, COUNT(DISTINCT CASE WHEN sign_in_status = '已签到' THEN customer_unique_id END) AS arrived, ROUND(COUNT(DISTINCT CASE WHEN sign_in_status = '已签到' THEN customer_unique_id END) * 100.0 / COUNT(DISTINCT customer_unique_id), 2) AS arrival_rate FROM meeting_registration WHERE market_service_attribution IS NOT NULL GROUP BY region ORDER BY total_register DESC",
    },
]
