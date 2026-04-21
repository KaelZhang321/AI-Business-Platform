import React, { useState } from 'react';
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
