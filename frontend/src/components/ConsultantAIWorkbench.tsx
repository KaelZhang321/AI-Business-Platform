import React, { useEffect, useMemo, useRef, useState } from 'react';
import { KeyboardSensor, PointerSensor, type DragEndEvent, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { apiClient } from '../services/api';
import { aiReportApi } from '../services/api/aiReportApi';
import {
  aiComponentViewApi,
  type RoleCardConfig,
  type RoleCardEndpointRelation,
} from '../services/api/aiComponentViewApi';
import { AssistantSidebarPanel } from './consultant-ai-workbench/modules/AssistantSidebarPanel';
import { CustomerSelectionModal } from './consultant-ai-workbench/modules/CustomerSelectionModal';
import { ExpandedCardModal } from './consultant-ai-workbench/modules/ExpandedCardModal';
import { FloatingAssistantBubble } from './consultant-ai-workbench/modules/FloatingAssistantBubble';
import { InsightsArea } from './consultant-ai-workbench/modules/InsightsArea';
import { MainContentPanel } from './consultant-ai-workbench/modules/MainContentPanel';
import { WorkbenchHeaderSection } from './consultant-ai-workbench/modules/WorkbenchHeaderSection';
import { AI_CARDS_DATA } from './AICards';
import type {
  AIResultItem,
  ChatHistoryItem,
  ConsultantAIWorkbenchProps,
  CustomerRecord,
  SavedLayout,
} from './consultant-ai-workbench/modules/types';

/** 原始客户列表接口返回的单条客户数据 */
type RawCustomerItem = {
  customerId?: string | number | null;
  patientName?: string | null;
  gender?: string | null;
  age?: number | string | null;
  encryptedIdCard?: string | null;
  idCardObfuscated?: string | null;
  encryptedPhone?: string | null;
  phoneObfuscated?: string | null;
  typeName?: string | null;
  storeName?: string | null;
  mainTeacherName?: string | null;
  subTeacherName?: string | null;
  latestExamDate?: string | null;
};

/** 客户列表 API 响应体（支持多层嵌套格式） */
type CustomerListApiResponse = {
  data?: RawCustomerItem[] | { data?: RawCustomerItem[]; total?: number | string };
  total?: number | string;
};

/** 客户分页参数 */
const CUSTOMER_PAGE_SIZE = 10;
/** 卡片运行时加载状态 */
type CardRuntimeStatus = 'loading' | 'ready' | 'empty' | 'error';
type RuntimeDataByCardId = Record<string, unknown>;
type RuntimeStatusByCardId = Record<string, CardRuntimeStatus>;
type RuntimeErrorByCardId = Record<string, string>;
type CardEndpointMap = Record<string, RoleCardEndpointRelation[]>;

/** 根据最近体检日期判断 AI 评估结果（超过6个月为“优先复查”） */
function resolveAiJudgment(latestExamDate?: string | null) {
  if (!latestExamDate) return '优先复查';
  const examTime = new Date(latestExamDate).getTime();
  if (Number.isNaN(examTime)) return '持续观察';
  const sixMonthsMs = 1000 * 60 * 60 * 24 * 180;
  return Date.now() - examTime > sixMonthsMs ? '优先复查' : '持续观察';
}

/** 拼接客户摘要信息（客户类型、门店、带教老师） */
function resolveCustomerSummary(record: {
  typeName?: string | null;
  storeName?: string | null;
  mainTeacherName?: string | null;
  subTeacherName?: string | null;
}) {
  const parts = [record.typeName, record.storeName].filter(Boolean);
  const teacher = [record.mainTeacherName, record.subTeacherName].filter(Boolean).join(' / ');
  if (teacher) {
    parts.push(`带教: ${teacher}`);
  }
  return parts.length > 0 ? parts.join(' · ') : '待补充';
}

/** 把原始 API 客户数据映射为前端 CustomerRecord */
function mapApiCustomer(item: RawCustomerItem, index: number): CustomerRecord {
  const id = item.customerId != null ? String(item.customerId) : `api-${Date.now()}-${index}`;
  return {
    id,
    name: item.patientName?.trim() || '未知客户',
    gender: item.gender || '未知',
    age: Number(item.age ?? 0),
    phone: item.phoneObfuscated || undefined,
    idCard: item.idCardObfuscated || undefined,
    lastCheckDate: item.latestExamDate || '暂无',
    aiJudgment: resolveAiJudgment(item.latestExamDate),
    keyAbnormal: resolveCustomerSummary(item),
    customerId: item.customerId != null ? String(item.customerId) : undefined,
    encryptedIdCard: item.encryptedIdCard ?? null,
    encryptedPhone: item.encryptedPhone ?? null,
    typeName: item.typeName ?? null,
    storeName: item.storeName ?? null,
    mainTeacherName: item.mainTeacherName ?? null,
    subTeacherName: item.subTeacherName ?? null,
    latestExamDate: item.latestExamDate ?? null,
  };
}

/** 将 AI 消息对象中的 ui_spec 字段统一为 spec */
function normalizeAiMessageObject(messageObj: Record<string, unknown>): Record<string, unknown> {
  const normalized = { ...messageObj };
  if (!normalized.spec && normalized.ui_spec && typeof normalized.ui_spec === 'object') {
    normalized.spec = normalized.ui_spec;
  }
  return normalized;
}

/** 尝试将字符串解析为 JSON 对象（非对象返回 null） */
function parseAiMessageObject(content: unknown): Record<string, unknown> | null {
  if (typeof content !== 'string') {
    return null;
  }

  const trimmed = content.trim();
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) {
    return null;
  }

  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return null;
  }

  return null;
}

/** 从 AI 消息对象中提取摘要文本 */
function pickAiSummary(messageObj: Record<string, unknown>): string {
  const candidates = [messageObj.text, messageObj.message, messageObj.summary, messageObj.reply, messageObj.result];
  for (const item of candidates) {
    if (typeof item === 'string' && item.trim()) {
      return item.trim();
    }
  }
  return '';
}

/** 将任意类型的 AI 回复内容统一为字符串 */
function normalizeAiResponseContent(content: unknown): string {
  if (typeof content === 'string') {
    const parsedObject = parseAiMessageObject(content);
    if (parsedObject) {
      return JSON.stringify(normalizeAiMessageObject(parsedObject));
    }
    return content.trim();
  }

  if (content && typeof content === 'object') {
    return JSON.stringify(normalizeAiMessageObject(content as Record<string, unknown>));
  }

  return '';
}

/** 从 AI 回复中提取摘要显示在聊天气泡中 */
function extractAiResultSummary(content: unknown, customerName: string): string {
  if (typeof content === 'string' && content.trim()) {
    const parsedObject = parseAiMessageObject(content);
    if (parsedObject) {
      const parsedSummary = pickAiSummary(normalizeAiMessageObject(parsedObject));
      if (parsedSummary) {
        return parsedSummary;
      }
      return `已为您生成 ${customerName} 的对话结果，请在 AI结果显示区查看。`;
    }
    return content.trim();
  }

  if (content && typeof content === 'object') {
    const summary = pickAiSummary(normalizeAiMessageObject(content as Record<string, unknown>));
    if (summary) {
      return summary;
    }
  }

  return `已为您生成 ${customerName} 的对话结果，请在 AI结果显示区查看。`;
}

/** 解析后端返回的卡片配置 JSON 为卡片 ID 数组 */
function parseCardSchemaJsonToCards(raw: unknown, validCardIdSet: Set<string>): string[] {
  if (typeof raw !== 'string' || !raw.trim()) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    const result: string[] = [];

    const pushCardId = (value: unknown) => {
      if (typeof value !== 'string') {
        return;
      }
      const cardId = value.trim();
      if (!cardId || !validCardIdSet.has(cardId) || result.includes(cardId)) {
        return;
      }
      result.push(cardId);
    };

    if (Array.isArray(parsed)) {
      parsed.forEach(pushCardId);
      return result;
    }

    if (parsed && typeof parsed === 'object') {
      const maybeCardIds = (parsed as { cardIds?: unknown }).cardIds;
      if (Array.isArray(maybeCardIds)) {
        maybeCardIds.forEach(pushCardId);
      }

      const maybeCards = (parsed as { cards?: unknown }).cards;
      if (Array.isArray(maybeCards)) {
        maybeCards.forEach((cardItem) => {
          if (!cardItem || typeof cardItem !== 'object') {
            return;
          }
          const cardId =
            (cardItem as { id?: unknown; cardId?: unknown; cardConfigId?: unknown }).id ??
            (cardItem as { id?: unknown; cardId?: unknown; cardConfigId?: unknown }).cardId ??
            (cardItem as { id?: unknown; cardId?: unknown; cardConfigId?: unknown }).cardConfigId;
          pushCardId(cardId);
        });
      }
    }

    return result;
  } catch {
    return [];
  }
}

/** 从后端响应中提取 cardSchemaJson 字段 */
function pickCardSchemaJson(payload: unknown): unknown {
  if (Array.isArray(payload)) {
    for (const item of payload) {
      if (!item || typeof item !== 'object') {
        continue;
      }
      const schema = (item as { cardSchemaJson?: unknown }).cardSchemaJson;
      if (schema !== undefined && schema !== null) {
        return schema;
      }
    }
    return undefined;
  }

  if (payload && typeof payload === 'object') {
    return (payload as { cardSchemaJson?: unknown }).cardSchemaJson;
  }

  return undefined;
}

/** 从 API 响应中提取当前登录用户的角色卡片配置 */
function pickMineRoleConfig(payload: unknown): RoleCardConfig | null {
  if (Array.isArray(payload)) {
    for (const item of payload) {
      if (item && typeof item === 'object') {
        return item as RoleCardConfig;
      }
    }
    return null;
  }

  if (payload && typeof payload === 'object') {
    return payload as RoleCardConfig;
  }

  return null;
}

/** 解包运行时接口响应的 data 层 */
function normalizeRuntimeResponseData(payload: unknown): unknown {
  if (payload && typeof payload === 'object') {
    const maybeEnvelope = payload as { data?: unknown };
    if (maybeEnvelope.data !== undefined) {
      return maybeEnvelope.data;
    }
  }
  return payload;
}

function toObjectRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

/** 根据角色卡片配置构建卡片 ID → 接口关联的映射表 */
function buildCardEndpointMap(config: RoleCardConfig | null, validCardIdSet: Set<string>): CardEndpointMap {
  if (!config?.cardEndpointRelations || typeof config.cardEndpointRelations !== 'object') {
    return {};
  }

  const nextMap: CardEndpointMap = {};
  const relationEntries = Object.entries(config.cardEndpointRelations);
  for (const [cardId, relations] of relationEntries) {
    const normalizedCardId = typeof cardId === 'string' ? cardId.trim() : '';
    if (!normalizedCardId || !validCardIdSet.has(normalizedCardId) || !Array.isArray(relations)) {
      continue;
    }

    const normalizedRelations = relations
      .filter((relation): relation is RoleCardEndpointRelation => Boolean(relation && typeof relation === 'object'))
      .map((relation) => ({
        ...relation,
        endpointId: typeof relation.endpointId === 'string' ? relation.endpointId.trim() : relation.endpointId,
        sortOrder: typeof relation.sortOrder === 'number' ? relation.sortOrder : Number(relation.sortOrder ?? 0),
      }))
      .filter((relation) => Boolean(relation.endpointId));

    if (normalizedRelations.length === 0) {
      continue;
    }

    normalizedRelations.sort((a, b) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0));
    nextMap[normalizedCardId] = normalizedRelations;
  }

  return nextMap;
}

/** 获取客户加密身份证号（用于接口调用） */
function resolveCustomerIdCardValue(customer: CustomerRecord | null): string {
  if (!customer) {
    return '';
  }
  const encryptedIdCard = typeof customer.encryptedIdCard === 'string' ? customer.encryptedIdCard.trim() : '';
  const rawIdCard = typeof customer.idCard === 'string' ? customer.idCard.trim() : '';
  return encryptedIdCard || rawIdCard;
}

/**
 * 顾问 AI 工作台主组件：
 * 集合客户选择、AI 助手对话、卡片布局管理、运行时数据加载和智能洞察面板。
 */
export const ConsultantAIWorkbench: React.FC<ConsultantAIWorkbenchProps> = ({
  setCurrentPage = (_page) => { },
  setNavigationParams,
}) => {
  const [customerPool, setCustomerPool] = useState<CustomerRecord[]>([]);
  const [isCustomersLoading, setIsCustomersLoading] = useState(false);
  const [isLoadingMoreCustomers, setIsLoadingMoreCustomers] = useState(false);
  const [hasMoreCustomers, setHasMoreCustomers] = useState(true);
  const [customerPageNo, setCustomerPageNo] = useState(0);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerRecord | null>(null);
  const [chatMessage, setChatMessage] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const [isRightPanelOpen, setIsRightPanelOpen] = useState(false);
  const [isAssistantShrunk, setIsAssistantShrunk] = useState(false);
  const [aiResults, setAiResults] = useState<AIResultItem[]>([]);
  const [aiFloatingTip, setAiFloatingTip] = useState('');
  const constraintsRef = useRef<HTMLDivElement | null>(null);

  const [dashboardCards, setDashboardCards] = useState<string[]>([]);
  const [cardEndpointMap, setCardEndpointMap] = useState<CardEndpointMap>({});
  const [runtimeDataByCardId, setRuntimeDataByCardId] = useState<RuntimeDataByCardId>({});
  const [runtimeStatusByCardId, setRuntimeStatusByCardId] = useState<RuntimeStatusByCardId>({});
  const [runtimeErrorByCardId, setRuntimeErrorByCardId] = useState<RuntimeErrorByCardId>({});
  const [isLayoutViewEnabled, setIsLayoutViewEnabled] = useState(false);
  const [isLayoutSaved, setIsLayoutSaved] = useState(false);
  const [expandedCardId, setExpandedCardId] = useState<string | null>(null);
  const [customerLayoutsFromApi, setCustomerLayoutsFromApi] = useState<SavedLayout[]>([]);

  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([]);
  const chatRequestPendingRef = useRef(false);
  const runtimeRequestSeqRef = useRef(0);

  const parseCustomerPayload = (payload: CustomerListApiResponse | RawCustomerItem[] | undefined) => {
    let list: RawCustomerItem[] = [];
    let total: number | undefined;

    if (Array.isArray(payload)) {
      list = payload;
    } else if (Array.isArray(payload?.data)) {
      list = payload.data;
      total = typeof payload.total === 'number' ? payload.total : Number(payload.total ?? NaN);
    } else if (payload?.data && typeof payload.data === 'object') {
      const nested = payload.data as { data?: RawCustomerItem[]; total?: number | string };
      if (Array.isArray(nested.data)) {
        list = nested.data;
      }
      const nestedTotal = nested.total ?? payload.total;
      total = typeof nestedTotal === 'number' ? nestedTotal : Number(nestedTotal ?? NaN);
    }

    if (!Number.isFinite(total as number)) {
      total = undefined;
    }

    return { list, total };
  };

  const fetchCustomerPage = async (pageNo: number, append = false, keyword = searchTerm.trim()) => {
    if (append) {
      if (isCustomersLoading || isLoadingMoreCustomers || !hasMoreCustomers) {
        return;
      }
      setIsLoadingMoreCustomers(true);
    } else {
      setIsCustomersLoading(true);
    }

    try {
      const res = await aiReportApi.getcustomersListApi({
        queryParams: {},
        body: {
          customerInfo: keyword,
        },
        page: String(pageNo),
        size: String(CUSTOMER_PAGE_SIZE),
      });
      const payload = res as CustomerListApiResponse | RawCustomerItem[] | undefined;
      const { list, total } = parseCustomerPayload(payload);
      const mapped = list.map(mapApiCustomer);

      if (append) {
        setCustomerPool((prev) => {
          const merged = Array.from(new Map([...prev, ...mapped].map((item) => [String(item.id), item])).values());
          if (typeof total === 'number') {
            setHasMoreCustomers(merged.length < total);
          } else {
            setHasMoreCustomers(mapped.length >= CUSTOMER_PAGE_SIZE);
          }
          return merged;
        });
      } else if (mapped.length > 0) {
        setCustomerPool(mapped);
        if (typeof total === 'number') {
          setHasMoreCustomers(mapped.length < total);
        } else {
          setHasMoreCustomers(mapped.length >= CUSTOMER_PAGE_SIZE);
        }
      } else {
        setCustomerPool([]);
        setHasMoreCustomers(false);
      }
      setCustomerPageNo(pageNo);
    } catch (error) {
      console.error('[ConsultantAIWorkbench] load customers error:', error);
      if (!append) {
        setCustomerPool([]);
        setHasMoreCustomers(false);
      }
    } finally {
      if (append) {
        setIsLoadingMoreCustomers(false);
      } else {
        setIsCustomersLoading(false);
      }
    }
  };

  useEffect(() => {
    void fetchCustomerPage(1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isModalOpen) {
      return;
    }
    void fetchCustomerPage(1, false, searchTerm.trim());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm, isModalOpen]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) {
      return;
    }

    setDashboardCards((items) => {
      const oldIndex = items.indexOf(active.id as string);
      const newIndex = items.indexOf(over.id as string);
      return arrayMove(items, oldIndex, newIndex);
    });
    setIsLayoutSaved(false);
  };

  const handleSaveLayout = async () => {
    if (!selectedCustomer) {
      return;
    }
    const customerIdCard = resolveCustomerIdCardValue(selectedCustomer);
    if (!customerIdCard) {
      setIsLayoutSaved(false);
      return;
    }

    const customerLayoutsCount = customerLayoutsFromApi.length;
    const favoriteName = `AI结果显示区-默认布局${customerLayoutsCount + 1}`;
    const cardJson = JSON.stringify(dashboardCards);

    try {
      const saved = await aiComponentViewApi.createCustomerCardCustomize({
        customerIdCard,
        favoriteName,
        cardJson,
      });

      const newLayout: SavedLayout = {
        id: (saved?.id ?? Date.now()).toString(),
        name: saved?.favoriteName?.trim() || favoriteName,
        cards: [...dashboardCards],
        customerId: selectedCustomer.id,
      };

      setCustomerLayoutsFromApi((prev) => [...prev, newLayout]);
      setIsLayoutSaved(true);
      setTimeout(() => setIsLayoutSaved(false), 2000);
    } catch (error) {
      console.error('[ConsultantAIWorkbench] create customer-card-customizes error:', error);
      setIsLayoutSaved(false);
    }
  };

  const handleRenameLayout = async (id: string, newName: string) => {
    const targetName = newName.trim();
    if (!targetName) {
      return;
    }
    const customerIdCard = resolveCustomerIdCardValue(selectedCustomer);
    if (!customerIdCard) {
      return;
    }

    try {
      const saved = await aiComponentViewApi.renameCustomerCardCustomize(id, {
        favoriteName: targetName,
        customerIdCard,
      });
      const finalName = saved?.favoriteName?.trim() || targetName;
      setCustomerLayoutsFromApi((prev) => prev.map((layout) => (layout.id === id ? { ...layout, name: finalName } : layout)));
    } catch (error) {
      console.error('[ConsultantAIWorkbench] rename customer-card-customizes error:', error);
    }
  };

  const handleApplyLayout = (id: string) => {
    const layout = customerLayoutsFromApi.find((item) => item.id === id);
    if (layout) {
      setDashboardCards(layout.cards);
      setIsLayoutViewEnabled(true);
    }
  };

  const handleDeleteLayout = async (id: string) => {
    try {
      await aiComponentViewApi.deleteCustomerCardCustomize(id);
      setCustomerLayoutsFromApi((prev) => prev.filter((layout) => layout.id !== id));
    } catch (error) {
      console.error('[ConsultantAIWorkbench] delete customer-card-customizes error:', error);
    }
  };

  const handleDeleteCard = (id: string) => {
    setDashboardCards((prev) => prev.filter((cardId) => cardId !== id));
  };

  const currentCustomerLayouts = useMemo(() => customerLayoutsFromApi, [customerLayoutsFromApi]);

  const filteredCustomers = useMemo(() => customerPool, [customerPool]);

  const [latestAssistantMessage, setLatestAssistantMessage] = useState<string | null>(null);
  const validCardIdSet = useMemo(() => new Set(AI_CARDS_DATA.map((item) => item.id)), []);

  const handleLoadMoreCustomers = () => {
    void fetchCustomerPage(customerPageNo + 1, true, searchTerm.trim());
  };

  const applyCardsFromCurrentUserSchema = async () => {
    try {
      const mineConfig = await aiComponentViewApi.queryCurrentLoginAvailableCards();
      const cardSchemaJson = pickCardSchemaJson(mineConfig);
      const cardsFromApi = parseCardSchemaJsonToCards(cardSchemaJson, validCardIdSet);
      const mineRoleConfig = pickMineRoleConfig(mineConfig);
      const nextEndpointMap = buildCardEndpointMap(mineRoleConfig, validCardIdSet);

      setDashboardCards(cardsFromApi);
      setCardEndpointMap(nextEndpointMap);
    } catch (error) {
      console.error('[ConsultantAIWorkbench] query current login available cards error:', error);
      setDashboardCards([]);
      setCardEndpointMap({});
    }
  };

  const loadCustomerLayoutsByApi = async (customer: CustomerRecord) => {
    const customerIdCard = resolveCustomerIdCardValue(customer);
    if (!customerIdCard) {
      setCustomerLayoutsFromApi([]);
      return;
    }

    try {
      const list = await aiComponentViewApi.listCustomerCardCustomizesByCustomer({ customerIdCard });
      const dataList = Array.isArray(list) ? list : [];

      const mapped: SavedLayout[] = dataList.map((item, index) => ({
        id: String(item?.id ?? `${customer.id}-${Date.now()}-${index}`),
        name: item?.favoriteName?.trim() || `接口布局${index + 1}`,
        cards: parseCardSchemaJsonToCards(item?.cardJson, validCardIdSet),
        customerId: customer.id,
      }));

      setCustomerLayoutsFromApi(mapped);
    } catch (error) {
      console.error('[ConsultantAIWorkbench] list customer-card-customizes by customer error:', error);
      setCustomerLayoutsFromApi([]);
    }
  };

  const handleSelectCustomer = (customer: CustomerRecord) => {
    setSelectedCustomer(customer);
    setIsModalOpen(false);
    setIsLayoutViewEnabled(true);
    setCustomerLayoutsFromApi([]);
    setChatHistory([
      {
        role: 'assistant',
        content: `已为您定位到客户 ${customer.name}，已同步客户档案。您可以让我整理客户全景、判断续费概率等。`,
      },
    ]);
    void loadCustomerLayoutsByApi(customer);
    void applyCardsFromCurrentUserSchema();
  };

  useEffect(() => {
    const requestSeq = runtimeRequestSeqRef.current + 1;
    runtimeRequestSeqRef.current = requestSeq;

    if (!selectedCustomer) {
      setRuntimeDataByCardId({});
      setRuntimeStatusByCardId({});
      setRuntimeErrorByCardId({});
      return;
    }

    const visibleCards = Array.from(
      new Set(dashboardCards.map((cardId) => cardId.trim()).filter(Boolean)),
    ) as string[];
    if (visibleCards.length === 0) {
      setRuntimeDataByCardId({});
      setRuntimeStatusByCardId({});
      setRuntimeErrorByCardId({});
      return;
    }

    const encryptedIdCard = typeof selectedCustomer.encryptedIdCard === 'string' ? selectedCustomer.encryptedIdCard.trim() : '';
    const initialStatus: RuntimeStatusByCardId = {};
    const initialErrors: RuntimeErrorByCardId = {};
    for (const cardId of visibleCards) {
      const hasRelations = Array.isArray(cardEndpointMap[cardId]) && cardEndpointMap[cardId].length > 0;
      initialStatus[cardId] = encryptedIdCard && hasRelations ? 'loading' : 'empty';
      if (!hasRelations) {
        initialErrors[cardId] = '未配置接口';
      } else if (!encryptedIdCard) {
        initialErrors[cardId] = '客户缺少加密身份证';
      }
    }
    setRuntimeStatusByCardId(initialStatus);
    setRuntimeErrorByCardId(initialErrors);
    setRuntimeDataByCardId((prev) => {
      const next: RuntimeDataByCardId = {};
      for (const cardId of visibleCards) {
        if (prev[cardId] !== undefined) {
          next[cardId] = prev[cardId];
        }
      }
      return next;
    });

    if (!encryptedIdCard) {
      return;
    }

    const loadRuntimeData = async () => {
      const perCardTasks = visibleCards.map(async (cardId) => {
        const relations = cardEndpointMap[cardId] ?? [];
        if (relations.length === 0) {
          return {
            cardId,
            status: 'empty' as CardRuntimeStatus,
            data: undefined,
            error: '未配置接口',
          };
        }

        let merged: Record<string, unknown> = {};
        for (const relation of relations) {
          const endpointId = relation.endpointId?.trim();
          if (!endpointId) {
            continue;
          }
          const response = await aiComponentViewApi.invokeRuntimeEndpoint(endpointId, {
            flowNum: 1,
            queryParams: {},
            body: {
              encryptedIdCard,
            },
            createdBy: '',
          });
          const normalized = normalizeRuntimeResponseData(response);
          merged = { ...merged, ...toObjectRecord(normalized) };
        }

        return {
          cardId,
          status: 'ready' as CardRuntimeStatus,
          data: merged,
          error: '',
        };
      });

      const settled = await Promise.allSettled(perCardTasks);
      if (runtimeRequestSeqRef.current !== requestSeq) {
        return;
      }

      const nextStatus: RuntimeStatusByCardId = {};
      const nextErrors: RuntimeErrorByCardId = {};
      const nextData: RuntimeDataByCardId = {};

      for (const item of settled) {
        if (item.status === 'fulfilled') {
          const { cardId, status, data, error } = item.value;
          nextStatus[cardId] = status;
          if (error) {
            nextErrors[cardId] = error;
          }
          if (status === 'ready' && data !== undefined) {
            nextData[cardId] = data;
          }
          continue;
        }
      }

      for (let i = 0; i < settled.length; i += 1) {
        const item = settled[i];
        if (item.status === 'fulfilled') {
          continue;
        }
        const cardId = visibleCards[i];
        nextStatus[cardId] = 'error';
        nextErrors[cardId] = '接口请求失败';
      }

      setRuntimeStatusByCardId(nextStatus);
      setRuntimeErrorByCardId(nextErrors);
      setRuntimeDataByCardId(nextData);
    };

    void loadRuntimeData();
  }, [cardEndpointMap, dashboardCards, selectedCustomer]);

  const handleChatSubmit = async (text?: string) => {
    if (chatRequestPendingRef.current) {
      return;
    }

    const input = typeof text === 'string' ? text : chatMessage;
    if (!input.trim()) {
      return;
    }

    const query = input.trim();
    setChatHistory((prev) => [...prev, { role: 'user', content: query }]);
    setChatMessage('');

    if (!selectedCustomer) {
      const foundCustomer = customerPool.find(
        (customer) => customer.name === query || customer.phone === query || customer.idCard === query
      );

      if (foundCustomer) {
        setSelectedCustomer(foundCustomer);
        setIsLayoutViewEnabled(true);
        setCustomerLayoutsFromApi([]);
        setChatHistory((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `已为您定位到客户 ${foundCustomer.name}，已同步客户档案。您可以让我整理客户全景、判断续费概率等。`,
          },
        ]);
        void loadCustomerLayoutsByApi(foundCustomer);
        void applyCardsFromCurrentUserSchema();
        return;
      }

      setChatHistory((prev) => [...prev, { role: 'assistant', content: '未找到匹配的客户，请重新输入姓名、手机号或身份证号。' }]);
      return;
    }

    setIsRightPanelOpen(false);
    setAiFloatingTip('正在生成对话结果...');
    chatRequestPendingRef.current = true;

    try {
      const response = await apiClient.post('/api/v1/api-query', { query });
      const aiResponseContent = response.data?.data ?? response.data ?? '';
      const assistantContent = normalizeAiResponseContent(aiResponseContent);
      const resultSummary = extractAiResultSummary(aiResponseContent, selectedCustomer.name);
      const finalAssistantContent = assistantContent || resultSummary;

      setIsLayoutViewEnabled(false);
      setLatestAssistantMessage(finalAssistantContent);

      setAiResults((prev) => [
        {
          id: Date.now(),
          type: 'AI对话结果',
          title: 'AI对话结果',
          content: resultSummary,
        },
        ...prev,
      ]);

      setChatHistory((prev) => [
        ...prev,
        { role: 'assistant', content: '已根据指令生成结构化卡片方案，请在旁侧查阅。' },
      ]);
    } catch (error) {
      console.error('[ConsultantAIWorkbench] API Query error:', error);
      const fallbackMessage = '服务暂不可用，已切换为本地结构化示例。';

      setIsLayoutViewEnabled(false);
      setLatestAssistantMessage(fallbackMessage);

      setAiResults((prev) => [
        {
          id: Date.now(),
          type: 'AI对话结果',
          title: 'AI对话结果',
          content: fallbackMessage,
        },
        ...prev,
      ]);

      setChatHistory((prev) => [
        ...prev,
        { role: 'assistant', content: '服务暂不可用，生成结构化方案失败。' },
      ]);
    } finally {
      chatRequestPendingRef.current = false;
      setAiFloatingTip('已为您生成对话结果');
      setTimeout(() => setAiFloatingTip(''), 3000);
    }
  };

  const middleColClass =
    !isAssistantShrunk && isRightPanelOpen
      ? '2xl:col-span-6'
      : !isAssistantShrunk && !isRightPanelOpen
        ? '2xl:col-span-9'
        : isAssistantShrunk && isRightPanelOpen
          ? '2xl:col-span-9'
          : '2xl:col-span-12';

  return (
    <div className="relative flex h-full min-h-0 flex-col gap-6">
      <WorkbenchHeaderSection
        hasCards={dashboardCards.length > 0}
        isLayoutSaved={isLayoutSaved}
        onSaveLayout={handleSaveLayout}
        onOpenCustomerModal={() => setIsModalOpen(true)}
      />

      <div className="relative grid flex-1 min-h-0 grid-cols-1 gap-6 2xl:grid-cols-12">
        <AssistantSidebarPanel
          isAssistantShrunk={isAssistantShrunk}
          selectedCustomer={selectedCustomer}
          chatHistory={chatHistory}
          chatMessage={chatMessage}
          onChatMessageChange={setChatMessage}
          onChatSubmit={handleChatSubmit}
          onQuickPrompt={(prompt) => {
            void handleChatSubmit(prompt);
          }}
          onShrink={() => setIsAssistantShrunk(true)}
        />

        <MainContentPanel
          middleColClass={middleColClass}
          isRightPanelOpen={isRightPanelOpen}
          selectedCustomer={selectedCustomer}
          currentCustomerLayouts={currentCustomerLayouts}
          constraintsRef={constraintsRef}
          onRenameLayout={handleRenameLayout}
          onApplyLayout={handleApplyLayout}
          onDeleteLayout={handleDeleteLayout}
          onOpenCustomerModal={() => setIsModalOpen(true)}
          onNavigateToComparison={() => {
            if (setNavigationParams && selectedCustomer) {
              setNavigationParams({ customerId: selectedCustomer.id });
            }
            setCurrentPage('ai-report-comparison');
          }}
          onNavigateToFourQuadrant={() => {
            if (setNavigationParams && selectedCustomer) {
              setNavigationParams({ customerId: selectedCustomer.id });
            }
            setCurrentPage('ai-four-quadrant');
          }}
          dashboardCards={dashboardCards}
          dndSensors={sensors}
          onDragEnd={handleDragEnd}
          onExpandCard={setExpandedCardId}
          onDeleteCard={handleDeleteCard}
          aiResults={aiResults}
          latestAssistantMessage={latestAssistantMessage}
          isLayoutViewEnabled={isLayoutViewEnabled}
          runtimeDataByCardId={runtimeDataByCardId}
          runtimeStatusByCardId={runtimeStatusByCardId}
          runtimeErrorByCardId={runtimeErrorByCardId}
        />

        <InsightsArea
          isRightPanelOpen={isRightPanelOpen}
          selectedCustomer={selectedCustomer}
          onOpenPanel={() => setIsRightPanelOpen(true)}
          onClosePanel={() => setIsRightPanelOpen(false)}
        />
      </div>

      <CustomerSelectionModal
        isOpen={isModalOpen}
        searchTerm={searchTerm}
        isLoadingCustomers={isCustomersLoading}
        isLoadingMoreCustomers={isLoadingMoreCustomers}
        hasMoreCustomers={hasMoreCustomers}
        filteredCustomers={filteredCustomers}
        onSearchTermChange={setSearchTerm}
        onLoadMoreCustomers={handleLoadMoreCustomers}
        onSelectCustomer={handleSelectCustomer}
        onClose={() => setIsModalOpen(false)}
      />

      <FloatingAssistantBubble
        isAssistantShrunk={isAssistantShrunk}
        aiFloatingTip={aiFloatingTip}
        onExpand={() => setIsAssistantShrunk(false)}
      />

      <ExpandedCardModal
        expandedCardId={expandedCardId}
        onClose={() => setExpandedCardId(null)}
        runtimeDataByCardId={runtimeDataByCardId}
        runtimeStatusByCardId={runtimeStatusByCardId}
        runtimeErrorByCardId={runtimeErrorByCardId}
      />
    </div>
  );
};
