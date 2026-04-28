import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Calendar,
  CheckCircle2,
  Clock,
  Coffee,
  Edit,
  FileText,
  Gem,
  Heart,
  Link as LinkIcon,
  MessageSquare,
  Moon,
  Package,
  ShieldCheck,
  ShoppingBag,
  Star,
  Target,
  TrendingUp,
  Unlock,
  Utensils,
  Wallet,
} from 'lucide-react';
import {
  assetInfo,
  basicHealthData,
  consultationRecords,
  consumptionAbility,
  customerRelations,
  educationRecords,
  executionDate,
  healthGoals,
  healthStatusMedicalHistory,
  identityContactInfo,
  lifestyleHabits,
  personalPreferences,
  physicalExamStatus,
  precautions,
  psychologyEmotion,
  remarks,
} from './mockData';

type CardContext = 'management' | 'workbench';
type CardRuntimeStatus = 'loading' | 'ready' | 'empty' | 'error';

type CardRuntimeProps = {
  title?: string;
  hideHeader?: boolean;
  onEdit?: () => void;
  onRuntimeSave?: (payload: Record<string, unknown>) => Promise<void> | void;
  context?: CardContext;
  runtimeData?: unknown;
  runtimeDataByCardId?: Record<string, unknown>;
  runtimeStatus?: CardRuntimeStatus;
  runtimeError?: string;
};

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

type RuntimeLookupContextValue = {
  context: CardContext;
  runtimeData?: unknown;
  runtimeStatus?: CardRuntimeStatus;
};

const RuntimeLookupContext = createContext<RuntimeLookupContextValue>({
  context: 'management',
  runtimeData: undefined,
  runtimeStatus: undefined,
});

const EMPTY_PLACEHOLDER = '-';

const LABEL_KEY_MAP: Record<string, string[]> = {
  '客户姓名': ['customerName'],
  '性别': ['gender'],
  '出生年月日（阳历）': ['birthday'],
  '年龄': ['age'],
  '血型': ['bloodType'],
  '身份证号': ['idCardObfuscated', 'idCard'],
  '联系电话': ['phone'],
  '微信': ['wechat'],
  '家庭地址': ['homeAddress'],
  '婚姻状况': ['marriageStatus'],
  '子女情况': ['childrenInfo'],
  '本人职业': ['selfOccupation'],
  '配偶职业': ['spouseOccupation'],
  '身高 (CM)': ['heightCm'],
  '体重 (KG)': ['weightKg'],
  'BMI': ['bmi'],
  '血压 (MMHG)': ['bloodPressure'],
  '血糖 (MMOL/L)': ['bloodGlucose'],
  '血脂 (总胆固醇/甘油三酯等)': ['bloodLipid'],
  '尿酸 (MMOL/L)': ['uricAcid'],
  '心率 (次/分)': ['heartRate'],
  '最近一次测量日期': ['latestMeasurementDate'],
  '月经是否正常': ['menstrualNormal'],
  '经期描述/问题': ['menstrualIssue'],
  '孕产史': ['pregnancyHistory'],
  '私密项目需求/记录': ['intimateNeeds'],
  '功能医学检测结果（如有）': ['functionalMedicineResult'],
  '既往史（慢性病/手术/住院）': ['pastHistory'],
  '当前用药（药名/剂量/频次）': ['currentMedication'],
  '过敏史（药物/食物/其他）': ['allergyHistory'],
  '过敏性疾病（鼻炎/哮喘/湿疹等）': ['allergicDiseases'],
  '家族史（直系亲属疾病）': ['familyHistory'],
  '遗传病史': ['geneticHistory'],
  '近期不适症状（参考问卷 Q5）': ['recentSymptoms'],
  '身体疼痛部位': ['painAreas'],
  '体检频率': ['physicalExamFrequency'],
  '最近一次体检时间': ['latestPhysicalExamTime'],
  '体检机构': ['physicalExamInstitution'],
  '体检套餐': ['physicalExamPackage'],
  '主要异常指标（乳腺/甲状腺/肺部/其他）': ['keyAbnormalIndicators'],
  '医生建议': ['doctorAdvice'],
  '运动频率': ['exerciseFrequency'],
  '运动时长': ['exerciseDuration'],
  '运动类型': ['exerciseType'],
  '工作性质': ['workNature'],
  '久坐时长': ['sedentaryDuration'],
  '饮食结构': ['dietStructure'],
  '蔬菜水果摄入': ['fruitVegetableIntake'],
  '早餐习惯': ['breakfastHabit'],
  '营养补充剂': ['supplements'],
  '饮食口味偏好': ['tastePreference'],
  '饮水习惯': ['waterIntakeHabit'],
  '含糖饮料/零食': ['sugarySnackHabit'],
  '作息规律': ['scheduleRegularity'],
  '睡眠时长': ['sleepDuration'],
  '睡眠质量问题': ['sleepQualityIssues'],
  '非工作电子设备': ['leisureScreenTime'],
  '吸烟': ['smokingPerDay'],
  '饮酒': ['drinkingPerWeek'],
  '咖啡/浓茶': ['coffeeTeaPerDay'],
  '排便情况': ['bowelHabit'],
  '记忆力/精气神': ['memoryEnergySelfAssessment'],
  '近三个月整体健康感受': ['overallHealthFeeling'],
  '常见情绪': ['commonEmotions'],
  '情绪对健康影响程度': ['emotionImpactLevel'],
  '压力应对方式': ['stressCopingWays'],
  '希望获得的情绪支持': ['expectedEmotionSupport'],
  '对服务者情绪支持能力的期望': ['expectationForServiceSupport'],
  '闲暇偏好': ['leisurePreference'],
  '放松方式': ['relaxWays'],
  '工作环境偏好': ['workEnvironmentPreference'],
  '工作节奏偏好': ['workPacePreference'],
  '团队角色偏好': ['teamRolePreference'],
  '获取健康知识方式': ['healthKnowledgePreference'],
  '激励方式偏好': ['motivationPreference'],
  '做得好的 1-2 件事': ['goodHealthManagementCases'],
  '有助于健康的能力': ['healthHelpfulAbilities'],
  '过去一年养成的习惯': ['healthyHabitsInPastYear'],
  '擅长指导他人的方面': ['goodAtGuidingOthers'],
  '克服过的最大挑战': ['biggestHealthChallenge'],
  '最需要外界支持的方面': ['mostNeededExternalSupport'],
  '最大挑战/痛点': ['biggestChallenges'],
  '核心影响因素': ['coreInfluencingFactors'],
  '迫切想解决的问题': ['urgentIssue'],
  '希望实现的目标': ['expectedGoal'],
  '美丽需求': ['beautyNeeds'],
  '情感需求': ['emotionalNeeds'],
  '花钱动机': ['spendingMotivation'],
  '本人职业收入': ['selfIncome'],
  '配偶职业收入': ['spouseIncome'],
  '花钱决策人': ['spendingDecisionMaker'],
  '保险金额': ['insuranceAmount'],
  '理财金额': ['wealthManagementAmount'],
  '单次消费金额': ['inStoreSingleAmount'],
  '年度消费金额': ['inStoreYearAmount'],
  '近三个月消费': ['inStoreRecentThreeMonthsAmount'],
  '储值卡余额': ['inStoreStoredCardBalance'],
  '店外单次消费': ['outStoreSingleAmount'],
  '店外年度消费': ['outStoreYearAmount'],
  '店外近三个月': ['outStoreRecentThreeMonthsAmount'],
  '店外储值卡余额': ['outStoreStoredCardBalance'],
  '单次奢侈品金额': ['luxurySingleAmount'],
  '购车金额': ['carPurchaseAmount'],
  '购房金额': ['housePurchaseAmount'],
  '其他大额消费': ['otherLargeConsumption'],
  '保健品效果/花费': ['healthProductsCostEffect'],
  '大健康项目及花费': ['healthProjectCost'],
  '大健康治疗机构': ['healthTreatmentInstitution'],
  '医美项目及花费': ['cosmeticProjectCost'],
  '私密项目及花费': ['intimateProjectCost'],
  '体检消费/机构': ['physicalExamCostInstitution'],
  '在店年限': ['yearsInStore'],
  '到店频次': ['visitFrequency'],
  '年度消费总额': ['inStoreYearTotalAmount'],
  '转介绍情况': ['referralStatus'],
  '店铺最信任的人': ['mostTrustedPerson'],
  '项目效果满意度': ['projectSatisfaction'],
  '隐私交流情况': ['privacyCommunication'],
  '是否了解客户收入': ['knowsCustomerIncome'],
  '消费习惯': ['consumptionHabit'],
  '最在乎的人和事': ['mostCareAbout'],
  '沟通喜好': ['communicationPreference'],
  '沟通禁忌': ['communicationTaboo'],
  '问题汇总': ['issueSummary'],
  '原因分析（观念引导）': ['causeAnalysis'],
  '咨询建议（抛方案）': ['consultationAdvice'],
  '其他措施及改善结果': ['otherMeasuresAndResults'],
  '功能医学建议': ['functionalMedicineAdvice'],
  '咨询顾问': ['consultant'],
  '咨询日期': ['consultationDate'],
  '负责人': ['responsiblePerson', 'ownerName'],
  '执行日期': ['executionDate'],
  '最近更新': ['lastUpdateDate'],
  '备注': ['content', 'remark', 'remarks'],
  '医疗项目金总余额': ['totalBalance'],
  '可用医疗项目金余额': ['availableBalance'],
  '已冻结医疗项目金': ['frozenBalance'],
  '待收回医疗项目金余额': ['pendingRecovery'],
  '消耗医疗项目金余额': ['consumedBalance'],
  '医疗项目剩余数量': ['remainingQuantity'],
};

const normalizeKey = (value: string) => value.replace(/[（）()：:\s/_\-·]/g, '').toLowerCase();

const toObjectRecord = (value: unknown): Record<string, unknown> => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
};

const isEmptyValue = (value: unknown): boolean => {
  if (value === null || value === undefined || value === '') {
    return true;
  }
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  if (typeof value === 'object') {
    return Object.keys(value as Record<string, unknown>).length === 0;
  }
  return false;
};

const readValueByPath = (payload: Record<string, unknown>, path: string): unknown => {
  const keys = path.split('.');
  let current: unknown = payload;
  for (const key of keys) {
    if (!current || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return current;
};

const toDisplayText = (value: unknown): string => {
  if (isEmptyValue(value)) {
    return EMPTY_PLACEHOLDER;
  }
  if (Array.isArray(value)) {
    const values = value.map((item) => toDisplayText(item)).filter((item) => item !== EMPTY_PLACEHOLDER);
    return values.length > 0 ? values.join('、') : EMPTY_PLACEHOLDER;
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
};

const pickRuntimeResultObject = (runtimeData: unknown): Record<string, unknown> => {
  const root = toObjectRecord(runtimeData);
  const rootResult = toObjectRecord(root.result);
  if (Object.keys(rootResult).length > 0) {
    return rootResult;
  }

  const rootData = toObjectRecord(root.data);
  const rootDataResult = toObjectRecord(rootData.result);
  if (Object.keys(rootDataResult).length > 0) {
    return rootDataResult;
  }
  if (Object.keys(rootData).length > 0) {
    return rootData;
  }
  return root;
};

const pickValueByCandidates = (payload: Record<string, unknown>, candidates: string[]): unknown => {
  for (const key of candidates) {
    const value = key.includes('.') ? readValueByPath(payload, key) : payload[key];
    if (!isEmptyValue(value)) {
      return value;
    }
  }
  return undefined;
};

const resolveRuntimeValueByLabel = (runtimeData: unknown, label: string): unknown => {
  const payload = pickRuntimeResultObject(runtimeData);
  if (Object.keys(payload).length === 0) {
    return undefined;
  }

  if (!isEmptyValue(payload[label])) {
    return payload[label];
  }

  const labelCandidates = LABEL_KEY_MAP[label];
  if (Array.isArray(labelCandidates)) {
    const mapped = pickValueByCandidates(payload, labelCandidates);
    if (mapped !== undefined) {
      return mapped;
    }
  }

  const targetLabel = normalizeKey(label);
  for (const [key, value] of Object.entries(payload)) {
    const normalized = normalizeKey(key);
    if ((normalized === targetLabel || normalized.includes(targetLabel) || targetLabel.includes(normalized)) && !isEmptyValue(value)) {
      return value;
    }
  }

  return undefined;
};

const useRuntimeFieldValue = (label: string, fallbackValue: unknown, candidates: string[] = []): string => {
  const runtimeContext = useContext(RuntimeLookupContext);
  const displayValue = useMemo(() => {
    if (runtimeContext.context !== 'workbench') {
      return fallbackValue;
    }
    if (runtimeContext.runtimeStatus !== 'ready') {
      return fallbackValue;
    }

    const payload = pickRuntimeResultObject(runtimeContext.runtimeData);
    const runtimeValue = candidates.length > 0
      ? pickValueByCandidates(payload, candidates)
      : resolveRuntimeValueByLabel(runtimeContext.runtimeData, label);
    if (runtimeValue !== undefined) {
      return runtimeValue;
    }
    return EMPTY_PLACEHOLDER;
  }, [candidates, fallbackValue, label, runtimeContext.context, runtimeContext.runtimeData, runtimeContext.runtimeStatus]);

  return toDisplayText(displayValue);
};

type NormalizedEducationRecord = {
  id: string;
  round: unknown;
  time: unknown;
  content: unknown;
  feedback: unknown;
};

const extractEducationContentByRound = (record: Record<string, unknown>, round: unknown): unknown => {
  const directContent = record.content ?? record.text ?? record.summary ?? record.educationContent;
  if (!isEmptyValue(directContent)) {
    return directContent;
  }

  const normalizedRound = normalizeKey(toDisplayText(round));
  if (normalizedRound.includes('第1次') || normalizedRound.endsWith('1次') || normalizedRound === '1') {
    if (!isEmptyValue(record.firstTime)) {
      return record.firstTime;
    }
  }
  if (normalizedRound.includes('第2次') || normalizedRound.endsWith('2次') || normalizedRound === '2') {
    if (!isEmptyValue(record.secondTime)) {
      return record.secondTime;
    }
  }
  if (normalizedRound.includes('第3次') || normalizedRound.endsWith('3次') || normalizedRound === '3') {
    if (!isEmptyValue(record.thirdTime)) {
      return record.thirdTime;
    }
  }
  if (normalizedRound.includes('项目') || normalizedRound.includes('价格') || normalizedRound.includes('铺垫')) {
    if (!isEmptyValue(record.projectPricePrepared)) {
      return record.projectPricePrepared;
    }
  }

  return record.firstTime ?? record.secondTime ?? record.thirdTime ?? record.projectPricePrepared;
};

const resolveEducationRound = (record: Record<string, unknown>): unknown => {
  const explicitRound = record.round ?? record.times ?? record.sequence ?? record.index ?? record.count;
  if (!isEmptyValue(explicitRound)) {
    return explicitRound;
  }
  if (!isEmptyValue(record.firstTime)) {
    return '第1次';
  }
  if (!isEmptyValue(record.secondTime)) {
    return '第2次';
  }
  if (!isEmptyValue(record.thirdTime)) {
    return '第3次';
  }
  if (!isEmptyValue(record.projectPricePrepared)) {
    return '项目及价格是否铺垫';
  }
  return undefined;
};

const normalizeEducationRecords = (value: unknown): NormalizedEducationRecord[] => {
  const sourceRows: unknown[] = Array.isArray(value)
    ? value
    : isEmptyValue(value)
      ? []
      : [value];

  if (sourceRows.length === 0) {
    return [];
  }

  return sourceRows
    .map((item, index) => {
      const record = toObjectRecord(item);
      const id = toDisplayText(record.id ?? record.recordId ?? index + 1);
      const round = resolveEducationRound(record);
      return {
        id,
        round,
        time: record.time ?? record.date ?? record.createdAt ?? record.createdTime ?? record.visitTime,
        content: extractEducationContentByRound(record, round),
        feedback: record.feedback ?? record.result ?? record.response ?? record.effect,
      };
    })
    .filter((item) => Boolean(item.id));
};

type PrecautionsFormData = typeof precautions;

const EMPTY_PRECAUTIONS_FORM: PrecautionsFormData = {
  consumptionHabits: '',
  mostCareAbout: '',
  communicationPreferences: '',
  communicationTaboos: '',
};

const toInputText = (value: unknown): string => {
  if (isEmptyValue(value)) {
    return '';
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => toInputText(item))
      .filter(Boolean)
      .join('、');
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
};

const buildPrecautionsFormData = (
  runtimeData: unknown,
  fallback: PrecautionsFormData,
): PrecautionsFormData => {
  const payload = pickRuntimeResultObject(runtimeData);
  if (Object.keys(payload).length === 0) {
    return { ...fallback };
  }

  const resolveField = (label: string, candidates: string[], fallbackValue: string) => {
    const candidateValue = pickValueByCandidates(payload, candidates);
    if (candidateValue !== undefined) {
      const text = toInputText(candidateValue);
      if (text) {
        return text;
      }
    }

    const labelValue = resolveRuntimeValueByLabel(payload, label);
    if (labelValue !== undefined) {
      const text = toInputText(labelValue);
      if (text) {
        return text;
      }
    }

    return fallbackValue;
  };

  return {
    consumptionHabits: resolveField('消费习惯', ['consumptionHabit', 'consumptionHabits'], fallback.consumptionHabits),
    mostCareAbout: resolveField('最在乎的人和事', ['mostCareAbout'], fallback.mostCareAbout),
    communicationPreferences: resolveField(
      '沟通喜好',
      ['communicationPreference', 'communicationPreferences'],
      fallback.communicationPreferences,
    ),
    communicationTaboos: resolveField(
      '沟通禁忌',
      ['communicationTaboo', 'communicationTaboos'],
      fallback.communicationTaboos,
    ),
  };
};

const RuntimeState = ({ status, error }: { status: CardRuntimeStatus; error?: string }) => {
  if (status === 'loading') {
    return <div className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">数据加载中...</div>;
  }

  if (status === 'error') {
    return (
      <div className="py-10 text-center text-sm text-rose-500 dark:text-rose-400">
        {error || '接口请求失败'}
      </div>
    );
  }

  return (
    <div className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
      {error || '暂无数据'}
    </div>
  );
};

const InnerCardWrapper = ({
  title,
  url,
  hideHeader,
  onEdit,
  showEdit = true,
  context = 'management',
  runtimeData,
  runtimeStatus,
  runtimeError,
  children,
}: {
  title: string;
  url?: string;
  hideHeader?: boolean;
  onEdit?: () => void;
  showEdit?: boolean;
  context?: CardContext;
  runtimeData?: unknown;
  runtimeStatus?: CardRuntimeStatus;
  runtimeError?: string;
  children: React.ReactNode;
}) => {
  const isWorkbench = context === 'workbench';
  const resolvedStatus: CardRuntimeStatus = runtimeStatus ?? 'loading';
  const content = isWorkbench && resolvedStatus !== 'ready'
    ? <RuntimeState status={resolvedStatus} error={runtimeError} />
    : children;

  if (hideHeader) {
    return (
      <RuntimeLookupContext.Provider value={{ context, runtimeData, runtimeStatus: resolvedStatus }}>
        <div className="h-full">{content}</div>
      </RuntimeLookupContext.Provider>
    );
  }
  return (
    <RuntimeLookupContext.Provider value={{ context, runtimeData, runtimeStatus: resolvedStatus }}>
      <div className="bg-gradient-to-b from-white to-slate-50/30 dark:from-slate-800 dark:to-slate-800/50 rounded-2xl p-5 shadow-[0_2px_10px_-3px_rgba(0,0,0,0.05)] hover:shadow-[0_8px_20px_rgba(0,0,0,0.08)] border border-slate-200/80 dark:border-slate-700/80 h-full transition-all duration-300 relative overflow-hidden">
        <CardHeader title={title} url={url} onEdit={onEdit} showEdit={showEdit} />
        {content}
      </div>
    </RuntimeLookupContext.Provider>
  );
};

const InfoItem = ({ label, value }: { label: string, value: unknown }) => {
  const runtimeContext = useContext(RuntimeLookupContext);
  const displayValue = useMemo(() => {
    if (runtimeContext.context !== 'workbench' || runtimeContext.runtimeStatus !== 'ready') {
      return value;
    }
    const runtimeValue = resolveRuntimeValueByLabel(runtimeContext.runtimeData, label);
    if (runtimeValue !== undefined) {
      return runtimeValue;
    }
    return EMPTY_PLACEHOLDER;
  }, [label, runtimeContext.context, runtimeContext.runtimeData, runtimeContext.runtimeStatus, value]);

  const text = toDisplayText(displayValue);
  return (
    <div className="flex flex-col space-y-1">
      <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
      <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate" title={text}>{text}</span>
    </div>
  );
};

export const AssetCard = ({ title = "客户资产概览", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => {
  const totalBalance = useRuntimeFieldValue('医疗项目金总余额', assetInfo.totalBalance, ['totalBalance', 'assetInfo.totalBalance', 'balance.total']);
  const availableBalance = useRuntimeFieldValue('可用医疗项目金余额', assetInfo.availableBalance, ['availableBalance', 'assetInfo.availableBalance', 'balance.available']);
  const frozenBalance = useRuntimeFieldValue('已冻结医疗项目金', assetInfo.frozenBalance, ['frozenBalance', 'assetInfo.frozenBalance', 'balance.frozen']);
  const pendingRecovery = useRuntimeFieldValue('待收回医疗项目金余额', assetInfo.pendingRecovery, ['pendingRecovery', 'assetInfo.pendingRecovery', 'balance.pendingRecovery']);
  const consumedBalance = useRuntimeFieldValue('消耗医疗项目金余额', assetInfo.consumedBalance, ['consumedBalance', 'assetInfo.consumedBalance', 'balance.consumed']);
  const remainingQuantity = useRuntimeFieldValue('医疗项目剩余数量', assetInfo.remainingQuantity, ['remainingQuantity', 'assetInfo.remainingQuantity', 'quantity.remaining']);

  return (
    <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{totalBalance}</div>
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
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{availableBalance}</div>
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
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{frozenBalance}</div>
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
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{pendingRecovery}</div>
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
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{consumedBalance}</div>
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
          <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-1 relative z-10">{remainingQuantity}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400 relative z-10">当前可用的医疗项目总数</div>
        </div>
      </div>
    </InnerCardWrapper>
  );
};

export const IdentityContactCard = ({ title = "身份与联系信息", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const BasicHealthDataCard = ({
  title = "健康基础数据",
  hideHeader = false,
  onEdit,
  context = 'management',
  runtimeData,
  runtimeDataByCardId,
  runtimeStatus,
  runtimeError,
}: CardRuntimeProps) => {
  const genderText = useMemo(() => {
    if (context === 'workbench') {
      const identityCardPayload = pickRuntimeResultObject(runtimeDataByCardId?.['identity-contact']);
      const identityGender = pickValueByCandidates(identityCardPayload, ['gender', 'sex']);
      const identityGenderText = toInputText(identityGender).trim();
      if (identityGenderText) {
        return identityGenderText;
      }

      const selfPayload = pickRuntimeResultObject(runtimeData);
      const selfGender = pickValueByCandidates(selfPayload, ['gender', 'sex']);
      const selfGenderText = toInputText(selfGender).trim();
      if (selfGenderText) {
        return selfGenderText;
      }
    }

    return String(identityContactInfo.gender ?? '');
  }, [context, runtimeData, runtimeDataByCardId]);

  const normalizedGender = genderText.trim().toLowerCase();
  const isMale = (
    normalizedGender === '男' ||
    normalizedGender === '男性' ||
    normalizedGender === 'male' ||
    normalizedGender === 'm' ||
    normalizedGender === 'false' ||
    normalizedGender === '0' ||
    normalizedGender === '1' ||
    normalizedGender.includes('男') ||
    normalizedGender.includes('male')
  );
  const isFemale = (
    normalizedGender === '女' ||
    normalizedGender === '女性' ||
    normalizedGender === 'female' ||
    normalizedGender === 'f' ||
    normalizedGender === '2' ||
    normalizedGender.includes('女') ||
    normalizedGender.includes('female')
  );
  const showFemaleHealth = isFemale && !isMale;

  return (
    <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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
          {showFemaleHealth && (
            <div className="md:border-l md:pl-6 border-slate-100 dark:border-slate-700/50">
              <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200 mb-3">女性健康</h4>
              <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-y-4 gap-x-4">
                <InfoItem label="月经是否正常" value={basicHealthData.menstruationNormal} />
                <InfoItem label="经期描述/问题" value={basicHealthData.menstrualDescription} />
                <InfoItem label="孕产史" value={basicHealthData.pregnancyHistory} />
                <InfoItem label="私密项目需求/记录" value={basicHealthData.privateProjectNeeds} />
              </div>
            </div>
          )}
          <div className="md:border-l md:pl-6 pt-4 border-slate-100 dark:border-slate-700/50">
            <InfoItem label="功能医学检测结果（如有）" value={basicHealthData.functionalMedicineResults} />
          </div>
        </div>
      </div>
    </InnerCardWrapper>
  );
};

export const HealthStatusMedicalHistoryCard = ({ title = "健康状况与医疗史", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const PhysicalExamStatusCard = ({ title = "体检情况", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const LifestyleHabitsCard = ({ title = "生活方式与习惯", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const PsychologyEmotionCard = ({ title = "心理与情绪", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const PersonalPreferencesCard = ({ title = "个人喜好与优势", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const HealthGoalsCard = ({ title = "健康目标与核心痛点", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const ConsumptionAbilityCard = ({ title = "消费能力与背景", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const CustomerRelationsCard = ({ title = "客户关系与服务记录", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => (
  <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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

export const EducationRecordsCard = ({ title = "教育铺垫记录", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => {
  const runtimeDataRef = runtimeData;
  const runtimeStatusRef = runtimeStatus;
  const tableRows = useMemo(() => {
    if (context !== 'workbench' || (runtimeStatusRef ?? 'loading') !== 'ready') {
      return educationRecords.map((record) => ({
        id: String(record.id),
        round: record.round,
        time: record.time,
        content: record.content,
        feedback: record.feedback,
      }));
    }

    const payload = pickRuntimeResultObject(runtimeDataRef);
    const runtimeRowsRaw = pickValueByCandidates(payload, [
      'educationRecords',
      'educationPreparationRecords',
      'educationPreparationRecordList',
      'records',
      'rows',
      'list',
      'items',
      'educationRecordList',
      'result',
    ]);
    const normalized = normalizeEducationRecords(runtimeRowsRaw);
    if (normalized.length === 0) {
      return [{
        id: 'empty-row',
        round: EMPTY_PLACEHOLDER,
        time: EMPTY_PLACEHOLDER,
        content: EMPTY_PLACEHOLDER,
        feedback: EMPTY_PLACEHOLDER,
      }];
    }
    return normalized;
  }, [context, runtimeDataRef, runtimeStatusRef]);

  return (
    <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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
            {tableRows.map((record) => (
              <tr key={record.id} className="text-slate-900 dark:text-slate-100">
                <td className="py-3">{toDisplayText(record.round)}</td>
                <td className="py-3">{toDisplayText(record.time)}</td>
                <td className="py-3">{toDisplayText(record.content)}</td>
                <td className="py-3">{toDisplayText(record.feedback)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </InnerCardWrapper>
  );
};

export const PrecautionsCard = ({ title = "注意事项", hideHeader = false, onEdit, onRuntimeSave, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState<PrecautionsFormData>(() => (
    context === 'workbench' ? { ...EMPTY_PRECAUTIONS_FORM } : { ...precautions }
  ));

  useEffect(() => {
    if (context !== 'workbench' || runtimeStatus !== 'ready' || isEditing) {
      return;
    }
    setFormData((prev) => buildPrecautionsFormData(runtimeData, prev));
  }, [context, isEditing, runtimeData, runtimeStatus]);

  const handleSave = async () => {
    if (context === 'workbench' && onRuntimeSave) {
      const payload = pickRuntimeResultObject(runtimeData);
      setIsSaving(true);
      try {
        await Promise.resolve(onRuntimeSave({
          pkId: payload.pkId ?? payload.id ?? '',
          customerMasterId: payload.customerMasterId ?? '',
          attentionNote: payload.attentionNote ?? payload.remark ?? '',
          consumptionHabit: formData.consumptionHabits,
          mostCareAbout: formData.mostCareAbout,
          communicationPreference: formData.communicationPreferences,
          communicationTaboo: formData.communicationTaboos,
          remark: payload.remark ?? '',
          owner: payload.owner ?? payload.ownerName ?? '',
          executionDate: payload.executionDate ?? '',
        }));
      } finally {
        setIsSaving(false);
      }
    }
    setIsEditing(false);
  };

  const handleEditClick = () => {
    if (context === 'management') {
      if (onEdit) onEdit();
    } else {
      if (!isEditing && runtimeStatus === 'ready') {
        setFormData((prev) => buildPrecautionsFormData(runtimeData, prev));
      }
      setIsEditing((prev) => !prev);
    }
  };

  return (
    <InnerCardWrapper
      title={title}
      onEdit={handleEditClick}
      hideHeader={hideHeader}
      showEdit={true}
      context={context}
      runtimeData={runtimeData}
      runtimeStatus={runtimeStatus}
      runtimeError={runtimeError}
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
                onClick={handleEditClick}
                className="p-1 text-orange-400 hover:text-orange-600 transition-colors"
                title="编辑注意事项"
              >
                <Edit className="w-3.5 h-3.5" />
              </button>
            )}
            {isEditing && (
              <button
                onClick={() => { void handleSave(); }}
                disabled={isSaving}
                className="px-3 py-1 bg-orange-500 disabled:bg-orange-300 text-white text-[10px] font-bold rounded-lg hover:bg-orange-600 transition-colors shadow-sm"
              >
                {isSaving ? '保存中...' : '保存'}
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
                  onChange={e => setFormData({ ...formData, [field.id]: e.target.value })}
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

export const ConsultationRecordsCard = ({ title = "综合分析及咨询记录", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => {
  const consultant = useRuntimeFieldValue('咨询顾问', EMPTY_PLACEHOLDER, ['consultant', 'consultantName']);
  const consultationDate = useRuntimeFieldValue('咨询日期', EMPTY_PLACEHOLDER, ['consultationDate', 'date']);
  const consultantInitial = consultant === EMPTY_PLACEHOLDER ? EMPTY_PLACEHOLDER : consultant.charAt(0);

  return (
    <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
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
              {consultantInitial}
            </div>
            <div>
              <div className="text-sm text-slate-500 dark:text-slate-400">咨询顾问</div>
              <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{consultant}</div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-500 dark:text-slate-400">咨询日期</div>
            <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{consultationDate}</div>
          </div>
        </div>
      </div>
    </InnerCardWrapper>
  );
};

export const RemarksCard = ({ title = "备注", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => {
  const content = useRuntimeFieldValue('备注', remarks.content, ['content', 'remark', 'remarks', 'note', 'comment']);

  return (
    <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
      <div className="text-sm text-slate-900 dark:text-slate-100 bg-yellow-50/50 dark:bg-yellow-900/10 p-4 rounded-xl border border-yellow-200/50 dark:border-yellow-800/30 leading-relaxed">
        {content}
      </div>
    </InnerCardWrapper>
  );
};

export const ExecutionDateCard = ({ title = "负责人及执行日期", hideHeader = false, onEdit, context = 'management', runtimeData, runtimeStatus, runtimeError }: CardRuntimeProps) => {
  const responsiblePerson = useRuntimeFieldValue('负责人', EMPTY_PLACEHOLDER, ['owner', 'responsiblePerson', 'ownerName']);
  const executionDateText = useRuntimeFieldValue('执行日期', EMPTY_PLACEHOLDER, ['executionDate']);
  const lastUpdateDate = useRuntimeFieldValue('最近更新', EMPTY_PLACEHOLDER, ['lastUpdateDate', 'updatedAt']);
  const responsibleInitial = responsiblePerson === EMPTY_PLACEHOLDER ? EMPTY_PLACEHOLDER : responsiblePerson.charAt(0);

  return (
    <InnerCardWrapper title={title} onEdit={onEdit} hideHeader={hideHeader} showEdit={context === 'management'} context={context} runtimeData={runtimeData} runtimeStatus={runtimeStatus} runtimeError={runtimeError}>
      <div className="flex items-center justify-between bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl border border-slate-100 dark:border-slate-700/50">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center text-indigo-600 dark:text-indigo-400 font-bold text-sm">
            {responsibleInitial}
          </div>
          <div>
            <div className="text-sm text-slate-500 dark:text-slate-400">负责人</div>
            <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{responsiblePerson}</div>
          </div>
        </div>
        <div className="space-y-1 text-right">
          <div>
            <span className="text-sm text-slate-500 dark:text-slate-400 mr-2">执行日期</span>
            <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{executionDateText}</span>
          </div>
          <div>
            <span className="text-sm text-slate-500 dark:text-slate-400 mr-2">最近更新</span>
            <span className="text-sm text-slate-900 dark:text-slate-100">{lastUpdateDate}</span>
          </div>
        </div>
      </div>
    </InnerCardWrapper>
  );
};
