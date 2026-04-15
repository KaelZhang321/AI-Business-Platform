import React, { useEffect, useMemo, useRef, useState } from 'react';
import { KeyboardSensor, PointerSensor, type DragEndEvent, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { CUSTOMERS } from '../data/mockData';
import { apiClient } from '../services/api';
import { AssistantSidebarPanel } from './consultant-ai-workbench/modules/AssistantSidebarPanel';
import { CustomerSelectionModal } from './consultant-ai-workbench/modules/CustomerSelectionModal';
import { ExpandedCardModal } from './consultant-ai-workbench/modules/ExpandedCardModal';
import { FloatingAssistantBubble } from './consultant-ai-workbench/modules/FloatingAssistantBubble';
import { InsightsArea } from './consultant-ai-workbench/modules/InsightsArea';
import { MainContentPanel } from './consultant-ai-workbench/modules/MainContentPanel';
import { WorkbenchHeaderSection } from './consultant-ai-workbench/modules/WorkbenchHeaderSection';
import resjson from './json-render/res.json'

import type {
  AIResultItem,
  ChatHistoryItem,
  ConsultantAIWorkbenchProps,
  CustomerRecord,
  SavedLayout,
} from './consultant-ai-workbench/modules/types';

const CUSTOMER_POOL = CUSTOMERS as CustomerRecord[];

function normalizeAiMessageObject(messageObj: Record<string, unknown>): Record<string, unknown> {
  const normalized = { ...messageObj };
  if (!normalized.spec && normalized.ui_spec && typeof normalized.ui_spec === 'object') {
    normalized.spec = normalized.ui_spec;
  }
  return normalized;
}

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

function pickAiSummary(messageObj: Record<string, unknown>): string {
  const candidates = [messageObj.text, messageObj.message, messageObj.summary, messageObj.reply, messageObj.result];
  for (const item of candidates) {
    if (typeof item === 'string' && item.trim()) {
      return item.trim();
    }
  }
  return '';
}

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

export const ConsultantAIWorkbench: React.FC<ConsultantAIWorkbenchProps> = ({
  setCurrentPage = (_page) => { },
  setNavigationParams,
}) => {
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
  const [isLayoutViewEnabled, setIsLayoutViewEnabled] = useState(false);
  const [isLayoutSaved, setIsLayoutSaved] = useState(false);
  const [expandedCardId, setExpandedCardId] = useState<string | null>(null);
  const [savedLayouts, setSavedLayouts] = useState<SavedLayout[]>([]);

  const [chatHistory, setChatHistory] = useState<ChatHistoryItem[]>([]);
  const chatRequestPendingRef = useRef(false);

  useEffect(() => {
    const savedLayoutsData = localStorage.getItem('aiWorkbenchLayouts');
    if (!savedLayoutsData) {
      return;
    }

    try {
      const parsedLayouts = JSON.parse(savedLayoutsData) as SavedLayout[];
      setSavedLayouts(Array.isArray(parsedLayouts) ? parsedLayouts : []);
    } catch {
      setSavedLayouts([]);
    }
  }, []);

  const loadCustomerLayout = (customer: CustomerRecord, currentLayouts: SavedLayout[]) => {
    const customerLayouts = currentLayouts.filter((layout) => layout.customerId === customer.id);
    if (customerLayouts.length > 0) {
      setDashboardCards(customerLayouts[customerLayouts.length - 1].cards);
      return;
    }

    setDashboardCards(['panorama', 'risk', 'objection', 'renewal', 'upsell', 'consumption', 'insight', 'action']);
  };

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

  const handleSaveLayout = () => {
    if (!selectedCustomer) {
      return;
    }

    const customerLayoutsCount = savedLayouts.filter((layout) => layout.customerId === selectedCustomer.id).length;
    const newLayout: SavedLayout = {
      id: Date.now().toString(),
      name: `AI结果显示区-默认布局${customerLayoutsCount + 1}`,
      cards: [...dashboardCards],
      customerId: selectedCustomer.id,
    };

    const newLayouts = [...savedLayouts, newLayout];
    setSavedLayouts(newLayouts);
    localStorage.setItem('aiWorkbenchLayouts', JSON.stringify(newLayouts));

    setIsLayoutSaved(true);
    setTimeout(() => setIsLayoutSaved(false), 2000);
  };

  const handleRenameLayout = (id: string, newName: string) => {
    const newLayouts = savedLayouts.map((layout) => (layout.id === id ? { ...layout, name: newName } : layout));
    setSavedLayouts(newLayouts);
    localStorage.setItem('aiWorkbenchLayouts', JSON.stringify(newLayouts));
  };

  const handleApplyLayout = (id: string) => {
    const layout = savedLayouts.find((item) => item.id === id);
    if (layout) {
      setDashboardCards(layout.cards);
      setIsLayoutViewEnabled(true);
    }
  };

  const handleDeleteLayout = (id: string) => {
    const newLayouts = savedLayouts.filter((layout) => layout.id !== id);
    setSavedLayouts(newLayouts);
    localStorage.setItem('aiWorkbenchLayouts', JSON.stringify(newLayouts));
  };

  const handleDeleteCard = (id: string) => {
    setDashboardCards((prev) => prev.filter((cardId) => cardId !== id));
  };

  const currentCustomerLayouts = useMemo(() => {
    if (!selectedCustomer) {
      return [];
    }
    return savedLayouts.filter((layout) => layout.customerId === selectedCustomer.id);
  }, [savedLayouts, selectedCustomer]);

  const filteredCustomers = useMemo(() => {
    return CUSTOMER_POOL.filter((customer) =>
      customer.name.includes(searchTerm) ||
      (typeof customer.phone === 'string' && customer.phone.includes(searchTerm)) ||
      (typeof customer.idCard === 'string' && customer.idCard.includes(searchTerm))
    );
  }, [searchTerm]);

  const [latestAssistantMessage, setLatestAssistantMessage] = useState<string | null>(null);

  const handleSelectCustomer = (customer: CustomerRecord) => {
    setSelectedCustomer(customer);
    setIsModalOpen(false);
    setIsLayoutViewEnabled(true);
    setChatHistory([
      {
        role: 'assistant',
        content: `已为您定位到客户 ${customer.name}，已同步客户档案。您可以让我整理客户全景、判断续费概率等。`,
      },
    ]);
    loadCustomerLayout(customer, savedLayouts);
  };

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
      const foundCustomer = CUSTOMER_POOL.find(
        (customer) => customer.name === query || customer.phone === query || customer.idCard === query
      );

      if (foundCustomer) {
        setSelectedCustomer(foundCustomer);
        setIsLayoutViewEnabled(true);
        setChatHistory((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `已为您定位到客户 ${foundCustomer.name}，已同步客户档案。您可以让我整理客户全景、判断续费概率等。`,
          },
        ]);
        loadCustomerLayout(foundCustomer, savedLayouts);
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
      // const aiResponseContent = resjson;
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
        filteredCustomers={filteredCustomers}
        onSearchTermChange={setSearchTerm}
        onSelectCustomer={handleSelectCustomer}
        onClose={() => setIsModalOpen(false)}
      />

      <FloatingAssistantBubble
        isAssistantShrunk={isAssistantShrunk}
        aiFloatingTip={aiFloatingTip}
        onExpand={() => setIsAssistantShrunk(false)}
      />

      <ExpandedCardModal expandedCardId={expandedCardId} onClose={() => setExpandedCardId(null)} />
    </div>
  );
};
