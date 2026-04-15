import React, { useState } from 'react';
import { 
  User, 
  Users, 
  Stethoscope, 
  Wallet, 
  ClipboardList, 
  Activity, 
  Network,
  Search,
  Filter,
  MoreHorizontal,
  Edit,
  Eye,
  Plus,
  Settings,
  Link as LinkIcon,
  Save,
  X,
  LayoutTemplate,
  Unlock,
  Clock,
  CheckCircle2,
  TrendingUp,
  CreditCard,
  Package,
  Utensils,
  Moon,
  Coffee,
  Heart,
  Star,
  Target,
  FileText,
  MessageSquare,
  AlertTriangle,
  Calendar,
  ShoppingBag,
  Gem,
  ShieldCheck
} from 'lucide-react';

interface AIComponentManagementViewProps {
  setCurrentPage: (page: any) => void;
  isDarkMode: boolean;
  setIsDarkMode: (val: boolean) => void;
}

interface CardConfig {
  id: string;
  title: string;
  type: string;
  category?: string;
  url?: string;
}

const initialCards: CardConfig[] = [
  { id: 'asset-info', title: '客户资产概览', type: 'asset-info' },
  { id: 'identity-contact', title: '身份与联系信息', type: 'identity-contact' },
  { id: 'basic-health-data', title: '健康基础数据', type: 'basic-health-data' },
  { id: 'health-status-medical-history', title: '健康状况与医疗史', type: 'health-status-medical-history' },
  { id: 'physical-exam-status', title: '体检情况', type: 'physical-exam-status' },
  { id: 'lifestyle-habits', title: '生活方式与习惯', type: 'lifestyle-habits' },
  { id: 'psychology-emotion', title: '心理与情绪', type: 'psychology-emotion' },
  { id: 'personal-preferences', title: '个人喜好与优势', type: 'personal-preferences' },
  { id: 'health-goals', title: '健康目标与核心痛点', type: 'health-goals' },
  { id: 'consumption-ability', title: '消费能力与背景', type: 'consumption-ability' },
  { id: 'customer-relations', title: '客户关系与服务记录', type: 'customer-relations' },
  { id: 'education-records', title: '教育铺垫记录', type: 'education-records' },
  { id: 'precautions', title: '注意事项', type: 'precautions' },
  { id: 'consultation-records', title: '综合分析及咨询记录', type: 'consultation-records' },
  { id: 'remarks', title: '备注', type: 'remarks' },
  { id: 'execution-date', title: '负责人及执行日期', type: 'execution-date' },
];

const initialLayouts = {
  'doctor': ['identity-contact', 'basic-health-data', 'health-status-medical-history', 'physical-exam-status', 'consultation-records'],
  'consultant': ['identity-contact', 'asset-info', 'health-goals', 'psychology-emotion', 'customer-relations'],
  'sales': ['identity-contact', 'asset-info', 'consumption-ability', 'education-records', 'precautions'],
};

// --- Mock Data for Cards ---

export const identityContactInfo = {
  name: '张三', gender: '女', birthDate: '1973-09-21', age: 52,
  bloodType: 'O型', idCard: '11010519730921XXXX', phone: '13800138000',
  wechat: 'zhangsan_wx', address: '北京市朝阳区建国路88号', maritalStatus: '已婚已育',
  children: '一子一女', occupation: '企业高管', spouseOccupation: '公务员'
};

export const basicHealthData = {
  height: '165', weight: '60', bmi: '22.0',
  bloodPressure: '120/80', bloodSugar: '5.2', bloodLipids: '正常',
  uricAcid: '300', heartRate: '75', lastMeasurementDate: '2024-03-01',
  menstruationNormal: '是', menstrualDescription: '无异常', pregnancyHistory: 'G2P2',
  privateProjectNeeds: '无', functionalMedicineResults: '无异常'
};

export const healthStatusMedicalHistory = {
  pastHistory: '无', currentMedication: '无', allergyHistory: '青霉素过敏',
  allergicDiseases: '无', familyHistory: '父亲有高血压', geneticDiseaseHistory: '无',
  recentDiscomfort: '偶尔失眠', bodyPainAreas: '颈部、肩部'
};

export const physicalExamStatus = {
  frequency: '每年一次', lastExamDate: '2023-10-15', institution: '北京协和医院',
  package: '全面VIP体检套餐', mainAbnormalIndicators: '甲状腺结节', doctorAdvice: '定期复查甲状腺彩超'
};

export const lifestyleHabits = {
  exerciseFrequency: '每周3次', exerciseDuration: '每次45分钟', exerciseType: '慢跑、瑜伽',
  workNature: '脑力劳动', sedentaryDuration: '每天8小时', dietaryStructure: '荤素搭配',
  vegFruitIntake: '充足', breakfastHabits: '每天吃', nutritionalSupplements: '复合维生素（每天）',
  dietaryTaste: '清淡', workRestRoutine: '规律', sleepDuration: '7小时',
  sleepQualityProblems: '入睡困难', drinkingWaterHabits: '每天1500ml', smoking: '无',
  drinking: '偶尔', coffeeTea: '每天1杯咖啡', sugaryDrinksSnacks: '少吃',
  nonWorkDeviceTime: '2小时', defecationStatus: '每天1次，正常', memorySpirit: '良好'
};

export const psychologyEmotion = {
  recentHealthFeeling: '一般', commonEmotions: '焦虑、疲惫', emotionImpact: '中度影响',
  stressCoping: '听音乐、运动', expectedEmotionalSupport: '倾听、专业建议',
  providerExpectation: '耐心、专业'
};

export const personalPreferences = {
  leisurePreference: '阅读、旅行', relaxationMethods: 'SPA、冥想', workEnvironment: '安静、独立',
  workPace: '适中', teamRole: '协作者', healthKnowledgeSource: '专业医生、健康讲座',
  incentivePreference: '效果反馈', healthManagementSuccess: '坚持运动',
  helpfulAbilities: '自律、学习能力', recentHealthHabit: '早睡早起',
  goodAtGuiding: '饮食搭配', biggestHealthChallenge: '控制体重',
  neededExternalSupport: '专业指导'
};

export const healthGoals = {
  biggestChallenge: '长期失眠', coreFactors: '工作压力大',
  targetGoal: '改善睡眠质量', urgentProblem: '入睡困难',
  beautyNeeds: '抗衰老', emotionalNeeds: '缓解焦虑',
  spendingMotivation: '追求高品质生活'
};

export const consumptionAbility = {
  personalIncome: '了解（高收入）', spouseIncome: '了解（高收入）',
  inStoreSingleConsumption: '¥ 5,000', inStoreAnnualConsumption: '¥ 100,000',
  inStoreRecent3Months: '¥ 20,000', inStoreCardBalance: '¥ 50,000',
  outStoreSingleConsumption: '¥ 10,000', outStoreAnnualConsumption: '¥ 200,000',
  outStoreRecent3Months: '¥ 50,000', outStoreCardBalance: '¥ 100,000',
  decisionMaker: '本人', luxuryConsumption: '¥ 50,000',
  carPurchase: '¥ 800,000', housePurchase: '¥ 10,000,000',
  insuranceAmount: '¥ 500,000', investmentAmount: '¥ 2,000,000',
  otherLargeConsumption: '无',
  healthSupplements: '¥ 10,000/年', healthProjects: '¥ 50,000/年',
  healthInstitutions: '某高端健康管理中心', medicalAesthetics: '¥ 30,000/年',
  privateProjects: '¥ 20,000/年', physicalExam: '北京协和医院VIP'
};

export const customerRelations = {
  yearsInStore: '3年', annualTotalConsumption: '¥ 150,000',
  referralStatus: '已转介绍2人', visitFrequency: '每月2次',
  mostTrustedPerson: '李健管', projectSatisfaction: '非常满意',
  knowsIncome: '是', privacyCommunication: '顺畅'
};

export const educationRecords = [
  { id: 1, round: '第1次', time: '2024-03-01', content: '睡眠管理重要性', feedback: '认可，愿意尝试' },
  { id: 2, round: '第2次', time: '2024-03-15', content: '功能医学检测介绍', feedback: '有兴趣，考虑中' },
  { id: 3, round: '第3次', time: '2024-04-01', content: '抗衰老方案沟通', feedback: '接受方案，准备实施' },
  { id: 4, round: '项目及价格是否铺垫', time: '2024-04-05', content: '已铺垫高端抗衰项目价格', feedback: '无异议' }
];

export const precautions = {
  consumptionHabits: '注重品质，不看重价格', mostCareAbout: '隐私保护、服务细节',
  communicationPreferences: '直接、高效', communicationTaboos: '过度推销、打探家庭隐私'
};

export const consultationRecords = {
  problemSummary: '严重失眠，伴随轻度焦虑', causeAnalysis: '工作压力大，作息不规律',
  consultationAdvice: '建议进行全面内分泌检查，配合心理疏导', otherMeasures: '调整作息，增加运动',
  functionalMedicineAdvice: '建议进行荷尔蒙平衡检测', consultant: '张医生',
  consultationDate: '2024-04-10'
};

export const remarks = {
  content: '客户近期准备出国旅行，需提前安排好相关健康服务。'
};

export const executionDate = {
  responsiblePerson: '李健管', executionDate: '2024-04-15', lastUpdateDate: '2024-04-12'
};

export const assetInfo = {
  totalBalance: '2,053,540',
  availableBalance: '2,043,360',
  frozenBalance: '0',
  pendingRecovery: '446,880',
  consumedBalance: '2,053,540',
  remainingQuantity: '16'
};

// --- Card Components ---

const CardHeader = ({ title, url, onEdit, showEdit = true }: { title: string, url?: string, onEdit?: () => void, showEdit?: boolean }) => (
  <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100 dark:border-slate-700/50">
    <div className="flex items-center space-x-2">
      <div className="w-1.5 h-4 bg-blue-500 rounded-full"></div>
      <h3 className="font-bold text-slate-800 dark:text-slate-200">
        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer" className="hover:text-blue-600 dark:hover:text-blue-400 transition-colors flex items-center">
            {title}
            <LinkIcon className="w-3.5 h-3.5 ml-1.5 text-slate-400" />
          </a>
        ) : title}
      </h3>
    </div>
    {onEdit && showEdit && (
      <button onClick={onEdit} className="p-1.5 text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors bg-slate-50 hover:bg-blue-50 dark:bg-slate-800 dark:hover:bg-blue-900/30 rounded-lg">
        <Edit className="w-4 h-4" />
      </button>
    )}
  </div>
);

const InnerCardWrapper = ({ title, url, hideHeader, onEdit, showEdit = true, children }: { title: string, url?: string, hideHeader?: boolean, onEdit?: () => void, showEdit?: boolean, children: React.ReactNode }) => {
  if (hideHeader) {
    return <div className="h-full">{children}</div>;
  }
  return (
    <div className="bg-gradient-to-b from-white to-slate-50/30 dark:from-slate-800 dark:to-slate-800/50 rounded-2xl p-5 shadow-[0_2px_10px_-3px_rgba(0,0,0,0.05)] hover:shadow-[0_8px_20px_rgba(0,0,0,0.08)] border border-slate-200/80 dark:border-slate-700/80 h-full transition-all duration-300 relative overflow-hidden">
      <CardHeader title={title} url={url} onEdit={onEdit} showEdit={showEdit} />
      {children}
    </div>
  );
};

const InfoItem = ({ label, value }: { label: string, value: string | number }) => (
  <div className="flex flex-col space-y-1">
    <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
    <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate" title={String(value)}>{value}</span>
  </div>
);

export const AssetCard = ({ title = "客户资产概览", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
      {/* Card 1 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-blue-50 to-blue-100/50 dark:from-blue-900/20 dark:to-blue-800/10 p-4 rounded-2xl border border-blue-100 dark:border-blue-800/30 group hover:shadow-md transition-all">
        <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity transform group-hover:scale-110 duration-500">
          <Wallet className="w-24 h-24 text-blue-600 dark:text-blue-400" />
        </div>
        <div className="flex items-center space-x-2 mb-3 relative z-10">
          <div className="p-2 bg-blue-100 dark:bg-blue-800/50 rounded-lg text-blue-600 dark:text-blue-400">
            <Wallet className="w-4 h-4" />
          </div>
          <div className="text-sm font-medium text-slate-500 dark:text-slate-400">医疗项目金总余额</div>
        </div>
        <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{assetInfo.totalBalance}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 relative z-10">包含所有可用及冻结金额</div>
      </div>

      {/* Card 2 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-emerald-50 to-emerald-100/50 dark:from-emerald-900/20 dark:to-emerald-800/10 p-4 rounded-2xl border border-emerald-100 dark:border-emerald-800/30 group hover:shadow-md transition-all">
        <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity transform group-hover:scale-110 duration-500">
          <Unlock className="w-24 h-24 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div className="flex items-center space-x-2 mb-3 relative z-10">
          <div className="p-2 bg-emerald-100 dark:bg-emerald-800/50 rounded-lg text-emerald-600 dark:text-emerald-400">
            <Unlock className="w-4 h-4" />
          </div>
          <div className="text-sm font-medium text-slate-500 dark:text-slate-400">可用医疗项目金余额</div>
        </div>
        <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{assetInfo.availableBalance}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 relative z-10">当前可直接用于消费的金额</div>
      </div>

      {/* Card 3 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-slate-50 to-slate-100/50 dark:from-slate-800/40 dark:to-slate-800/20 p-4 rounded-2xl border border-slate-200 dark:border-slate-700/50 group hover:shadow-md transition-all">
        <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity transform group-hover:scale-110 duration-500">
          <CheckCircle2 className="w-24 h-24 text-slate-600 dark:text-slate-400" />
        </div>
        <div className="flex items-center space-x-2 mb-3 relative z-10">
          <div className="p-2 bg-slate-200 dark:bg-slate-700 rounded-lg text-slate-600 dark:text-slate-400">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div className="text-sm font-medium text-slate-500 dark:text-slate-400">已冻结医疗项目金</div>
        </div>
        <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{assetInfo.frozenBalance}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 relative z-10">因业务处理暂时冻结的金额</div>
      </div>

      {/* Card 4 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-amber-50 to-amber-100/50 dark:from-amber-900/20 dark:to-amber-800/10 p-4 rounded-2xl border border-amber-100 dark:border-amber-800/30 group hover:shadow-md transition-all">
        <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity transform group-hover:scale-110 duration-500">
          <Clock className="w-24 h-24 text-amber-600 dark:text-amber-400" />
        </div>
        <div className="flex items-center space-x-2 mb-3 relative z-10">
          <div className="p-2 bg-amber-100 dark:bg-amber-800/50 rounded-lg text-amber-600 dark:text-amber-400">
            <Clock className="w-4 h-4" />
          </div>
          <div className="text-sm font-medium text-slate-500 dark:text-slate-400">待收回医疗项目金余额</div>
        </div>
        <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{assetInfo.pendingRecovery}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 relative z-10">预计近期可收回的金额</div>
      </div>

      {/* Card 5 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-purple-50 to-purple-100/50 dark:from-purple-900/20 dark:to-purple-800/10 p-4 rounded-2xl border border-purple-100 dark:border-purple-800/30 group hover:shadow-md transition-all">
        <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity transform group-hover:scale-110 duration-500">
          <TrendingUp className="w-24 h-24 text-purple-600 dark:text-purple-400" />
        </div>
        <div className="flex items-center space-x-2 mb-3 relative z-10">
          <div className="p-2 bg-purple-100 dark:bg-purple-800/50 rounded-lg text-purple-600 dark:text-purple-400">
            <TrendingUp className="w-4 h-4" />
          </div>
          <div className="text-sm font-medium text-slate-500 dark:text-slate-400">消耗医疗项目金余额</div>
        </div>
        <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{assetInfo.consumedBalance}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 relative z-10">历史累计已消耗的总金额</div>
      </div>

      {/* Card 6 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-cyan-50 to-cyan-100/50 dark:from-cyan-900/20 dark:to-cyan-800/10 p-4 rounded-2xl border border-cyan-100 dark:border-cyan-800/30 group hover:shadow-md transition-all">
        <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity transform group-hover:scale-110 duration-500">
          <Package className="w-24 h-24 text-cyan-600 dark:text-cyan-400" />
        </div>
        <div className="flex items-center space-x-2 mb-3 relative z-10">
          <div className="p-2 bg-cyan-100 dark:bg-cyan-800/50 rounded-lg text-cyan-600 dark:text-cyan-400">
            <Package className="w-4 h-4" />
          </div>
          <div className="text-sm font-medium text-slate-500 dark:text-slate-400">医疗项目剩余数量</div>
        </div>
        <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{assetInfo.remainingQuantity}</div>
        <div className="text-xs text-slate-500 dark:text-slate-400 relative z-10">当前可用的医疗项目总数</div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const IdentityContactCard = ({ title = "身份与联系信息", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-y-4 gap-x-4">
      <InfoItem label="客户姓名" value={identityContactInfo.name} />
      <InfoItem label="性别" value={identityContactInfo.gender} />
      <InfoItem label="出生年月日（阳历）" value={identityContactInfo.birthDate} />
      <InfoItem label="年龄" value={identityContactInfo.age} />
      <InfoItem label="血型" value={identityContactInfo.bloodType} />
      <InfoItem label="身份证号" value={identityContactInfo.idCard} />
      <InfoItem label="联系电话" value={identityContactInfo.phone} />
      <InfoItem label="微信" value={identityContactInfo.wechat} />
      <InfoItem label="家庭地址" value={identityContactInfo.address} />
      <InfoItem label="婚姻状况" value={identityContactInfo.maritalStatus} />
      <InfoItem label="子女情况" value={identityContactInfo.children} />
      <InfoItem label="本人职业" value={identityContactInfo.occupation} />
      <InfoItem label="配偶职业" value={identityContactInfo.spouseOccupation} />
    </div>
  </InnerCardWrapper>
);

export const BasicHealthDataCard = ({ title = "健康基础数据", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-y-4 gap-x-4">
        <InfoItem label="身高 (CM)" value={basicHealthData.height} />
        <InfoItem label="体重 (KG)" value={basicHealthData.weight} />
        <InfoItem label="BMI" value={basicHealthData.bmi} />
        <InfoItem label="血压 (MMHG)" value={basicHealthData.bloodPressure} />
        <InfoItem label="血糖 (MMOL/L)" value={basicHealthData.bloodSugar} />
        <InfoItem label="血脂 (总胆固醇/甘油三酯等)" value={basicHealthData.bloodLipids} />
        <InfoItem label="尿酸 (MMOL/L)" value={basicHealthData.uricAcid} />
        <InfoItem label="心率 (次/分)" value={basicHealthData.heartRate} />
        <InfoItem label="最近一次测量日期" value={basicHealthData.lastMeasurementDate} />
      </div>
      <div className="space-y-6">
        <div className="md:border-l md:pl-6 border-slate-100 dark:border-slate-700/50">
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 mb-3">女性健康</h4>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-y-4 gap-x-4">
            <InfoItem label="月经是否正常" value={basicHealthData.menstruationNormal} />
            <InfoItem label="经期描述/问题" value={basicHealthData.menstrualDescription} />
            <InfoItem label="孕产史" value={basicHealthData.pregnancyHistory} />
            <InfoItem label="私密项目需求/记录" value={basicHealthData.privateProjectNeeds} />
          </div>
        </div>
        <div className="md:border-l md:pl-6 pt-4 border-t border-slate-100 dark:border-slate-700/50">
          <InfoItem label="功能医学检测结果（如有）" value={basicHealthData.functionalMedicineResults} />
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const HealthStatusMedicalHistoryCard = ({ title = "健康状况与医疗史", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-y-4 gap-x-4">
      <InfoItem label="既往史（慢性病/手术/住院）" value={healthStatusMedicalHistory.pastHistory} />
      <InfoItem label="当前用药（药名/剂量/频次）" value={healthStatusMedicalHistory.currentMedication} />
      <InfoItem label="过敏史（药物/食物/其他）" value={healthStatusMedicalHistory.allergyHistory} />
      <InfoItem label="过敏性疾病（鼻炎/哮喘/湿疹等）" value={healthStatusMedicalHistory.allergicDiseases} />
      <InfoItem label="家族史（直系亲属疾病）" value={healthStatusMedicalHistory.familyHistory} />
      <InfoItem label="遗传病史" value={healthStatusMedicalHistory.geneticDiseaseHistory} />
      <InfoItem label="近期不适症状（参考问卷 Q5）" value={healthStatusMedicalHistory.recentDiscomfort} />
      <InfoItem label="身体疼痛部位" value={healthStatusMedicalHistory.bodyPainAreas} />
    </div>
  </InnerCardWrapper>
);

export const PhysicalExamStatusCard = ({ title = "体检情况", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-y-4 gap-x-4">
      <InfoItem label="体检频率" value={physicalExamStatus.frequency} />
      <InfoItem label="最近一次体检时间" value={physicalExamStatus.lastExamDate} />
      <InfoItem label="体检机构" value={physicalExamStatus.institution} />
      <InfoItem label="体检套餐" value={physicalExamStatus.package} />
      <InfoItem label="主要异常指标（乳腺/甲状腺/肺部/其他）" value={physicalExamStatus.mainAbnormalIndicators} />
      <InfoItem label="医生建议" value={physicalExamStatus.doctorAdvice} />
    </div>
  </InnerCardWrapper>
);

export const LifestyleHabitsCard = ({ title = "生活方式与习惯", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Exercise */}
      <div className="bg-blue-50/50 dark:bg-blue-900/10 rounded-xl p-4 border border-blue-100 dark:border-blue-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-blue-100 dark:bg-blue-800/50 rounded-lg text-blue-600 dark:text-blue-400">
            <Activity className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">运动与活动</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="运动频率" value={lifestyleHabits.exerciseFrequency} />
          <InfoItem label="运动时长" value={lifestyleHabits.exerciseDuration} />
          <InfoItem label="运动类型" value={lifestyleHabits.exerciseType} />
          <InfoItem label="工作性质" value={lifestyleHabits.workNature} />
          <InfoItem label="久坐时长" value={lifestyleHabits.sedentaryDuration} />
        </div>
      </div>

      {/* Diet */}
      <div className="bg-emerald-50/50 dark:bg-emerald-900/10 rounded-xl p-4 border border-emerald-100 dark:border-emerald-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-emerald-100 dark:bg-emerald-800/50 rounded-lg text-emerald-600 dark:text-emerald-400">
            <Utensils className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">饮食与营养</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="饮食结构" value={lifestyleHabits.dietaryStructure} />
          <InfoItem label="蔬菜水果摄入" value={lifestyleHabits.vegFruitIntake} />
          <InfoItem label="早餐习惯" value={lifestyleHabits.breakfastHabits} />
          <InfoItem label="营养补充剂" value={lifestyleHabits.nutritionalSupplements} />
          <InfoItem label="饮食口味偏好" value={lifestyleHabits.dietaryTaste} />
          <InfoItem label="饮水习惯" value={lifestyleHabits.drinkingWaterHabits} />
          <InfoItem label="含糖饮料/零食" value={lifestyleHabits.sugaryDrinksSnacks} />
        </div>
      </div>

      {/* Sleep */}
      <div className="bg-indigo-50/50 dark:bg-indigo-900/10 rounded-xl p-4 border border-indigo-100 dark:border-indigo-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-indigo-100 dark:bg-indigo-800/50 rounded-lg text-indigo-600 dark:text-indigo-400">
            <Moon className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">睡眠与作息</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="作息规律" value={lifestyleHabits.workRestRoutine} />
          <InfoItem label="睡眠时长" value={lifestyleHabits.sleepDuration} />
          <InfoItem label="睡眠质量问题" value={lifestyleHabits.sleepQualityProblems} />
          <InfoItem label="非工作电子设备" value={lifestyleHabits.nonWorkDeviceTime} />
        </div>
      </div>

      {/* Other */}
      <div className="bg-amber-50/50 dark:bg-amber-900/10 rounded-xl p-4 border border-amber-100 dark:border-amber-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-amber-100 dark:bg-amber-800/50 rounded-lg text-amber-600 dark:text-amber-400">
            <Coffee className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">其他习惯与状态</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="吸烟" value={lifestyleHabits.smoking} />
          <InfoItem label="饮酒" value={lifestyleHabits.drinking} />
          <InfoItem label="咖啡/浓茶" value={lifestyleHabits.coffeeTea} />
          <InfoItem label="排便情况" value={lifestyleHabits.defecationStatus} />
          <InfoItem label="记忆力/精气神" value={lifestyleHabits.memorySpirit} />
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const PsychologyEmotionCard = ({ title = "心理与情绪", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-rose-50/50 dark:bg-rose-900/10 rounded-xl p-4 border border-rose-100 dark:border-rose-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-rose-100 dark:bg-rose-800/50 rounded-lg text-rose-600 dark:text-rose-400">
            <Heart className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">情绪状态</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="近三个月整体健康感受" value={psychologyEmotion.recentHealthFeeling} />
          <InfoItem label="常见情绪" value={psychologyEmotion.commonEmotions} />
          <InfoItem label="情绪对健康影响程度" value={psychologyEmotion.emotionImpact} />
          <InfoItem label="压力应对方式" value={psychologyEmotion.stressCoping} />
        </div>
      </div>
      <div className="bg-blue-50/50 dark:bg-blue-900/10 rounded-xl p-4 border border-blue-100 dark:border-blue-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-blue-100 dark:bg-blue-800/50 rounded-lg text-blue-600 dark:text-blue-400">
            <MessageSquare className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">情绪支持需求</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="希望获得的情绪支持" value={psychologyEmotion.expectedEmotionalSupport} />
          <InfoItem label="对服务者情绪支持能力的期望" value={psychologyEmotion.providerExpectation} />
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const PersonalPreferencesCard = ({ title = "个人喜好与优势", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-amber-50/50 dark:bg-amber-900/10 rounded-xl p-4 border border-amber-100 dark:border-amber-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-amber-100 dark:bg-amber-800/50 rounded-lg text-amber-600 dark:text-amber-400">
            <Star className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">生活与工作偏好</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="闲暇偏好" value={personalPreferences.leisurePreference} />
          <InfoItem label="放松方式" value={personalPreferences.relaxationMethods} />
          <InfoItem label="工作环境偏好" value={personalPreferences.workEnvironment} />
          <InfoItem label="工作节奏偏好" value={personalPreferences.workPace} />
          <InfoItem label="团队角色偏好" value={personalPreferences.teamRole} />
        </div>
      </div>
      <div className="bg-emerald-50/50 dark:bg-emerald-900/10 rounded-xl p-4 border border-emerald-100 dark:border-emerald-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-emerald-100 dark:bg-emerald-800/50 rounded-lg text-emerald-600 dark:text-emerald-400">
            <Target className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">健康管理优势</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="获取健康知识方式" value={personalPreferences.healthKnowledgeSource} />
          <InfoItem label="激励方式偏好" value={personalPreferences.incentivePreference} />
          <InfoItem label="做得好的 1-2 件事" value={personalPreferences.healthManagementSuccess} />
          <InfoItem label="有助于健康的能力" value={personalPreferences.helpfulAbilities} />
          <InfoItem label="过去一年养成的习惯" value={personalPreferences.recentHealthHabit} />
          <InfoItem label="擅长指导他人的方面" value={personalPreferences.goodAtGuiding} />
          <InfoItem label="克服过的最大挑战" value={personalPreferences.biggestHealthChallenge} />
          <InfoItem label="最需要外界支持的方面" value={personalPreferences.neededExternalSupport} />
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const HealthGoalsCard = ({ title = "健康目标与核心痛点", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-red-50/50 dark:bg-red-900/10 rounded-xl p-4 border border-red-100 dark:border-red-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-red-100 dark:bg-red-800/50 rounded-lg text-red-600 dark:text-red-400">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">核心痛点</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="最大挑战/痛点" value={healthGoals.biggestChallenge} />
          <InfoItem label="核心影响因素" value={healthGoals.coreFactors} />
          <InfoItem label="迫切想解决的问题" value={healthGoals.urgentProblem} />
        </div>
      </div>
      <div className="bg-indigo-50/50 dark:bg-indigo-900/10 rounded-xl p-4 border border-indigo-100 dark:border-indigo-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-indigo-100 dark:bg-indigo-800/50 rounded-lg text-indigo-600 dark:text-indigo-400">
            <Target className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">目标与需求</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="希望实现的目标" value={healthGoals.targetGoal} />
          <InfoItem label="美丽需求" value={healthGoals.beautyNeeds} />
          <InfoItem label="情感需求" value={healthGoals.emotionalNeeds} />
          <InfoItem label="花钱动机" value={healthGoals.spendingMotivation} />
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const ConsumptionAbilityCard = ({ title = "消费能力与背景", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Income & Assets */}
      <div className="bg-blue-50/50 dark:bg-blue-900/10 rounded-xl p-4 border border-blue-100 dark:border-blue-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-blue-100 dark:bg-blue-800/50 rounded-lg text-blue-600 dark:text-blue-400">
            <Wallet className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">收入与资产</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="本人职业收入" value={consumptionAbility.personalIncome} />
          <InfoItem label="配偶职业收入" value={consumptionAbility.spouseIncome} />
          <InfoItem label="花钱决策人" value={consumptionAbility.decisionMaker} />
          <InfoItem label="保险金额" value={consumptionAbility.insuranceAmount} />
          <InfoItem label="理财金额" value={consumptionAbility.investmentAmount} />
        </div>
      </div>

      {/* In-Store Consumption */}
      <div className="bg-emerald-50/50 dark:bg-emerald-900/10 rounded-xl p-4 border border-emerald-100 dark:border-emerald-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-emerald-100 dark:bg-emerald-800/50 rounded-lg text-emerald-600 dark:text-emerald-400">
            <ShoppingBag className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">店内消费</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="单次消费金额" value={consumptionAbility.inStoreSingleConsumption} />
          <InfoItem label="年度消费金额" value={consumptionAbility.inStoreAnnualConsumption} />
          <InfoItem label="近三个月消费" value={consumptionAbility.inStoreRecent3Months} />
          <InfoItem label="储值卡余额" value={consumptionAbility.inStoreCardBalance} />
        </div>
      </div>

      {/* Out-of-Store & Large Consumption */}
      <div className="bg-purple-50/50 dark:bg-purple-900/10 rounded-xl p-4 border border-purple-100 dark:border-purple-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-purple-100 dark:bg-purple-800/50 rounded-lg text-purple-600 dark:text-purple-400">
            <Gem className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">店外及大额消费</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="店外单次消费" value={consumptionAbility.outStoreSingleConsumption} />
          <InfoItem label="店外年度消费" value={consumptionAbility.outStoreAnnualConsumption} />
          <InfoItem label="店外近三个月" value={consumptionAbility.outStoreRecent3Months} />
          <InfoItem label="店外储值卡余额" value={consumptionAbility.outStoreCardBalance} />
          <InfoItem label="单次奢侈品金额" value={consumptionAbility.luxuryConsumption} />
          <InfoItem label="购车金额" value={consumptionAbility.carPurchase} />
          <InfoItem label="购房金额" value={consumptionAbility.housePurchase} />
          <InfoItem label="其他大额消费" value={consumptionAbility.otherLargeConsumption} />
        </div>
      </div>

      {/* Health Consumption */}
      <div className="bg-rose-50/50 dark:bg-rose-900/10 rounded-xl p-4 border border-rose-100 dark:border-rose-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-rose-100 dark:bg-rose-800/50 rounded-lg text-rose-600 dark:text-rose-400">
            <Heart className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">健康相关消费</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="保健品效果/花费" value={consumptionAbility.healthSupplements} />
          <InfoItem label="大健康项目及花费" value={consumptionAbility.healthProjects} />
          <InfoItem label="大健康治疗机构" value={consumptionAbility.healthInstitutions} />
          <InfoItem label="医美项目及花费" value={consumptionAbility.medicalAesthetics} />
          <InfoItem label="私密项目及花费" value={consumptionAbility.privateProjects} />
          <InfoItem label="体检消费/机构" value={consumptionAbility.physicalExam} />
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const CustomerRelationsCard = ({ title = "客户关系与服务记录", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Store Loyalty */}
      <div className="bg-amber-50/50 dark:bg-amber-900/10 rounded-xl p-4 border border-amber-100 dark:border-amber-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-amber-100 dark:bg-amber-800/50 rounded-lg text-amber-600 dark:text-amber-400">
            <Calendar className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">在店情况</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="在店年限" value={customerRelations.yearsInStore} />
          <InfoItem label="到店频次" value={customerRelations.visitFrequency} />
          <InfoItem label="年度消费总额" value={customerRelations.annualTotalConsumption} />
          <InfoItem label="转介绍情况" value={customerRelations.referralStatus} />
        </div>
      </div>

      {/* Trust & Satisfaction */}
      <div className="bg-indigo-50/50 dark:bg-indigo-900/10 rounded-xl p-4 border border-indigo-100 dark:border-indigo-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-indigo-100 dark:bg-indigo-800/50 rounded-lg text-indigo-600 dark:text-indigo-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">信任与满意度</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="店铺最信任的人" value={customerRelations.mostTrustedPerson} />
          <InfoItem label="项目效果满意度" value={customerRelations.projectSatisfaction} />
          <InfoItem label="隐私交流情况" value={customerRelations.privacyCommunication} />
          <InfoItem label="是否了解客户收入" value={customerRelations.knowsIncome} />
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const EducationRecordsCard = ({ title = "教育铺垫记录", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm whitespace-nowrap">
        <thead>
          <tr className="text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-700/50">
            <th className="pb-2 font-medium">次数</th>
            <th className="pb-2 font-medium">时间</th>
            <th className="pb-2 font-medium">铺垫内容</th>
            <th className="pb-2 font-medium">结果反馈</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
          {educationRecords.map((record) => (
            <tr key={record.id} className="text-slate-900 dark:text-slate-100">
              <td className="py-3">{record.round}</td>
              <td className="py-3">{record.time}</td>
              <td className="py-3">{record.content}</td>
              <td className="py-3">{record.feedback}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </InnerCardWrapper>
);

export const PrecautionsCard = ({ title = "注意事项", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState(precautions);

  const handleSave = () => {
    setIsEditing(false);
  };

  const handleEditClick = () => {
    if (context === 'management') {
      if (onEdit) onEdit();
    } else {
      setIsEditing(!isEditing);
    }
  };

  return (
    <InnerCardWrapper 
      title={title} 
      onEdit={handleEditClick} 
      hideHeader={hideHeader}
      showEdit={true}
    >
      <div className="bg-orange-50/50 dark:bg-orange-900/10 rounded-xl p-4 border border-orange-100 dark:border-orange-800/30">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-orange-100 dark:bg-orange-800/50 rounded-lg text-orange-600 dark:text-orange-400">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">服务注意事项</h4>
          </div>
          <div className="flex items-center space-x-2">
            {hideHeader && context === 'workbench' && (
              <button 
                onClick={() => setIsEditing(!isEditing)}
                className="p-1 text-orange-400 hover:text-orange-600 transition-colors"
                title="编辑注意事项"
              >
                <Edit className="w-3.5 h-3.5" />
              </button>
            )}
            {isEditing && (
              <button 
                onClick={handleSave}
                className="px-3 py-1 bg-orange-500 text-white text-[10px] font-bold rounded-lg hover:bg-orange-600 transition-colors shadow-sm"
              >
                保存
              </button>
            )}
          </div>
        </div>
        
        {isEditing ? (
          <div className="space-y-3">
            {[
              { id: 'consumptionHabits', label: '消费习惯' },
              { id: 'mostCareAbout', label: '最在乎的人和事' },
              { id: 'communicationPreferences', label: '沟通喜好' },
              { id: 'communicationTaboos', label: '沟通禁忌' }
            ].map((field) => (
              <div key={field.id} className="space-y-1">
                <label className="text-sm text-slate-500 dark:text-slate-400 font-medium ml-1">{field.label}</label>
                <input 
                  value={formData[field.id as keyof typeof precautions]}
                  onChange={e => setFormData({...formData, [field.id]: e.target.value})}
                  className="w-full bg-white dark:bg-slate-800 border border-orange-200 dark:border-orange-800 rounded-lg px-3 py-1.5 text-sm text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-orange-500/20 transition-all"
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
            <InfoItem label="消费习惯" value={formData.consumptionHabits} />
            <InfoItem label="最在乎的人和事" value={formData.mostCareAbout} />
            <InfoItem label="沟通喜好" value={formData.communicationPreferences} />
            <InfoItem label="沟通禁忌" value={formData.communicationTaboos} />
          </div>
        )}
      </div>
    </InnerCardWrapper>
  );
};

export const ConsultationRecordsCard = ({ title = "综合分析及咨询记录", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="space-y-4">
      <div className="bg-cyan-50/50 dark:bg-cyan-900/10 rounded-xl p-4 border border-cyan-100 dark:border-cyan-800/30">
        <div className="flex items-center space-x-2 mb-4">
          <div className="p-1.5 bg-cyan-100 dark:bg-cyan-800/50 rounded-lg text-cyan-600 dark:text-cyan-400">
            <FileText className="w-4 h-4" />
          </div>
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">分析与建议</h4>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
          <InfoItem label="问题汇总" value={consultationRecords.problemSummary} />
          <InfoItem label="原因分析（观念引导）" value={consultationRecords.causeAnalysis} />
          <InfoItem label="咨询建议（抛方案）" value={consultationRecords.consultationAdvice} />
          <InfoItem label="其他措施及改善结果" value={consultationRecords.otherMeasures} />
          <InfoItem label="功能医学建议" value={consultationRecords.functionalMedicineAdvice} />
        </div>
      </div>
      <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/50 p-3 rounded-xl border border-slate-100 dark:border-slate-700/50">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold text-xs">
            {consultationRecords.consultant.charAt(0)}
          </div>
          <div>
            <div className="text-sm text-slate-500 dark:text-slate-400">咨询顾问</div>
            <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{consultationRecords.consultant}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm text-slate-500 dark:text-slate-400">咨询日期</div>
          <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{consultationRecords.consultationDate}</div>
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const RemarksCard = ({ title = "备注", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="text-sm text-slate-900 dark:text-slate-100 bg-yellow-50/50 dark:bg-yellow-900/10 p-4 rounded-xl border border-yellow-200/50 dark:border-yellow-800/30 leading-relaxed">
      {remarks.content}
    </div>
  </InnerCardWrapper>
);

export const ExecutionDateCard = ({ title = "负责人及执行日期", hideHeader = false, onEdit, context = 'management' }: { title?: string, hideHeader?: boolean, onEdit?: () => void, context?: 'management' | 'workbench' }) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'}>
    <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50">
      <div className="flex items-center space-x-3">
        <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center text-indigo-600 dark:text-indigo-400 font-bold text-sm">
          {executionDate.responsiblePerson.charAt(0)}
        </div>
        <div>
          <div className="text-sm text-slate-500 dark:text-slate-400">负责人</div>
          <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{executionDate.responsiblePerson}</div>
        </div>
      </div>
      <div className="space-y-1 text-right">
        <div>
          <span className="text-sm text-slate-500 dark:text-slate-400 mr-2">执行日期</span>
          <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{executionDate.executionDate}</span>
        </div>
        <div>
          <span className="text-sm text-slate-500 dark:text-slate-400 mr-2">最近更新</span>
          <span className="text-sm text-slate-900 dark:text-slate-100">{executionDate.lastUpdateDate}</span>
        </div>
      </div>
    </div>
  </InnerCardWrapper>
);

export const AIComponentManagementView: React.FC<AIComponentManagementViewProps> = ({ setCurrentPage, isDarkMode, setIsDarkMode }) => {
  const [activeTab, setActiveTab] = useState('cards');
  const [cards, setCards] = useState<CardConfig[]>(initialCards);
  const [layouts, setLayouts] = useState(initialLayouts);
  const [editingCard, setEditingCard] = useState<CardConfig | null>(null);
  
  const [categories, setCategories] = useState<string[]>(['客户基本信息', '团队信息', '资产与服务']);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  
  const [selectedRole, setSelectedRole] = useState('doctor');
  const [cardFilter, setCardFilter] = useState('all');
  
  const [isEditingLayout, setIsEditingLayout] = useState(false);
  const [draftLayouts, setDraftLayouts] = useState(initialLayouts);

  const handleSaveCard = (updatedCard: CardConfig) => {
    setCards(cards.map(c => c.id === updatedCard.id ? updatedCard : c));
    setEditingCard(null);
  };

  const handleCreateCategory = () => {
    if (!newCategoryName.trim() || categories.includes(newCategoryName.trim())) return;
    setCategories([...categories, newCategoryName.trim()]);
    setIsCategoryModalOpen(false);
    setNewCategoryName('');
  };

  const renderCardContent = (card: CardConfig, onEdit?: () => void) => {
    switch (card.type) {
      case 'asset-info': return <AssetCard title={card.title} onEdit={onEdit} />;
      case 'identity-contact': return <IdentityContactCard title={card.title} onEdit={onEdit} />;
      case 'basic-health-data': return <BasicHealthDataCard title={card.title} onEdit={onEdit} />;
      case 'health-status-medical-history': return <HealthStatusMedicalHistoryCard title={card.title} onEdit={onEdit} />;
      case 'physical-exam-status': return <PhysicalExamStatusCard title={card.title} onEdit={onEdit} />;
      case 'lifestyle-habits': return <LifestyleHabitsCard title={card.title} onEdit={onEdit} />;
      case 'psychology-emotion': return <PsychologyEmotionCard title={card.title} onEdit={onEdit} />;
      case 'personal-preferences': return <PersonalPreferencesCard title={card.title} onEdit={onEdit} />;
      case 'health-goals': return <HealthGoalsCard title={card.title} onEdit={onEdit} />;
      case 'consumption-ability': return <ConsumptionAbilityCard title={card.title} onEdit={onEdit} />;
      case 'customer-relations': return <CustomerRelationsCard title={card.title} onEdit={onEdit} />;
      case 'education-records': return <EducationRecordsCard title={card.title} onEdit={onEdit} />;
      case 'precautions': return <PrecautionsCard title={card.title} onEdit={onEdit} />;
      case 'consultation-records': return <ConsultationRecordsCard title={card.title} onEdit={onEdit} />;
      case 'remarks': return <RemarksCard title={card.title} onEdit={onEdit} />;
      case 'execution-date': return <ExecutionDateCard title={card.title} onEdit={onEdit} />;
      default: return null;
    }
  };

  const CardWrapper: React.FC<{ card: CardConfig }> = ({ card }) => {
    return (
      <div className="w-full break-inside-avoid mb-6">
        {renderCardContent(card, () => setEditingCard(card))}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white transition-colors duration-300">AI组件管理</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 transition-colors duration-300">管理和配置系统中的各类AI组件与业务卡片</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input 
              type="text" 
              placeholder="搜索组件..." 
              className="pl-9 pr-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full text-sm focus:ring-2 focus:ring-blue-500 outline-none w-64 text-slate-900 dark:text-white placeholder-slate-400 transition-colors duration-300"
            />
          </div>
          <button className="p-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors duration-300">
            <Filter className="w-4 h-4 text-slate-600 dark:text-slate-300" />
          </button>
        </div>
      </div>
      
      {/* Header Area: Tabs + Action Button */}
      <div className="flex items-center justify-between">
        {/* Tabs */}
        <div className="flex space-x-1 bg-slate-100 dark:bg-slate-800/50 p-1 rounded-xl w-fit">
          <button 
            onClick={() => setActiveTab('cards')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'cards' ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'}`}
          >
            业务卡片库 ({cards.length})
          </button>
          <button 
            onClick={() => setActiveTab('layouts')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'layouts' ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'}`}
          >
            工作台默认布局
          </button>
        </div>

        {activeTab === 'cards' && (
          <button 
            onClick={() => setIsCategoryModalOpen(true)}
            className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4 mr-2" />
            新增分组
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar pb-6 pr-2">
        {activeTab === 'cards' ? (
          <div className="space-y-6">
            {/* Sub-tabs for filtering */}
            <div className="flex space-x-6 border-b border-slate-200 dark:border-slate-700 overflow-x-auto custom-scrollbar">
              <button
                onClick={() => setCardFilter('all')}
                className={`pb-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${cardFilter === 'all' ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'}`}
              >
                全部
              </button>
              <button
                onClick={() => setCardFilter('uncategorized')}
                className={`pb-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${cardFilter === 'uncategorized' ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'}`}
              >
                未分组
              </button>
              {categories.map(cat => (
                <button
                  key={cat}
                  onClick={() => setCardFilter(cat)}
                  className={`pb-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${cardFilter === cat ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'}`}
                >
                  {cat}
                </button>
              ))}
            </div>

            <div className="columns-1 md:columns-2 xl:columns-3 2xl:columns-4 gap-6">
              {cards.filter(c => {
                if (cardFilter === 'all') return true;
                if (cardFilter === 'uncategorized') return !c.category;
                return c.category === cardFilter;
              }).map(card => (
                <CardWrapper key={card.id} card={card} />
              ))}
            </div>
          </div>
        ) : activeTab === 'layouts' ? (
          <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 shadow-sm border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
                <LayoutTemplate className="w-5 h-5 mr-2 text-blue-500" />
                角色默认布局配置
              </h3>
              <div className="flex items-center space-x-4">
                <div className="flex space-x-2">
                  {['doctor', 'consultant', 'sales'].map(role => (
                    <button
                      key={role}
                      onClick={() => setSelectedRole(role)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        selectedRole === role 
                          ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-500/30' 
                          : 'bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'
                      }`}
                    >
                      {role === 'doctor' ? '医生' : role === 'consultant' ? '咨询师' : '销售'}
                    </button>
                  ))}
                </div>
                <div className="h-6 w-px bg-slate-200 dark:bg-slate-700"></div>
                {!isEditingLayout ? (
                  <button 
                    onClick={() => { setIsEditingLayout(true); setDraftLayouts(layouts); }} 
                    className="px-4 py-2 bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400 rounded-lg text-sm font-medium hover:bg-blue-100 dark:hover:bg-blue-500/20 transition-colors flex items-center"
                  >
                    <Edit className="w-4 h-4 mr-1.5" />
                    编辑布局
                  </button>
                ) : (
                  <div className="flex space-x-2">
                    <button 
                      onClick={() => setIsEditingLayout(false)} 
                      className="px-4 py-2 bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 rounded-lg text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                    >
                      取消
                    </button>
                    <button 
                      onClick={() => { setLayouts(draftLayouts); setIsEditingLayout(false); }} 
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors flex items-center"
                    >
                      <Save className="w-4 h-4 mr-1.5" />
                      保存
                    </button>
                  </div>
                )}
              </div>
            </div>
            
            <div className="space-y-4">
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                {isEditingLayout 
                  ? `正在编辑 ${selectedRole === 'doctor' ? '医生' : selectedRole === 'consultant' ? '咨询师' : '销售'} 角色的默认布局，点击卡片进行勾选或取消。`
                  : `配置 ${selectedRole === 'doctor' ? '医生' : selectedRole === 'consultant' ? '咨询师' : '销售'} 角色在“我的AI工作台”中默认展示的卡片。`
                }
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {cards.map(card => {
                  const activeLayouts = isEditingLayout ? draftLayouts : layouts;
                  const isSelected = activeLayouts[selectedRole as keyof typeof activeLayouts].includes(card.id);
                  return (
                    <div 
                      key={card.id}
                      onClick={() => {
                        if (!isEditingLayout) return;
                        const currentLayout = draftLayouts[selectedRole as keyof typeof draftLayouts];
                        const newLayout = isSelected 
                          ? currentLayout.filter(id => id !== card.id)
                          : [...currentLayout, card.id];
                        setDraftLayouts({ ...draftLayouts, [selectedRole]: newLayout });
                      }}
                      className={`p-4 rounded-xl border-2 transition-all ${isEditingLayout ? 'cursor-pointer' : 'cursor-default'} ${
                        isSelected 
                          ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-500/5' 
                          : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800'
                      } ${isEditingLayout && !isSelected ? 'hover:border-blue-300 dark:hover:border-blue-700' : ''}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className={`font-medium ${isSelected ? 'text-blue-700 dark:text-blue-400' : 'text-slate-800 dark:text-slate-200'}`}>{card.title}</span>
                        <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-colors ${
                          isSelected ? 'border-blue-500 bg-blue-500' : 'border-slate-300 dark:border-slate-600'
                        } ${!isEditingLayout && !isSelected ? 'opacity-50' : ''}`}>
                          {isSelected && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                        </div>
                      </div>
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {card.category || '未分组'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center bg-white/40 dark:bg-slate-900/40 rounded-3xl border border-dashed border-slate-200 dark:border-slate-700">
            <div className="w-16 h-16 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center text-slate-400 mb-4">
              <MoreHorizontal className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">模块开发中</h3>
            <p className="text-sm text-slate-500 dark:text-slate-400">该功能模块正在紧张开发中，敬请期待。</p>
          </div>
        )}
      </div>

      {/* Edit Card Modal */}
      {editingCard && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-700/50">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">编辑卡片</h3>
              <button onClick={() => setEditingCard(null)} className="text-slate-400 hover:text-slate-500">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">卡片名称</label>
                <input 
                  type="text" 
                  value={editingCard.title}
                  onChange={e => setEditingCard({ ...editingCard, title: e.target.value })}
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">所属分组</label>
                <select
                  value={editingCard.category || ''}
                  onChange={e => setEditingCard({ ...editingCard, category: e.target.value })}
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                >
                  <option value="">未分组</option>
                  {categories.map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">关联URL地址 (可选)</label>
                <input 
                  type="text" 
                  value={editingCard.url || ''}
                  onChange={e => setEditingCard({ ...editingCard, url: e.target.value })}
                  placeholder="https://"
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                />
              </div>
              <div className="bg-blue-50 dark:bg-blue-500/10 p-4 rounded-lg">
                <p className="text-xs text-blue-600 dark:text-blue-400">提示：卡片内的数据内容为系统自动回传，不可手动更改。</p>
              </div>
            </div>
            <div className="flex items-center justify-end p-6 border-t border-slate-100 dark:border-slate-700/50 space-x-3">
              <button onClick={() => setEditingCard(null)} className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg transition-colors">
                取消
              </button>
              <button onClick={() => handleSaveCard(editingCard)} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center">
                <Save className="w-4 h-4 mr-2" />
                保存修改
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Category Modal */}
      {isCategoryModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl w-full max-w-md overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-700/50">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">新增分组</h3>
              <button onClick={() => setIsCategoryModalOpen(false)} className="text-slate-400 hover:text-slate-500">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">分组名称</label>
                <input 
                  type="text" 
                  value={newCategoryName}
                  onChange={e => setNewCategoryName(e.target.value)}
                  placeholder="例如：客户基本信息"
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                />
              </div>
            </div>
            <div className="flex items-center justify-end p-6 border-t border-slate-100 dark:border-slate-700/50 space-x-3">
              <button onClick={() => setIsCategoryModalOpen(false)} className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg transition-colors">
                取消
              </button>
              <button 
                onClick={handleCreateCategory} 
                disabled={!newCategoryName.trim()}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center"
              >
                <Save className="w-4 h-4 mr-2" />
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
