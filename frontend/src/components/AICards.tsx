import React from 'react';
import { motion } from 'motion/react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Maximize2, Trash2, Edit } from 'lucide-react';
import {
  AssetCard,
  IdentityContactCard,
  BasicHealthDataCard,
  HealthStatusMedicalHistoryCard,
  PhysicalExamStatusCard,
  LifestyleHabitsCard,
  PsychologyEmotionCard,
  PersonalPreferencesCard,
  HealthGoalsCard,
  ConsumptionAbilityCard,
  CustomerRelationsCard,
  EducationRecordsCard,
  PrecautionsCard,
  ConsultationRecordsCard,
  RemarksCard,
  ExecutionDateCard
} from './AIComponentManagementView';

export const SortableCard: React.FC<{
  id: string,
  title: string,
  children: React.ReactNode,
  colSpan: number,
  onEnlarge?: () => void,
  onDelete?: () => void
}> = ({ id, title, children, colSpan, onEnlarge, onDelete }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 10 : 1,
  };

  // Responsive flex mapping for auto-stretch and arrange
  const flexClass = {
    3: 'flex-[1_1_100%] md:flex-[3_1_280px]',
    4: 'flex-[1_1_100%] md:flex-[4_1_320px]',
    6: 'flex-[1_1_100%] md:flex-[6_1_450px]',
    12: 'flex-[1_1_100%]'
  }[colSpan] || 'flex-[1_1_100%] md:flex-[1_1_300px]';

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`${flexClass} bg-white dark:bg-slate-800 rounded-2xl p-5 shadow-sm border border-slate-200 dark:border-slate-700 flex flex-col ${isDragging ? 'opacity-50 shadow-xl' : ''} transition-all duration-300`}
    >
      <div
        className="flex justify-between items-center mb-4 pb-3 border-b border-slate-100 dark:border-slate-700/50 cursor-grab active:cursor-grabbing"
        {...attributes}
        {...listeners}
      >
        <div className="flex items-center space-x-2">
          <div className="w-1.5 h-4 bg-blue-500 rounded-full"></div>
          <h3 className="font-bold text-slate-800 dark:text-slate-200">{title}</h3>
        </div>
        <div className="flex items-center space-x-1">
          <button
            onPointerDown={(e) => e.stopPropagation()}
            onClick={onEnlarge}
            className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors cursor-pointer"
            title="放大预览"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
          <button
            onPointerDown={(e) => e.stopPropagation()}
            onClick={onDelete}
            className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"
            title="删除卡片"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="flex-1">
        {children}
      </div>
    </div>
  );
};

export const CardPanorama = () => (
  <div className="flex flex-col h-full">
    <div className="flex items-center space-x-2 mb-4">
      <span className="px-3 py-1 bg-blue-50 text-blue-600 text-xs rounded-full font-medium">高价值VIP</span>
      <span className="px-3 py-1 bg-red-50 text-red-600 text-xs rounded-full font-medium">中风险流失</span>
      <span className="px-3 py-1 bg-green-50 text-green-600 text-xs rounded-full font-medium">续费窗口开启</span>
    </div>
    <div className="flex justify-between items-center flex-1">
      <div className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
        <p>1. 张美玲当前处于方案平稳期，客户价值需要新一轮经营动作承接。</p>
        <p>2. 历史消费与当前方案适配度较高，具备续费与升单基础。</p>
        <p>3. 最近 30 天主动沟通频次下降，需尽快用结果型话题拉回活跃度。</p>
      </div>
      <div className="flex space-x-6 ml-4">
        <div className="text-center">
          <div className="text-xs text-slate-500 mb-1">续费概率</div>
          <div className="text-3xl font-bold text-blue-500">68%</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-slate-500 mb-1">风险等级</div>
          <div className="text-3xl font-bold text-red-500">中</div>
        </div>
      </div>
    </div>
  </div>
);

export const CardRisk = () => (
  <div className="flex flex-col h-full justify-center space-y-4">
    <div className="flex items-start space-x-2">
      <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 flex-shrink-0"></div>
      <p className="text-sm text-slate-700 dark:text-slate-300">最近 30 天沟通下降，需 72 小时内主动回访</p>
    </div>
    <div className="flex items-start space-x-2">
      <div className="w-1.5 h-1.5 rounded-full bg-orange-500 mt-1.5 flex-shrink-0"></div>
      <p className="text-sm text-slate-700 dark:text-slate-300">当前方案进入平稳期，需补充新阶段价值感</p>
    </div>
    <div className="flex items-start space-x-2">
      <div className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 flex-shrink-0"></div>
      <p className="text-sm text-slate-700 dark:text-slate-300">建议：先回访激活，再承接续费</p>
    </div>
  </div>
);

export const CardObjection = () => (
  <div className="flex flex-col h-full justify-center space-y-3">
    <p className="text-sm text-slate-700 dark:text-slate-300">可能异议 1：我现在状态挺稳定的，先不用续了。</p>
    <p className="text-sm text-slate-500 dark:text-slate-400">建议回应：理解当前感受，但这阶段最能降低波动风险。</p>
    <p className="text-sm text-slate-700 dark:text-slate-300">可能异议 2：项目太多，先不做升级。</p>
  </div>
);

export const CardRenewal = () => (
  <div className="flex flex-col h-full justify-center space-y-4">
    <div className="bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl flex justify-between items-center">
      <div>
        <div className="font-bold text-slate-900 dark:text-white">基础项：年度健康管理套餐续费</div>
        <div className="text-xs text-slate-500 mt-1">建议优先承接原有方案，保持客户连续性</div>
      </div>
      <div className="text-xl font-bold text-slate-900 dark:text-white">¥28,000</div>
    </div>
    <div className="text-sm font-bold text-slate-700 dark:text-slate-300">
      承接策略：回访后3日内给出正式续费方案
    </div>
  </div>
);

export const CardUpsell = () => (
  <div className="flex flex-col h-full justify-center space-y-4">
    <div className="flex items-center space-x-4">
      <div className="bg-purple-50 dark:bg-purple-900/30 p-4 rounded-xl text-center">
        <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">高</div>
        <div className="text-xs text-purple-500 font-medium mt-1">AI升单潜力</div>
        <div className="text-xs text-slate-600 dark:text-slate-400 mt-2">潜在新增 ¥40,000</div>
      </div>
      <div className="flex-1">
        <p className="text-sm text-slate-700 dark:text-slate-300 mb-3">
          推荐组合：中医调理金卡 + 光电抗衰疗程，适合当前客户阶段，续费完成后可进一步放大客单。
        </p>
        <div className="flex space-x-2">
          <span className="px-2 py-1 bg-blue-50 text-blue-600 text-xs rounded font-medium">匹配度 87%</span>
          <span className="px-2 py-1 bg-green-50 text-green-600 text-xs rounded font-medium">转化率 45%</span>
        </div>
      </div>
    </div>
  </div>
);

export const CardConsumption = () => (
  <div className="flex flex-col h-full justify-center space-y-4 relative before:absolute before:left-[5px] before:top-2 before:bottom-2 before:w-px before:bg-slate-200 dark:before:bg-slate-700">
    <div className="relative pl-5 flex justify-between items-start">
      <div className="absolute left-0 top-1.5 w-2.5 h-2.5 bg-blue-500 rounded-full"></div>
      <div>
        <div className="text-sm font-bold text-slate-800 dark:text-slate-200">4月 启动期</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">体检评估 + 首次中医调理</div>
      </div>
      <div className="text-xs text-blue-500 font-medium">预计消耗 ¥8,500</div>
    </div>
    <div className="relative pl-5 flex justify-between items-start">
      <div className="absolute left-0 top-1.5 w-2.5 h-2.5 bg-purple-500 rounded-full"></div>
      <div>
        <div className="text-sm font-bold text-slate-800 dark:text-slate-200">5-6月 密集期</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">中医调理4次 + 光电抗衰2次</div>
      </div>
      <div className="text-xs text-blue-500 font-medium">预计消耗 ¥32,000</div>
    </div>
    <div className="relative pl-5 flex justify-between items-start">
      <div className="absolute left-0 top-1.5 w-2.5 h-2.5 bg-green-500 rounded-full"></div>
      <div>
        <div className="text-sm font-bold text-slate-800 dark:text-slate-200">7-9月 巩固期</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">复查 + 维护疗程组合</div>
      </div>
      <div className="text-xs text-blue-500 font-medium">预计消耗 ¥27,500</div>
    </div>
  </div>
);

export const CardInsight = () => (
  <div className="flex flex-col h-full">
    <div className="flex items-center space-x-2 mb-4">
      <span className="px-3 py-1 bg-blue-50 text-blue-600 text-xs rounded-full font-medium">高贡献客户</span>
      <span className="px-3 py-1 bg-green-50 text-green-600 text-xs rounded-full font-medium">续费窗口客户</span>
      <span className="px-3 py-1 bg-red-50 text-red-600 text-xs rounded-full font-medium">需主动回访</span>
    </div>
    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
      小智判断：张美玲目前属于“高价值但进入平稳期”的经营状态。适合先用结果回顾拉回活跃，再承接续费，并视反馈切入升单。
    </p>
  </div>
);

export const CardAction = () => (
  <div className="flex h-full items-center space-x-6">
    <div className="flex-1 bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl">
      <div className="text-sm text-slate-700 dark:text-slate-300 mb-2">推荐话术：</div>
      <p className="text-sm text-slate-600 dark:text-slate-400 italic">
        “阿姨，这阶段的基础问题已经进入关键承接窗口，我先帮您把下一阶段规划和维护方案整理好，再看哪些增值项更适合您目前状态。”
      </p>
    </div>
    <div className="flex-1 flex flex-col justify-between h-full">
      <div className="space-y-1 text-sm text-slate-700 dark:text-slate-300">
        <div className="font-bold mb-2">下一步动作</div>
        <p>1. 48 小时内主动回访</p>
        <p>2. 先承接续费，再切入升单</p>
        <p>3. 生成正式销售话术</p>
      </div>
      <div className="flex justify-end mt-4">
        <button className="px-4 py-2 bg-blue-500 text-white text-sm font-bold rounded-full shadow-md shadow-blue-500/20 hover:bg-blue-600 transition-colors">
          生成跟进话术
        </button>
      </div>
    </div>
  </div>
);

export const AI_CARDS_DATA = [
  // Management Cards
  // { id: 'asset', title: '客户资产概览', component: (props: any) => <AssetCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'identity-contact', title: '身份与联系信息', component: (props: any) => <IdentityContactCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'basic-health-data', title: '健康基础数据', component: (props: any) => <BasicHealthDataCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'health-status-medical-history', title: '健康状况与医疗史', component: (props: any) => <HealthStatusMedicalHistoryCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'physical-exam-status', title: '体检情况', component: (props: any) => <PhysicalExamStatusCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'lifestyle-habits', title: '生活方式与习惯', component: (props: any) => <LifestyleHabitsCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'psychology-emotion', title: '心理与情绪', component: (props: any) => <PsychologyEmotionCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'personal-preferences', title: '个人喜好与优势', component: (props: any) => <PersonalPreferencesCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'health-goals', title: '健康目标与核心痛点', component: (props: any) => <HealthGoalsCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'consumption-ability', title: '消费能力与背景', component: (props: any) => <ConsumptionAbilityCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'customer-relations', title: '客户关系与服务记录', component: (props: any) => <CustomerRelationsCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'education-records', title: '教育铺垫记录', component: (props: any) => <EducationRecordsCard {...props} hideHeader={true} context="workbench" />, colSpan: 12 },
  { id: 'precautions', title: '注意事项', component: (props: any) => <PrecautionsCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'consultation-records', title: '综合分析及咨询记录', component: (props: any) => <ConsultationRecordsCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'remarks', title: '备注', component: (props: any) => <RemarksCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
  { id: 'execution-date', title: '负责人及执行日期', component: (props: any) => <ExecutionDateCard {...props} hideHeader={true} context="workbench" />, colSpan: 4 },
];
