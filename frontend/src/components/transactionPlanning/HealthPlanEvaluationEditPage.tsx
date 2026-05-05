import React, { useMemo, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  Lock,
  Maximize2,
  PencilLine,
  Pill,
  ShieldCheck,
  Sparkles,
  Target,
} from 'lucide-react';

type StepItem = {
  title: string;
  meta: string;
  active?: boolean;
};

type InfoField = {
  label: string;
  value: string;
};

type HealthIndicator = {
  id: string;
  name: string;
  value: string;
  target: string;
  severity: string;
  quadrant: string;
};

type ImagingFinding = {
  id: string;
  category: string;
  exam: string;
  summary: string;
  severity: string;
  quadrant: string;
};

type TreatmentItem = {
  id: string;
  name: string;
  course: string;
  unitPrice: string;
  subtotal: string;
  note: string;
};

type TreatmentPhase = {
  id: string;
  title: string;
  items: TreatmentItem[];
  subtotal: string;
};

type RecommendationPlan = {
  id: string;
  title: string;
  amount: string;
  duration: string;
  description: string;
  accent: 'green' | 'amber' | 'slate';
  recommended?: boolean;
};

type RoiSummary = {
  hiddenCost: string;
  investment: string;
  expectedReturn: string;
  roi: string;
};

type GuaranteeSummary = {
  indicatorCommitment: string;
  symptomCommitment: string;
  serviceCommitment: string;
};

export interface HealthPlanEvaluationEditPayload {
  supplementNote: string;
  caseStudies: string;
  roiSummary: RoiSummary;
  guaranteeSummary: GuaranteeSummary;
  servicePromise: string;
  selectedPlanId: string;
}

export interface HealthPlanEvaluationEditPageProps {
  className?: string;
  onBack?: () => void;
  onDownload?: (payload: HealthPlanEvaluationEditPayload) => void;
  onSaveDraft?: (payload: HealthPlanEvaluationEditPayload) => void;
  onSubmitReview?: (payload: HealthPlanEvaluationEditPayload) => void;
  onPublish?: (payload: HealthPlanEvaluationEditPayload) => void;
}

const STEP_ITEMS: StepItem[] = [
  { title: '方案评估', meta: '当前阶段', active: true },
  { title: '方案确认', meta: '待处理' },
  { title: '确认发布', meta: '最终步骤' },
];

const CUSTOMER_FIELDS: InfoField[] = [
  { label: '客户姓名', value: '王先生' },
  { label: '性别/年龄', value: '男 / 48岁' },
  { label: '职业', value: '企业管理层（IT公司 CEO）' },
  { label: '消费等级', value: '高端客户（VIP）' },
  { label: '首次到院', value: '2023年6月' },
  { label: '历史消费', value: '累计约35万元' },
  { label: '账户余额', value: '12.8万元' },
  { label: '已规划项目', value: '心血管养护套餐（已消耗60%）' },
  { label: '到院频次', value: '年均3-4次' },
];

const HEALTH_INDICATORS: HealthIndicator[] = [
  {
    id: 'ldl-c',
    name: '低密度脂蛋白胆固醇 (LDL-C)',
    value: '4.34',
    target: '< 2.6 mmol/L',
    severity: '中度升高',
    quadrant: '监测区',
  },
  {
    id: 'hcy',
    name: '同型半胱氨酸 (Hcy)',
    value: '18.5',
    target: '5 - 15 μmol/L',
    severity: '严重升高',
    quadrant: '干预区',
  },
  {
    id: 'hgb',
    name: '血红蛋白 (HGB)',
    value: '175',
    target: '130 - 175 g/L',
    severity: '轻度升高',
    quadrant: '预防区',
  },
];

const IMAGING_FINDINGS: ImagingFinding[] = [
  {
    id: 'cardiac-ultrasound',
    category: '心血管影像',
    exam: '心脏超声',
    summary: '左心室舒张功能减低',
    severity: '轻度异常',
    quadrant: '预防区',
  },
  {
    id: 'abdomen-ultrasound',
    category: '消化影像',
    exam: '腹部超声',
    summary: '脂肪肝（中度）；胆囊息肉（0.6cm）',
    severity: '中度异常',
    quadrant: '预防区',
  },
];

const TREATMENT_PHASES: TreatmentPhase[] = [
  {
    id: 'phase-1',
    title: '第一阶段：快速改善期（第1-3个月）',
    subtotal: '63,200元',
    items: [
      {
        id: 'phase-1-item-1',
        name: '心脑血管预防套餐',
        course: '12次',
        unitPrice: '3,800元',
        subtotal: '45,600元',
        note: '针对血脂、血压与动脉粥样硬化高风险因素进行集中干预。',
      },
      {
        id: 'phase-1-item-2',
        name: '同型半胱氨酸靶向调理',
        course: '8次',
        unitPrice: '2,200元',
        subtotal: '17,600元',
        note: '重点改善甲基化代谢异常，降低未来心脑血管事件风险。',
      },
    ],
  },
  {
    id: 'phase-2',
    title: '第二阶段：稳定巩固期（第4-6个月）',
    subtotal: '52,000元',
    items: [
      {
        id: 'phase-2-item-1',
        name: '代谢综合修复计划',
        course: '10次',
        unitPrice: '3,000元',
        subtotal: '30,000元',
        note: '围绕脂肪肝、体重管理和胰岛素抵抗进行持续性干预。',
      },
      {
        id: 'phase-2-item-2',
        name: '微循环改善支持',
        course: '8次',
        unitPrice: '2,750元',
        subtotal: '22,000元',
        note: '提升血管弹性与供氧能力，改善疲劳、头晕等主诉。',
      },
    ],
  },
  {
    id: 'phase-3',
    title: '第三阶段：长期维护期（第7-12个月）',
    subtotal: '41,000元',
    items: [
      {
        id: 'phase-3-item-1',
        name: '年度风险复评与动态随访',
        course: '6次',
        unitPrice: '3,500元',
        subtotal: '21,000元',
        note: '动态追踪指标趋势，及时调整干预节奏与重点。',
      },
      {
        id: 'phase-3-item-2',
        name: '生活方式强化管理',
        course: '10次',
        unitPrice: '2,000元',
        subtotal: '20,000元',
        note: '配合饮食、运动、作息方案，巩固阶段性成果。',
      },
    ],
  },
];

const RECOMMENDATION_PLANS: RecommendationPlan[] = [
  {
    id: 'plan-a',
    title: '方案A：完整三阶段方案',
    amount: '156,200元',
    duration: '12个月',
    description: '从高风险到低风险，完整覆盖风险评估、强化干预与长期维护。',
    accent: 'green',
    recommended: true,
  },
  {
    id: 'plan-b',
    title: '方案B：快速改善方案',
    amount: '76,000元',
    duration: '3个月',
    description: '先聚焦主诉改善与核心指标下降，适合短周期启动。',
    accent: 'amber',
  },
  {
    id: 'plan-c',
    title: '方案C：预防性方案',
    amount: '45,200元',
    duration: '6个月',
    description: '用于稳定当前状态并延缓风险进展，适合保守决策客户。',
    accent: 'slate',
  },
];

const DEFAULT_SUPPLEMENT_NOTE =
  '系统已结合客户历史资料预填分析摘要，当前建议补充本次沟通重点、预算倾向与异议信息，以便进一步优化方案呈现与成交话术。';

const DEFAULT_CASE_STUDIES =
  '案例一：赵先生（52岁）- 血脂异常改善\n• 干预前：LDL-C 5.1 mmol/L，伴有轻微头晕\n• 干预后：LDL-C 降至 2.8 mmol/L，头晕消失，精力明显提升\n\n案例二：孙女士（45岁）- 同型半胱氨酸显著下降\n• 干预前：Hcy 22.5 μmol/L，家族性高血压风险\n• 干预后：Hcy 降至 11.2 μmol/L，血压趋于平稳，整体代谢改善';

const DEFAULT_ROI_SUMMARY: RoiSummary = {
  hiddenCost: '预计未来3-5年医疗支出约 40-60万元',
  investment: '156,200元',
  expectedReturn: '降低重大心脑血管疾病发生风险 70%以上，生活质量显著提升',
  roi: '约 150% - 200%',
};

const DEFAULT_GUARANTEE_SUMMARY: GuaranteeSummary = {
  indicatorCommitment: '若按方案执行后关键目标指标未达预期，可提供免费强化疗程。',
  symptomCommitment: '针对头晕、乏力等核心不适，预期 1-3 个月内获得明显缓解。',
  serviceCommitment: '全程私人医生级管理服务，24小时健康咨询响应。',
};

const DEFAULT_SERVICE_PROMISE =
  '服务承诺：专属医生团队24小时咨询服务，定期复查评估，动态调整方案。';

const ACCENT_CLASS_MAP: Record<RecommendationPlan['accent'], string> = {
  green: 'border-emerald-400 bg-emerald-950/40 text-emerald-200',
  amber: 'border-amber-400 bg-amber-950/30 text-amber-200',
  slate: 'border-slate-600 bg-slate-900 text-slate-200',
};

interface PanelCardProps {
  title: string;
  icon: LucideIcon;
  children: React.ReactNode;
  rightSlot?: React.ReactNode;
}

function PanelCard({ title, icon: Icon, children, rightSlot }: PanelCardProps) {
  return (
    <section className="overflow-hidden rounded-2xl border border-[#2E2E2E] bg-[#1A1A1A]">
      <div className="flex items-center justify-between border-b border-[#2E2E2E] px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#2B2115] text-[#FF9A38]">
            <Icon className="h-4 w-4" />
          </div>
          <div className="text-base font-semibold text-white">{title}</div>
        </div>
        {rightSlot}
      </div>
      <div className="space-y-5 p-6">{children}</div>
    </section>
  );
}

interface InfoFieldCardProps {
  label: string;
  value: string;
}

function InfoFieldCard({ label, value }: InfoFieldCardProps) {
  return (
    <div className="rounded-xl border border-[#242424] bg-[#151515] px-4 py-3">
      <div className="text-xs text-[#888888]">{label}</div>
      <div className="mt-1 text-sm font-medium text-white">{value}</div>
    </div>
  );
}

function EditableBlock({
  label,
  value,
  onChange,
  minRows = 4,
}: {
  label: string;
  value: string;
  onChange: (nextValue: string) => void;
  minRows?: number;
}) {
  return (
    <label className="block">
      <div className="mb-2 text-sm font-medium text-[#D0D0D0]">{label}</div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={minRows}
        className="w-full rounded-2xl border border-[#303030] bg-[#141414] px-4 py-3 text-sm leading-6 text-white outline-none transition focus:border-[#4D8DFF] focus:ring-2 focus:ring-[#4D8DFF]/20"
      />
    </label>
  );
}

function PreviewDivider() {
  return <div className="h-px w-full bg-[#D6DEE8]" />;
}

export function HealthPlanEvaluationEditPage({
  className,
  onBack,
  onDownload,
  onSaveDraft,
  onSubmitReview,
  onPublish,
}: HealthPlanEvaluationEditPageProps) {
  const [supplementNote, setSupplementNote] = useState(DEFAULT_SUPPLEMENT_NOTE);
  const [caseStudies, setCaseStudies] = useState(DEFAULT_CASE_STUDIES);
  const [roiSummary, setRoiSummary] = useState<RoiSummary>(DEFAULT_ROI_SUMMARY);
  const [guaranteeSummary, setGuaranteeSummary] = useState<GuaranteeSummary>(DEFAULT_GUARANTEE_SUMMARY);
  const [servicePromise, setServicePromise] = useState(DEFAULT_SERVICE_PROMISE);
  const [selectedPlanId, setSelectedPlanId] = useState(RECOMMENDATION_PLANS[0]?.id ?? '');

  const selectedPlan =
    RECOMMENDATION_PLANS.find((plan) => plan.id === selectedPlanId) ?? RECOMMENDATION_PLANS[0];

  const payload = useMemo<HealthPlanEvaluationEditPayload>(
    () => ({
      supplementNote,
      caseStudies,
      roiSummary,
      guaranteeSummary,
      servicePromise,
      selectedPlanId,
    }),
    [caseStudies, guaranteeSummary, roiSummary, selectedPlanId, servicePromise, supplementNote],
  );

  const riskSummaryText = useMemo(
    () =>
      [
        '体检时间：2026年2月20日',
        '',
        '异常指标总结：',
        ...HEALTH_INDICATORS.map((item) => `• ${item.name}：${item.value}（${item.severity}）`),
        '',
        '心脑血管风险等级：高风险',
        '未来5年心梗/脑卒中风险：约 12-15%',
      ].join('\n'),
    [],
  );

  return (
    <div className={`min-h-screen bg-[#111111] text-white ${className ?? ''}`}>
      <header className="border-b border-[#2E2E2E] bg-[#111111] px-4 py-4 md:px-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBack}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#2E2E2E] bg-[#181818] text-white transition hover:border-[#4D8DFF]/40 hover:bg-[#202020]"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <div>
              <div className="text-lg font-semibold">健康方案评估 - 编辑</div>
              <div className="text-sm text-[#8E8E8E]">面向咨询师的健康方案评估编辑与实时预览页面</div>
            </div>
          </div>

          <div className="flex flex-1 flex-wrap items-center justify-start gap-4 xl:justify-center">
            {STEP_ITEMS.map((item, index) => (
              <React.Fragment key={item.title}>
                <div className="min-w-[88px]">
                  <div className={`text-xs font-semibold ${item.active ? 'text-white' : 'text-[#B8B9B6]'}`}>{item.title}</div>
                  <div className="mt-1 text-[11px] text-[#7C7C7C]">{item.meta}</div>
                </div>
                {index < STEP_ITEMS.length - 1 ? <div className="hidden h-px w-9 bg-[#2E2E2E] sm:block" /> : null}
              </React.Fragment>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => onDownload?.(payload)}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#2E2E2E] bg-[#181818] text-white transition hover:border-[#4D8DFF]/40 hover:bg-[#202020]"
            >
              <Download className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => onSaveDraft?.(payload)}
              className="rounded-xl border border-[#2E2E2E] bg-[#181818] px-4 py-2.5 text-sm font-medium text-white transition hover:border-[#4D8DFF]/40 hover:bg-[#202020]"
            >
              保存草稿
            </button>
            <button
              type="button"
              onClick={() => onSubmitReview?.(payload)}
              className="rounded-xl border border-[#2851A3] bg-[#0F1E3D] px-4 py-2.5 text-sm font-medium text-[#C7D9FF] transition hover:bg-[#162A54]"
            >
              提交确认
            </button>
            <button
              type="button"
              onClick={() => onPublish?.(payload)}
              className="rounded-xl bg-[#2563EB] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#1F56CE]"
            >
              确认及发布
            </button>
          </div>
        </div>
      </header>

      <main className="grid min-h-[calc(100vh-89px)] grid-cols-1 xl:grid-cols-[minmax(0,1.4fr)_minmax(380px,0.95fr)]">
        <section className="overflow-y-auto bg-[#111111]">
          <div className="space-y-6 px-4 py-6 md:px-6 xl:px-8">
            <section className="rounded-2xl border border-[#2E2E2E] bg-[#1A1A1A] p-6">
              <div className="flex items-center justify-between">
                <div className="text-lg font-semibold text-white">客户基础信息</div>
                <div className="inline-flex items-center gap-2 rounded-full bg-[#2E2E2E] px-3 py-1 text-xs text-[#888888]">
                  <Lock className="h-3.5 w-3.5" />
                  只读
                </div>
              </div>
              <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {CUSTOMER_FIELDS.map((field) => (
                  <React.Fragment key={field.label}>
                    <InfoFieldCard label={field.label} value={field.value} />
                  </React.Fragment>
                ))}
              </div>
            </section>

            <PanelCard title="客户健康信息分析" icon={Activity}>
              <div>
                <div className="mb-3 flex items-center gap-2 text-sm text-[#CFCFCF]">
                  <span className="font-semibold">本次体检异常指标总结</span>
                  <button type="button" className="text-[#9A9A9A] transition hover:text-white">
                    <PencilLine className="h-3.5 w-3.5" />
                  </button>
                </div>
                <div className="mb-4 text-sm text-[#9E9E9E]">体检时间：2026年2月20日</div>
                <div className="overflow-hidden rounded-xl border border-[#333333]">
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-left text-sm">
                      <thead className="bg-[#222222] text-[#888888]">
                        <tr>
                          <th className="px-4 py-3 font-medium">检验指标</th>
                          <th className="px-4 py-3 font-medium">本次数值</th>
                          <th className="px-4 py-3 font-medium">理想值范围</th>
                          <th className="px-4 py-3 font-medium">异常程度</th>
                          <th className="px-4 py-3 font-medium">四象限落位</th>
                        </tr>
                      </thead>
                      <tbody>
                        {HEALTH_INDICATORS.map((row) => (
                          <tr key={row.id} className="border-t border-[#333333] bg-[#181818]">
                            <td className="px-4 py-3 text-white">{row.name}</td>
                            <td className="px-4 py-3 font-medium text-[#FF7043]">{row.value}</td>
                            <td className="px-4 py-3 text-[#9E9E9E]">{row.target}</td>
                            <td className="px-4 py-3 text-[#FF9A38]">{row.severity}</td>
                            <td className="px-4 py-3 text-[#B0B0B0]">{row.quadrant}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div>
                <div className="mb-3 text-sm font-semibold text-[#CFCFCF]">影像与专项检查摘要</div>
                <div className="overflow-hidden rounded-xl border border-[#333333]">
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-left text-sm">
                      <thead className="bg-[#222222] text-[#888888]">
                        <tr>
                          <th className="px-4 py-3 font-medium">分类</th>
                          <th className="px-4 py-3 font-medium">检查项目</th>
                          <th className="px-4 py-3 font-medium">结果摘要</th>
                          <th className="px-4 py-3 font-medium">异常等级</th>
                          <th className="px-4 py-3 font-medium">四象限落位</th>
                        </tr>
                      </thead>
                      <tbody>
                        {IMAGING_FINDINGS.map((row) => (
                          <tr key={row.id} className="border-t border-[#333333] bg-[#181818] align-top">
                            <td className="px-4 py-3 font-medium text-white">{row.category}</td>
                            <td className="px-4 py-3 text-white">{row.exam}</td>
                            <td className="px-4 py-3 text-[#C8C8C8]">{row.summary}</td>
                            <td className="px-4 py-3 text-[#FF9A38]">{row.severity}</td>
                            <td className="px-4 py-3 text-[#B0B0B0]">{row.quadrant}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl bg-[#222222] p-4">
                <div className="text-sm font-semibold text-[#CCCCCC]">四象限风险分类</div>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div>
                    <div className="text-xs text-[#888888]">心脑血管风险等级</div>
                    <div className="mt-1 text-base font-semibold text-[#FF7043]">高风险</div>
                  </div>
                  <div>
                    <div className="text-xs text-[#888888]">未来5年心梗/脑卒中风险</div>
                    <div className="mt-1 text-base font-semibold text-[#FF9A38]">约 12-15%</div>
                  </div>
                </div>
              </div>
            </PanelCard>

            <PanelCard title="个性化治疗方案设计" icon={Pill}>
              {TREATMENT_PHASES.map((phase) => (
                <div key={phase.id} className="rounded-2xl border border-[#2A2A2A] bg-[#151515]">
                  <div className="flex items-center gap-2 border-b border-[#2A2A2A] px-4 py-3">
                    <div className="text-sm font-semibold text-[#DDDDDD]">{phase.title}</div>
                    <button type="button" className="text-[#8E8E8E] transition hover:text-white">
                      <PencilLine className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-left text-sm">
                      <thead className="bg-[#202020] text-[#888888]">
                        <tr>
                          <th className="px-4 py-3 font-medium">项目名称</th>
                          <th className="px-4 py-3 font-medium">疗程</th>
                          <th className="px-4 py-3 font-medium">单价</th>
                          <th className="px-4 py-3 font-medium">小计</th>
                          <th className="px-4 py-3 font-medium">说明</th>
                        </tr>
                      </thead>
                      <tbody>
                        {phase.items.map((item) => (
                          <tr key={item.id} className="border-t border-[#2F2F2F] align-top">
                            <td className="px-4 py-3 font-medium text-white">{item.name}</td>
                            <td className="px-4 py-3 text-[#E3E3E3]">{item.course}</td>
                            <td className="px-4 py-3 text-[#E3E3E3]">{item.unitPrice}</td>
                            <td className="px-4 py-3 text-[#E3E3E3]">{item.subtotal}</td>
                            <td className="px-4 py-3 text-[#A9A9A9]">{item.note}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex justify-end border-t border-[#2A2A2A] px-4 py-3 text-sm">
                    <span className="text-[#A9A9A9]">阶段小计：</span>
                    <span className="ml-2 font-semibold text-white">{phase.subtotal}</span>
                  </div>
                </div>
              ))}
            </PanelCard>

            <PanelCard title="真人成功案例" icon={FileText}>
              <EditableBlock label="案例讲解内容" value={caseStudies} onChange={setCaseStudies} minRows={10} />
            </PanelCard>

            <PanelCard title="投资回报分析（ROI）" icon={Sparkles}>
              <div className="grid gap-4 md:grid-cols-2">
                <EditableBlock
                  label="不干预的隐形成本"
                  value={roiSummary.hiddenCost}
                  onChange={(value) => setRoiSummary((prev) => ({ ...prev, hiddenCost: value }))}
                  minRows={3}
                />
                <EditableBlock
                  label="本方案年度总投资"
                  value={roiSummary.investment}
                  onChange={(value) => setRoiSummary((prev) => ({ ...prev, investment: value }))}
                  minRows={3}
                />
                <EditableBlock
                  label="预期收益"
                  value={roiSummary.expectedReturn}
                  onChange={(value) => setRoiSummary((prev) => ({ ...prev, expectedReturn: value }))}
                  minRows={4}
                />
                <EditableBlock
                  label="综合投资回报率"
                  value={roiSummary.roi}
                  onChange={(value) => setRoiSummary((prev) => ({ ...prev, roi: value }))}
                  minRows={3}
                />
              </div>
            </PanelCard>

            <PanelCard title="转化强化与承诺保障" icon={ShieldCheck}>
              <div className="grid gap-4 md:grid-cols-3">
                <EditableBlock
                  label="指标改善承诺"
                  value={guaranteeSummary.indicatorCommitment}
                  onChange={(value) => setGuaranteeSummary((prev) => ({ ...prev, indicatorCommitment: value }))}
                  minRows={5}
                />
                <EditableBlock
                  label="症状缓解承诺"
                  value={guaranteeSummary.symptomCommitment}
                  onChange={(value) => setGuaranteeSummary((prev) => ({ ...prev, symptomCommitment: value }))}
                  minRows={5}
                />
                <EditableBlock
                  label="服务品质承诺"
                  value={guaranteeSummary.serviceCommitment}
                  onChange={(value) => setGuaranteeSummary((prev) => ({ ...prev, serviceCommitment: value }))}
                  minRows={5}
                />
              </div>
              <EditableBlock label="服务承诺补充" value={servicePromise} onChange={setServicePromise} minRows={3} />
            </PanelCard>

            <PanelCard title="购买方案综合建议" icon={Target}>
              <EditableBlock label="文本补充" value={supplementNote} onChange={setSupplementNote} minRows={4} />

              <div className="grid gap-4 lg:grid-cols-3">
                {RECOMMENDATION_PLANS.map((plan) => {
                  const active = selectedPlanId === plan.id;
                  return (
                    <button
                      key={plan.id}
                      type="button"
                      onClick={() => setSelectedPlanId(plan.id)}
                      className={`rounded-2xl border p-5 text-left transition ${
                        active
                          ? `${ACCENT_CLASS_MAP[plan.accent]} ring-2 ring-white/20`
                          : 'border-[#313131] bg-[#151515] text-white hover:border-[#4D8DFF]/40'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        {plan.recommended ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2 py-1 text-[10px] font-semibold">
                            <CheckCircle2 className="h-3 w-3" />
                            推荐
                          </span>
                        ) : (
                          <span className="inline-flex rounded-full border border-white/10 px-2 py-1 text-[10px] font-semibold text-[#BEBEBE]">
                            备选
                          </span>
                        )}
                        <span className="text-sm font-semibold">{plan.amount}</span>
                      </div>
                      <div className="mt-4 text-base font-semibold">{plan.title}</div>
                      <div className="mt-1 text-sm opacity-90">{plan.duration}</div>
                      <p className="mt-3 text-sm leading-6 opacity-80">{plan.description}</p>
                    </button>
                  );
                })}
              </div>
            </PanelCard>
          </div>
        </section>

        <aside className="border-t border-[#CBCCC9] bg-[#F2F3F0] xl:border-l xl:border-t-0">
          <div className="flex items-center justify-between border-b border-[#CBCCC9] px-6 py-4">
            <div className="text-sm font-semibold text-[#111111]">实时预览</div>
            <button
              type="button"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-[#666666] transition hover:bg-black/5"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          </div>

          <div className="max-h-[calc(100vh-138px)] overflow-y-auto px-4 py-6 md:px-6">
            <div className="mx-auto w-full max-w-[780px] rounded-[20px] border border-[#D9E2EC] bg-gradient-to-b from-white to-[#F4F7FB] p-8 shadow-[0_8px_24px_rgba(15,23,42,0.10)] md:p-12">
              <div className="text-center text-[26px] font-bold text-[#0B1220]">个性化健康评估方案</div>
              <div className="mt-3 text-center text-xs text-[#475569]">方案编号：HPA-2026-0228-001 ｜ 生成日期：2026年2月28日</div>

              <div className="mt-8 space-y-7">
                <PreviewDivider />

                <section>
                  <div className="text-lg font-bold text-[#0F172A]">第一部分：客户基础信息</div>
                  <div className="mt-3 whitespace-pre-line text-sm leading-8 text-[#1F2937]">
                    {CUSTOMER_FIELDS.slice(0, 4).map((field) => `${field.label}：${field.value}`).join('\n')}
                  </div>
                </section>

                <PreviewDivider />

                <section>
                  <div className="text-lg font-bold text-[#0F172A]">第二部分：客户健康信息分析</div>
                  <div className="mt-3 whitespace-pre-line text-sm leading-8 text-[#1F2937]">{riskSummaryText}</div>
                </section>

                <PreviewDivider />

                <section>
                  <div className="text-lg font-bold text-[#0F172A]">第三部分：真人成功案例</div>
                  <div className="mt-3 whitespace-pre-line text-sm leading-8 text-[#1F2937]">{caseStudies}</div>
                </section>

                <PreviewDivider />

                <section>
                  <div className="text-lg font-bold text-[#0F172A]">第四部分：投资回报分析 (ROI)</div>
                  <div className="mt-3 whitespace-pre-line text-sm leading-8 text-[#1F2937]">
                    {`• 不干预的隐形成本：${roiSummary.hiddenCost}
• 本方案年度总投资：${roiSummary.investment}
• 预期收益：${roiSummary.expectedReturn}
• 综合投资回报率：${roiSummary.roi}`}
                  </div>
                </section>

                <PreviewDivider />

                <section>
                  <div className="text-lg font-bold text-[#0F172A]">第五部分：转化强化与承诺保障</div>
                  <div className="mt-3 whitespace-pre-line text-sm leading-8 text-[#1F2937]">
                    {`• 指标改善承诺：${guaranteeSummary.indicatorCommitment}
• 症状缓解承诺：${guaranteeSummary.symptomCommitment}
• 服务品质承诺：${guaranteeSummary.serviceCommitment}

${servicePromise}`}
                  </div>
                </section>

                <PreviewDivider />

                <section>
                  <div className="text-lg font-bold text-[#0F172A]">第六部分：行动号召与购买建议</div>
                  <div className="mt-3 whitespace-pre-line text-sm leading-8 text-[#1F2937]">
                    {`方案A（推荐）：${RECOMMENDATION_PLANS[0].amount} / ${RECOMMENDATION_PLANS[0].duration}
方案B：${RECOMMENDATION_PLANS[1].amount} / ${RECOMMENDATION_PLANS[1].duration}
方案C：${RECOMMENDATION_PLANS[2].amount} / ${RECOMMENDATION_PLANS[2].duration}

【当前推荐】${selectedPlan.title}
金额：${selectedPlan.amount}
周期：${selectedPlan.duration}
说明：${selectedPlan.description}

【文本补充】
${supplementNote}`}
                  </div>
                </section>
              </div>
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

export default HealthPlanEvaluationEditPage;
