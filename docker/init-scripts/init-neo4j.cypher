// S5-8: 医疗知识图谱 Schema — 疾病/药物/症状/检查 实体 + 关系模型

// ── 约束与索引 ──────────────────────────────────────────
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (m:Medicine) REQUIRE m.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (s:Symptom) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Examination) REQUIRE e.name IS UNIQUE;

CREATE FULLTEXT INDEX knowledge_index IF NOT EXISTS FOR (n:Disease|Medicine|Symptom|Examination) ON EACH [n.name, n.description];

// ── 基础配伍禁忌图谱数据 ─────────────────────────────────
// 疾病
MERGE (d1:Disease {name: '高血压', description: '以动脉血压持续升高为特征的慢性病'})
MERGE (d2:Disease {name: '糖尿病', description: '以高血糖为特征的代谢性疾病'})
MERGE (d3:Disease {name: '冠心病', description: '冠状动脉粥样硬化性心脏病'})

// 药物
MERGE (m1:Medicine {name: '阿司匹林', description: '解热镇痛抗炎药，低剂量用于抗血小板'})
MERGE (m2:Medicine {name: '二甲双胍', description: '一线口服降糖药'})
MERGE (m3:Medicine {name: '氨氯地平', description: '钙通道阻滞剂，用于降压'})
MERGE (m4:Medicine {name: '华法林', description: '口服抗凝药'})
MERGE (m5:Medicine {name: '辛伐他汀', description: 'HMG-CoA还原酶抑制剂，调脂药'})

// 症状
MERGE (s1:Symptom {name: '头痛', description: '头部疼痛'})
MERGE (s2:Symptom {name: '多饮多尿', description: '饮水量和尿量显著增多'})
MERGE (s3:Symptom {name: '胸闷', description: '胸部闷胀感'})

// 检查
MERGE (e1:Examination {name: '血压监测', description: '测量动脉血压'})
MERGE (e2:Examination {name: '糖化血红蛋白', description: 'HbA1c，反映近2-3个月血糖水平'})
MERGE (e3:Examination {name: '心电图', description: '记录心脏电活动'})

// ── 关系 ─────────────────────────────────────────────────
// 疾病 - 症状
MERGE (d1)-[:HAS_SYMPTOM]->(s1)
MERGE (d2)-[:HAS_SYMPTOM]->(s2)
MERGE (d3)-[:HAS_SYMPTOM]->(s3)

// 疾病 - 治疗药物
MERGE (d1)-[:TREATED_BY]->(m3)
MERGE (d2)-[:TREATED_BY]->(m2)
MERGE (d3)-[:TREATED_BY]->(m1)
MERGE (d3)-[:TREATED_BY]->(m5)

// 疾病 - 检查
MERGE (d1)-[:DIAGNOSED_BY]->(e1)
MERGE (d2)-[:DIAGNOSED_BY]->(e2)
MERGE (d3)-[:DIAGNOSED_BY]->(e3)

// 配伍禁忌
MERGE (m1)-[:CONTRAINDICATED_WITH {reason: '增加出血风险', severity: 'HIGH'}]->(m4)
MERGE (m2)-[:INTERACTION_WITH {reason: '可能增强降糖效果', severity: 'MEDIUM'}]->(m1)

// 疾病共病关系
MERGE (d1)-[:COMORBID_WITH]->(d3)
MERGE (d2)-[:COMORBID_WITH]->(d3)
