import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Edit, Filter, LayoutTemplate, MoreHorizontal, Plus, Save, Search, X } from 'lucide-react';
import {
  aiComponentViewApi,
  type AuthRole,
  type CardGroup,
  type RoleCardConfig,
} from '../../services/api/aiComponentViewApi';
import {
  AssetCard,
  BasicHealthDataCard,
  ConsultationRecordsCard,
  ConsumptionAbilityCard,
  CustomerRelationsCard,
  EducationRecordsCard,
  ExecutionDateCard,
  HealthGoalsCard,
  HealthStatusMedicalHistoryCard,
  IdentityContactCard,
  LifestyleHabitsCard,
  PersonalPreferencesCard,
  PhysicalExamStatusCard,
  PrecautionsCard,
  PsychologyEmotionCard,
  RemarksCard,
} from './cards';
import { initialCards, initialLayouts } from './config';
import type { AIComponentManagementViewProps, CardConfig } from './types';

export const AIComponentManagementView: React.FC<AIComponentManagementViewProps> = () => {
  const [activeTab, setActiveTab] = useState('cards');
  const [cards, setCards] = useState<CardConfig[]>(initialCards);
  const [layouts, setLayouts] = useState(initialLayouts);
  const [editingCard, setEditingCard] = useState<CardConfig | null>(null);
  const [cardGroups, setCardGroups] = useState<CardGroup[]>([]);
  const [isLoadingGroups, setIsLoadingGroups] = useState(false);
  const [groupError, setGroupError] = useState('');
  const [customGroups, setCustomGroups] = useState<string[]>([]);
  const [activeGroup, setActiveGroup] = useState('全部');
  const [activeGroupCardIds, setActiveGroupCardIds] = useState<string[]>([]);
  const [isLoadingGroupCards, setIsLoadingGroupCards] = useState(false);
  const [groupCardsError, setGroupCardsError] = useState('');
  const groupCardsRequestSeqRef = useRef(0);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [categoryError, setCategoryError] = useState('');
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [isSavingCard, setIsSavingCard] = useState(false);
  const [saveCardError, setSaveCardError] = useState('');
  const [roles, setRoles] = useState<AuthRole[]>([]);
  const [isLoadingRoles, setIsLoadingRoles] = useState(false);
  const [rolesError, setRolesError] = useState('');
  const [roleCardConfigs, setRoleCardConfigs] = useState<RoleCardConfig[]>([]);
  const [isLoadingRoleCards, setIsLoadingRoleCards] = useState(false);
  const [roleCardsError, setRoleCardsError] = useState('');
  const [isSavingRoleCards, setIsSavingRoleCards] = useState(false);
  const roleCardsRequestSeqRef = useRef(0);

  const [selectedRole, setSelectedRole] = useState('doctor');

  const [isEditingLayout, setIsEditingLayout] = useState(false);
  const [draftLayouts, setDraftLayouts] = useState(initialLayouts);

  // 获取卡片分组
  useEffect(() => {
    const loadCardGroups = async () => {
      setIsLoadingGroups(true);
      setGroupError('');
      try {
        const groupRes = await aiComponentViewApi.queryCardGroupsPage({
          page: 1,
          size: 200,
          status: 'active',
        });
        const groups = Array.isArray(groupRes?.data) ? groupRes.data : [];
        setCardGroups(groups);
      } catch (error) {
        console.error('[AIComponentManagementView] query card-groups error:', error);
        setCardGroups([]);
        setGroupError('卡片分组数据加载失败，已展示默认配置。');
      } finally {
        setIsLoadingGroups(false);
      }
    };

    void loadCardGroups();
  }, []);

  // 获取角色列表
  useEffect(() => {
    const loadRoles = async () => {
      setIsLoadingRoles(true);
      setRolesError('');
      try {
        const roleRes = await aiComponentViewApi.queryAuthRoles({
          appCode: 'AI-RND-WORKFLOW',
          pageNo: 1,
          pageSize: 200,
        });
        const roleList = Array.isArray(roleRes?.records) ? roleRes.records : [];
        setRoles(roleList);
      } catch (error) {
        console.error('[AIComponentManagementView] query auth roles error:', error);
        setRoles([]);
        setRolesError('角色数据加载失败，已使用默认角色。');
      } finally {
        setIsLoadingRoles(false);
      }
    };

    void loadRoles();
  }, []);

  // 转换角色列表函数
  const roleOptions = useMemo(() => {
    const fromApi = roles
      .map((role) => ({
        code: role.roleCode?.trim() || '',
        name: role.roleName?.trim() || '',
      }))
      .filter((role): role is { code: string; name: string } => Boolean(role.code && role.name));

    if (fromApi.length > 0) {
      return fromApi;
    }

    return [];
  }, [roles]);

  useEffect(() => {
    if (roleOptions.length === 0) {
      return;
    }

    const matched = roleOptions.some((role) => role.code === selectedRole);
    if (!matched) {
      setSelectedRole(roleOptions[0].code);
    }
  }, [roleOptions, selectedRole]);

  const roleNameMap = useMemo(
    () => Object.fromEntries(roleOptions.map((role) => [role.code, role.name])),
    [roleOptions],
  );

  const selectedRoleName = roleNameMap[selectedRole] || selectedRole || '角色';
  const selectedRoleId = useMemo(() => {
    return roles.find((role) => role.roleCode?.trim() === selectedRole)?.id?.trim() || '';
  }, [roles, selectedRole]);

  const visibleRoleCardIds = useMemo(() => {
    const result = new Set<string>();

    for (const config of roleCardConfigs) {
      const rawSchema = config.cardSchemaJson;
      if (!rawSchema || typeof rawSchema !== 'string') {
        continue;
      }

      try {
        const parsed = JSON.parse(rawSchema) as unknown;
        if (Array.isArray(parsed)) {
          for (const item of parsed) {
            if (typeof item === 'string' && item.trim()) {
              result.add(item.trim());
            }
          }
          continue;
        }

        if (parsed && typeof parsed === 'object') {
          const maybeCardIds = (parsed as { cardIds?: unknown }).cardIds;
          if (Array.isArray(maybeCardIds)) {
            for (const id of maybeCardIds) {
              if (typeof id === 'string' && id.trim()) {
                result.add(id.trim());
              }
            }
            continue;
          }

          const maybeCards = (parsed as { cards?: unknown }).cards;
          if (Array.isArray(maybeCards)) {
            for (const card of maybeCards) {
              if (card && typeof card === 'object') {
                const maybeId =
                  (card as { id?: unknown; cardId?: unknown; cardConfigId?: unknown }).id ??
                  (card as { id?: unknown; cardId?: unknown; cardConfigId?: unknown }).cardId ??
                  (card as { id?: unknown; cardId?: unknown; cardConfigId?: unknown }).cardConfigId;
                if (typeof maybeId === 'string' && maybeId.trim()) {
                  result.add(maybeId.trim());
                }
              }
            }
          }
        }
      } catch {
        // Ignore invalid cardSchemaJson and continue parsing other records.
      }
    }

    return result;
  }, [roleCardConfigs]);
  const roleCardIdList = useMemo(() => Array.from(visibleRoleCardIds), [visibleRoleCardIds]);
  const roleCardIdSet = useMemo(() => new Set(roleCardIdList), [roleCardIdList]);

  useEffect(() => {
    if (!selectedRoleId) {
      setRoleCardConfigs([]);
      setRoleCardsError('');
      setIsLoadingRoleCards(false);
      return;
    }

    const requestSeq = roleCardsRequestSeqRef.current + 1;
    roleCardsRequestSeqRef.current = requestSeq;

    const loadRoleCards = async () => {
      setIsLoadingRoleCards(true);
      setRoleCardsError('');
      setRoleCardConfigs([]);
      try {
        const configList = await aiComponentViewApi.listRoleCardConfigsByRole(selectedRoleId);
        if (roleCardsRequestSeqRef.current !== requestSeq) {
          return;
        }
        setRoleCardConfigs(Array.isArray(configList) ? configList : []);
      } catch (error) {
        if (roleCardsRequestSeqRef.current !== requestSeq) {
          return;
        }
        console.error('[AIComponentManagementView] list role-card-configs by role error:', error);
        setRoleCardConfigs([]);
        setRoleCardsError('角色卡片配置加载失败，当前未选中卡片。');
      } finally {
        if (roleCardsRequestSeqRef.current === requestSeq) {
          setIsLoadingRoleCards(false);
        }
      }
    };

    void loadRoleCards();
  }, [selectedRoleId]);

  const handleSaveRoleCards = async () => {
    if (!selectedRoleId) {
      setRoleCardsError('当前角色ID为空，无法保存');
      return;
    }

    const selectedCardIds = normalizedDraftLayouts[selectedRole] ?? [];
    const cardSchemaJson = JSON.stringify(selectedCardIds);

    try {
      setIsSavingRoleCards(true);
      setRoleCardsError('');

      const latestConfigs = await aiComponentViewApi.listRoleCardConfigsByRole(selectedRoleId);
      const roleConfigList = Array.isArray(latestConfigs) ? latestConfigs : [];
      const currentConfig = roleConfigList[0];

      const savedConfig = currentConfig?.id?.trim()
        ? await aiComponentViewApi.updateRoleCardConfig(currentConfig.id.trim(), {
          roleId: selectedRoleId,
          cardSchemaJson,
        })
        : await aiComponentViewApi.createRoleCardConfig({
          roleId: selectedRoleId,
          cardSchemaJson,
        });

      const normalizedSavedConfig: RoleCardConfig = {
        ...savedConfig,
        roleId: savedConfig?.roleId || selectedRoleId,
        cardSchemaJson: savedConfig?.cardSchemaJson ?? cardSchemaJson,
      };

      setRoleCardConfigs([normalizedSavedConfig]);
      setDraftLayouts((prev) => ({
        ...prev,
        [selectedRole]: selectedCardIds,
      }));
      setLayouts((prev) => ({
        ...prev,
        [selectedRole]: selectedCardIds,
      }));
      setIsEditingLayout(false);
    } catch (error) {
      console.error('[AIComponentManagementView] save role-card-configs error:', error);
      setRoleCardsError('保存失败，请稍后重试');
    } finally {
      setIsSavingRoleCards(false);
    }
  };

  const normalizedDraftLayouts = useMemo(() => {
    return roleOptions.reduce<Record<string, string[]>>((acc, role) => {
      const roleCode = role.code;
      if (Array.isArray(draftLayouts[roleCode])) {
        acc[roleCode] = draftLayouts[roleCode];
        return acc;
      }

      acc[roleCode] = roleCode === selectedRole ? roleCardIdList : [];
      return acc;
    }, {});
  }, [draftLayouts, roleCardIdList, roleOptions, selectedRole]);

  const baseGroups = useMemo(() => {
    const fromCards = cards
      .map((item) => item.category?.trim())
      .filter((item): item is string => Boolean(item));
    const fromGroupApi = cardGroups
      .map((item) => item.groupName?.trim())
      .filter((item): item is string => Boolean(item));
    return Array.from(new Set([...fromCards, ...fromGroupApi].filter((item) => item !== '全部')));
  }, [cards, cardGroups]);

  const groupTabs = useMemo(
    () => ['全部', ...Array.from(new Set([...baseGroups, ...customGroups]))],
    [baseGroups, customGroups],
  );

  const groupOptions = useMemo(
    () =>
      cardGroups
        .map((item) => ({
          id: item.id?.trim() || '',
          name: item.groupName?.trim() || '',
        }))
        .filter((item): item is { id: string; name: string } => Boolean(item.id && item.name)),
    [cardGroups],
  );

  const editingGroupId = useMemo(() => {
    if (!editingCard) return '';
    const rawValue = editingCard.category?.trim() || '';
    if (!rawValue) return '';

    const byId = cardGroups.find((group) => group.id?.trim() === rawValue);
    if (byId?.id) {
      return byId.id.trim();
    }

    const byName = cardGroups.find((group) => group.groupName?.trim() === rawValue);
    return byName?.id?.trim() || '';
  }, [editingCard, cardGroups]);

  const handleGroupChange = async (groupName: string, explicitGroupId?: string) => {
    setActiveGroup(groupName);
    setGroupCardsError('');

    if (groupName === '全部') {
      setIsLoadingGroupCards(false);
      setActiveGroupCardIds([]);
      return;
    }

    const groupId =
      explicitGroupId?.trim() ||
      cardGroups.find((group) => group.groupName?.trim() === groupName)?.id?.trim() ||
      '';

    if (!groupId) {
      setIsLoadingGroupCards(false);
      setActiveGroupCardIds([]);
      setGroupCardsError('未找到该分组的ID，暂无法加载分组卡片');
      return;
    }

    const requestSeq = groupCardsRequestSeqRef.current + 1;
    groupCardsRequestSeqRef.current = requestSeq;

    try {
      setIsLoadingGroupCards(true);
      const relationList = await aiComponentViewApi.listCardGroupRelationsByGroup(groupId);
      if (groupCardsRequestSeqRef.current !== requestSeq) {
        return;
      }

      const nextCardIds = Array.from(
        new Set(
          (Array.isArray(relationList) ? relationList : [])
            .map((item) => item.cardConfigId?.trim())
            .filter((item): item is string => Boolean(item)),
        ),
      );
      setActiveGroupCardIds(nextCardIds);
    } catch (error) {
      if (groupCardsRequestSeqRef.current !== requestSeq) {
        return;
      }
      console.error('[AIComponentManagementView] query card-group-relations by group error:', error);
      setActiveGroupCardIds([]);
      setGroupCardsError('分组卡片加载失败，请稍后重试');
    } finally {
      if (groupCardsRequestSeqRef.current === requestSeq) {
        setIsLoadingGroupCards(false);
      }
    }
  };

  const displayedCards = useMemo(() => {
    if (activeGroup === '全部') {
      return cards;
    }

    if (activeGroupCardIds.length === 0) {
      return [];
    }

    const visibleCardIdSet = new Set(activeGroupCardIds);
    return cards.filter((card) => visibleCardIdSet.has(card.id));
  }, [activeGroup, activeGroupCardIds, cards]);

  const handleCreateCategory = async () => {
    const nextGroup = newCategoryName.trim();
    if (!nextGroup) {
      setCategoryError('请输入分组名称');
      return;
    }
    if (nextGroup === '全部') {
      setCategoryError('分组名称不能为“全部”');
      return;
    }
    if (groupTabs.includes(nextGroup)) {
      setCategoryError('分组名称已存在');
      return;
    }

    try {
      setIsCreatingCategory(true);
      setCategoryError('');
      const created = await aiComponentViewApi.createCardGroup(nextGroup);
      const savedGroupName = created?.groupName?.trim() || nextGroup;

      setCustomGroups((prev) => (prev.includes(savedGroupName) ? prev : [...prev, savedGroupName]));
      setCardGroups((prev) => {
        const createdGroup: CardGroup = {
          ...created,
          groupName: savedGroupName,
        };
        const createdGroupId = createdGroup.id?.trim();
        if (createdGroupId && prev.some((item) => item.id?.trim() === createdGroupId)) {
          return prev;
        }
        if (prev.some((item) => item.groupName?.trim() === savedGroupName)) {
          return prev;
        }
        return [createdGroup, ...prev];
      });
      await handleGroupChange(savedGroupName, created?.id?.trim() || '');
      setNewCategoryName('');
      setIsCategoryModalOpen(false);
    } catch (error) {
      console.error('[AIComponentManagementView] create card-group error:', error);
      setCategoryError('新增分组失败，请稍后重试');
    } finally {
      setIsCreatingCategory(false);
    }
  };

  const handleSaveCard = async (updatedCard: CardConfig) => {
    const selectedGroupId = updatedCard.category?.trim();
    const targetGroup = cardGroups.find((group) => group.id?.trim() === selectedGroupId);
    const groupId = targetGroup?.id?.trim() || selectedGroupId;

    if (!groupId) {
      setSaveCardError('请选择有效分组后再保存');
      return;
    }

    try {
      setIsSavingCard(true);
      setSaveCardError('');
      await aiComponentViewApi.createCardGroupRelation({
        groupId,
        cardConfigId: updatedCard.id,
      });
      const nextCategory = targetGroup?.groupName?.trim() || updatedCard.category;
      setCards((prev) =>
        prev.map((c) =>
          c.id === updatedCard.id
            ? {
              ...updatedCard,
              category: nextCategory,
            }
            : c,
        ),
      );
      setEditingCard(null);
    } catch (error) {
      console.error('[AIComponentManagementView] save card relation error:', error);
      setSaveCardError('保存失败，请稍后重试');
    } finally {
      setIsSavingCard(false);
    }
  };

  const groupStatusMessage = useMemo(() => {
    if (isLoadingGroups) return '正在加载卡片分组...';
    if (groupError) return groupError;
    if (isLoadingGroupCards) return '正在加载分组卡片...';
    if (groupCardsError) return groupCardsError;
    return '';
  }, [groupCardsError, groupError, isLoadingGroupCards, isLoadingGroups]);

  const renderCardContent = (card: CardConfig, onEdit?: () => void) => {
    switch (card.type) {
      // case 'asset-info': return <AssetCard title={card.title} onEdit={onEdit} />;
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
            onClick={() => {
              setIsCategoryModalOpen(true);
              setNewCategoryName('');
              setCategoryError('');
            }}
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
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 gap-3">
              <div className="flex space-x-6 overflow-x-auto custom-scrollbar">
                {groupTabs.map((group) => {
                  const isActive = activeGroup === group;
                  return (
                    <button
                      key={group}
                      type="button"
                      onClick={() => {
                        void handleGroupChange(group);
                      }}
                      className={`pb-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${isActive
                        ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                        : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                        }`}
                    >
                      {group}
                    </button>
                  );
                })}
              </div>
            </div>

            {groupStatusMessage && (
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
                {groupStatusMessage}
              </div>
            )}

            <div className="columns-1 md:columns-2 xl:columns-3 2xl:columns-4 gap-6">
              {displayedCards.map(card => (
                <CardWrapper key={card.id} card={card} />
              ))}
              {!isLoadingGroups && !isLoadingGroupCards && displayedCards.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
                  暂无可展示的卡片数据
                </div>
              )}
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
                  {roleOptions.map((role) => (
                    <button
                      key={role.code}
                      onClick={() => setSelectedRole(role.code)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${selectedRole === role.code
                        ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-500/30'
                        : 'bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'
                        }`}
                      disabled={isLoadingRoles}
                    >
                      {role.name}
                    </button>
                  ))}
                </div>
                <div className="h-6 w-px bg-slate-200 dark:bg-slate-700"></div>
                {!isEditingLayout ? (
                  <button
                    onClick={() => {
                      setDraftLayouts((prev) => ({
                        ...prev,
                        [selectedRole]: roleCardIdList,
                      }));
                      setIsEditingLayout(true);
                    }}
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
                      onClick={() => {
                        void handleSaveRoleCards();
                      }}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors flex items-center"
                      disabled={isSavingRoleCards}
                    >
                      <Save className="w-4 h-4 mr-1.5" />
                      {isSavingRoleCards ? '保存中...' : '保存'}
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-4">
              {rolesError && (
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
                  {rolesError}
                </div>
              )}
              {(isLoadingRoleCards || roleCardsError) && (
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
                  {isLoadingRoleCards ? '正在加载角色卡片配置...' : roleCardsError}
                </div>
              )}
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                {isEditingLayout
                  ? `正在编辑 ${selectedRoleName} 角色的默认布局，点击卡片进行勾选或取消。`
                  : `配置 ${selectedRoleName} 角色在“我的AI工作台”中默认展示的卡片。`
                }
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {cards.map(card => {
                  const draftSelectedIds = normalizedDraftLayouts[selectedRole] ?? [];
                  const isSelected = isEditingLayout
                    ? draftSelectedIds.includes(card.id)
                    : roleCardIdSet.has(card.id);
                  return (
                    <div
                      key={card.id}
                      onClick={() => {
                        if (!isEditingLayout) return;
                        const currentLayout = normalizedDraftLayouts[selectedRole] ?? [];
                        const newLayout = isSelected
                          ? currentLayout.filter(id => id !== card.id)
                          : [...currentLayout, card.id];
                        setDraftLayouts({ ...draftLayouts, [selectedRole]: newLayout });
                      }}
                      className={`p-4 rounded-xl border-2 transition-all ${isEditingLayout ? 'cursor-pointer' : 'cursor-default'} ${isSelected
                        ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-500/5'
                        : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800'
                        } ${isEditingLayout && !isSelected ? 'hover:border-blue-300 dark:hover:border-blue-700' : ''}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className={`font-medium ${isSelected ? 'text-blue-700 dark:text-blue-400' : 'text-slate-800 dark:text-slate-200'}`}>{card.title}</span>
                        <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-colors ${isSelected ? 'border-blue-500 bg-blue-500' : 'border-slate-300 dark:border-slate-600'
                          } ${!isEditingLayout && !isSelected ? 'opacity-50' : ''}`}>
                          {isSelected && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                        </div>
                      </div>
                      <div className="space-y-1">
                        <span className="block text-xs text-slate-500 dark:text-slate-400">
                          {card.category || '全部'}
                        </span>
                      </div>
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

      {isCategoryModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl dark:bg-slate-800">
            <div className="flex items-center justify-between border-b border-slate-100 p-6 dark:border-slate-700/50">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">新增分组</h3>
              <button
                onClick={() => {
                  if (isCreatingCategory) return;
                  setIsCategoryModalOpen(false);
                  setNewCategoryName('');
                  setCategoryError('');
                }}
                className="text-slate-400 hover:text-slate-500 disabled:opacity-50"
                disabled={isCreatingCategory}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-3">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">分组名称</label>
              <input
                type="text"
                value={newCategoryName}
                onChange={(e) => {
                  setNewCategoryName(e.target.value);
                  if (categoryError) setCategoryError('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    void handleCreateCategory();
                  }
                }}
                placeholder="请输入分组名称"
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-slate-900 outline-none focus:ring-2 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                disabled={isCreatingCategory}
              />
              {categoryError && (
                <p className="text-xs text-red-500">{categoryError}</p>
              )}
            </div>
            <div className="flex items-center justify-end space-x-3 border-t border-slate-100 p-6 dark:border-slate-700/50">
              <button
                onClick={() => {
                  if (isCreatingCategory) return;
                  setIsCategoryModalOpen(false);
                  setNewCategoryName('');
                  setCategoryError('');
                }}
                className="rounded-lg px-4 py-2 text-slate-600 transition-colors hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-700 disabled:opacity-50"
                disabled={isCreatingCategory}
              >
                取消
              </button>
              <button
                onClick={() => void handleCreateCategory()}
                className="rounded-lg bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isCreatingCategory}
              >
                {isCreatingCategory ? '提交中...' : '确认新增'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Card Modal */}
      {editingCard && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between p-6 border-b border-slate-100 dark:border-slate-700/50">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">编辑卡片</h3>
              <button
                onClick={() => {
                  if (isSavingCard) return;
                  setEditingCard(null);
                  setSaveCardError('');
                }}
                className="text-slate-400 hover:text-slate-500 disabled:opacity-50"
                disabled={isSavingCard}
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">所属分组</label>
                <select
                  value={editingGroupId}
                  onChange={e => {
                    setEditingCard({ ...editingCard, category: e.target.value });
                    if (saveCardError) setSaveCardError('');
                  }}
                  className="w-full px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-slate-900 dark:text-white"
                  disabled={isSavingCard}
                >
                  <option value="">请选择分组</option>
                  {groupOptions.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
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
                  disabled={isSavingCard}
                />
              </div>
              {saveCardError && (
                <p className="text-xs text-red-500">{saveCardError}</p>
              )}
              <div className="bg-blue-50 dark:bg-blue-500/10 p-4 rounded-lg">
                <p className="text-xs text-blue-600 dark:text-blue-400">提示：卡片内的数据内容为系统自动回传，不可手动更改。</p>
              </div>
            </div>
            <div className="flex items-center justify-end p-6 border-t border-slate-100 dark:border-slate-700/50 space-x-3">
              <button
                onClick={() => {
                  if (isSavingCard) return;
                  setEditingCard(null);
                  setSaveCardError('');
                }}
                className="px-4 py-2 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
                disabled={isSavingCard}
              >
                取消
              </button>
              <button
                onClick={() => void handleSaveCard(editingCard)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isSavingCard}
              >
                <Save className="w-4 h-4 mr-2" />
                {isSavingCard ? '保存中...' : '保存修改'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
