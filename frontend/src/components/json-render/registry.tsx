import { createRenderer, useBoundProp } from '@json-render/react';
import { Children, isValidElement, type ReactNode, useEffect, useMemo, useState } from 'react';
import { Descriptions, Pagination, Table } from 'antd';
import {
  Activity,
  AlertTriangle,
  Calendar,
  CheckCircle2,
  ClipboardList,
  Clock,
  Coffee,
  CreditCard,
  FileText,
  Gem,
  Heart,
  MessageSquare,
  Moon,
  Network,
  Package,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Star,
  Stethoscope,
  Target,
  TrendingUp,
  Unlock,
  User,
  Users,
  Utensils,
  Wallet,
} from 'lucide-react';
import { apiClient } from '../../services/api';
import { assistantCatalog } from './catalog';

interface DictOption {
  label: string;
  value: string;
}

const dictCache = new Map<string, DictOption[]>();
const EMPTY_ROWS: any[] = [];
const PLANNER_TABLE_ROW_KEY = '__plannerTableRowKey';
const PLANNER_TABLE_RAW_RECORD = '__plannerTableRawRecord';

const uiTokens = {
  cardShell:
    'mb-6 rounded-2xl border border-slate-200/80 bg-gradient-to-b from-white to-slate-50/30 p-5 shadow-[0_2px_10px_-3px_rgba(0,0,0,0.05)] dark:border-slate-700/70 dark:from-slate-800 dark:to-slate-800/60',
  cardHeader: 'mb-4 border-b border-slate-100 pb-3 dark:border-slate-700/60',
  headerAccent: 'h-4 w-1.5 rounded-full bg-blue-500',
  headerTitle: 'font-bold text-slate-800 dark:text-slate-100',
  headerSubtitle: 'mt-1 text-xs text-slate-500 dark:text-slate-400',
  headerBadge: 'rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-medium text-blue-600 dark:bg-blue-900/30 dark:text-blue-200',
  fieldLabel: 'text-sm text-slate-500 dark:text-slate-400',
  fieldValue: 'text-sm font-medium text-slate-900 dark:text-slate-100',
  fieldValueXs: 'text-xs text-slate-500 dark:text-slate-400',
  sectionTitle: 'text-sm font-bold text-slate-800 dark:text-slate-100',
  noteShell: 'rounded-xl border p-4 text-sm leading-relaxed',
  tableShell: 'rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700/70 dark:bg-slate-800/80',
  tableTitle: 'mb-3 text-[13px] font-bold text-slate-700 dark:text-slate-100',
  tableClassName:
    'text-xs [&_.ant-table]:bg-transparent [&_.ant-table-container]:border [&_.ant-table-container]:border-slate-100 [&_.ant-table-container]:rounded-lg [&_.ant-table-thead>tr>th]:bg-slate-50 [&_.ant-table-thead>tr>th]:text-slate-500 [&_.ant-table-thead>tr>th]:font-semibold [&_.ant-table-tbody>tr>td]:border-slate-100 dark:[&_.ant-table-container]:border-slate-700 dark:[&_.ant-table-thead>tr>th]:bg-slate-700/70 dark:[&_.ant-table-thead>tr>th]:text-slate-200 dark:[&_.ant-table-tbody>tr>td]:border-slate-700 dark:[&_.ant-table-tbody>tr>td]:text-slate-100',
};

const toneClassMap: Record<string, string> = {
  neutral:
    'from-slate-50 to-slate-100/50 border-slate-200 text-slate-600 dark:from-slate-800/60 dark:to-slate-700/30 dark:border-slate-700/70 dark:text-slate-300',
  slate:
    'from-slate-50 to-slate-100/50 border-slate-200 text-slate-600 dark:from-slate-800/60 dark:to-slate-700/30 dark:border-slate-700/70 dark:text-slate-300',
  blue:
    'from-blue-50 to-blue-100/50 border-blue-100 text-blue-600 dark:from-blue-900/20 dark:to-blue-800/10 dark:border-blue-800/40 dark:text-blue-300',
  emerald:
    'from-emerald-50 to-emerald-100/50 border-emerald-100 text-emerald-600 dark:from-emerald-900/20 dark:to-emerald-800/10 dark:border-emerald-800/40 dark:text-emerald-300',
  amber:
    'from-amber-50 to-amber-100/50 border-amber-100 text-amber-600 dark:from-amber-900/20 dark:to-amber-800/10 dark:border-amber-800/40 dark:text-amber-300',
  rose:
    'from-rose-50 to-rose-100/50 border-rose-100 text-rose-600 dark:from-rose-900/20 dark:to-rose-800/10 dark:border-rose-800/40 dark:text-rose-300',
  purple:
    'from-purple-50 to-purple-100/50 border-purple-100 text-purple-600 dark:from-purple-900/20 dark:to-purple-800/10 dark:border-purple-800/40 dark:text-purple-300',
  cyan:
    'from-cyan-50 to-cyan-100/50 border-cyan-100 text-cyan-600 dark:from-cyan-900/20 dark:to-cyan-800/10 dark:border-cyan-800/40 dark:text-cyan-300',
  indigo:
    'from-indigo-50 to-indigo-100/50 border-indigo-100 text-indigo-600 dark:from-indigo-900/20 dark:to-indigo-800/10 dark:border-indigo-800/40 dark:text-indigo-300',
};

const iconMap = {
  user: User,
  users: Users,
  clipboardList: ClipboardList,
  stethoscope: Stethoscope,
  wallet: Wallet,
  clipboard: FileText,
  activity: Activity,
  network: Network,
  unlock: Unlock,
  clock: Clock,
  checkCircle: CheckCircle2,
  trendingUp: TrendingUp,
  creditCard: CreditCard,
  package: Package,
  utensils: Utensils,
  moon: Moon,
  coffee: Coffee,
  heart: Heart,
  star: Star,
  target: Target,
  fileText: FileText,
  messageSquare: MessageSquare,
  alertTriangle: AlertTriangle,
  calendar: Calendar,
  shoppingBag: ShoppingBag,
  gem: Gem,
  shieldCheck: ShieldCheck,
  settings: Settings,
};

function getIconByName(name?: string | null) {
  if (!name) {
    return null;
  }
  return iconMap[name as keyof typeof iconMap] ?? null;
}

function formatDisplayValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '-';
  }
  return String(value);
}

function buildPlannerTableRowKey(record: unknown, index: number) {
  if (record && typeof record === 'object' && !Array.isArray(record)) {
    const row = record as Record<string, unknown>;
    const idLikeKey = row.id ?? row.uid ?? row.key;
    if (idLikeKey !== null && idLikeKey !== undefined && String(idLikeKey).trim() !== '') {
      return String(idLikeKey);
    }
    return `${JSON.stringify(record)}__${index}`;
  }

  return `${String(record)}__${index}`;
}

function attachPlannerTableRowKeys(rows: any[]) {
  return rows.map((row, index) => {
    const rowKey = buildPlannerTableRowKey(row, index);
    if (row && typeof row === 'object' && !Array.isArray(row)) {
      return {
        ...row,
        [PLANNER_TABLE_ROW_KEY]: rowKey,
        [PLANNER_TABLE_RAW_RECORD]: row,
      };
    }

    return {
      value: row,
      [PLANNER_TABLE_ROW_KEY]: rowKey,
      [PLANNER_TABLE_RAW_RECORD]: row,
    };
  });
}

function isFormActionNode(node: ReactNode): boolean {
  if (!isValidElement(node)) {
    return false;
  }
  return (node.props as { ['data-planner-role']?: string })['data-planner-role'] === 'form-action';
}

async function fetchDictOptions(dictCode: string): Promise<DictOption[]> {
  if (dictCache.has(dictCode)) {
    return dictCache.get(dictCode)!;
  }
  try {
    const res = await apiClient.get<{
      data: Array<{ dictLabel: string; dictValue: string }>;
    }>(`/api/v1/system/dict/data/type/${dictCode}`);

    const options: DictOption[] = (res.data.data ?? []).map((item) => ({
      label: item.dictLabel,
      value: item.dictValue,
    }));
    dictCache.set(dictCode, options);
    return options;
  } catch (err) {
    console.error(`[PlannerSelect] 字典加载失败 (${dictCode}):`, err);
    return [];
  }
}

export const AssistantRenderer = createRenderer(assistantCatalog, {
  PlannerCard: ({ element, children }) => {
    const { title, subtitle, headerRightText } = element.props;
    return (
      <div className={uiTokens.cardShell}>
        <div className={uiTokens.cardHeader}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className={uiTokens.headerAccent} />
              <h4 className={uiTokens.headerTitle}>{title}</h4>
            </div>
            {headerRightText ? (
              <span className={uiTokens.headerBadge}>
                {headerRightText}
              </span>
            ) : null}
          </div>
          {subtitle ? <p className={uiTokens.headerSubtitle}>{subtitle}</p> : null}
        </div>
        <div className="space-y-3">{children}</div>
      </div>
    );
  },

  PlannerBlankContainer: ({ element, children }) => {
    const { minHeight } = element.props;
    return (
      <div
        className="rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-600"
        style={{ minHeight: Number(minHeight) > 0 ? Number(minHeight) : undefined }}
      >
        {children}
      </div>
    );
  },

  PlannerMetric: ({ element }) => {
    const { label, value } = element.props;
    return (
      <div className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
        <span className={uiTokens.fieldValueXs}>{label}</span>
        <span className="text-xs font-bold text-slate-700">{formatDisplayValue(value)}</span>
      </div>
    );
  },

  PlannerMetricTiles: ({ element }) => {
    const { tiles = [], minColumnWidth } = element.props;
    const columnWidth = Math.max(Number(minColumnWidth) || 140, 120);
    return (
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${columnWidth}px, 1fr))` }}
      >
        {tiles.map((tile: any, index: number) => {
          const tone = toneClassMap[tile.tone ?? 'blue'] ?? toneClassMap.blue;
          const Icon = getIconByName(tile.icon);
          return (
            <div
              key={`${tile.label}-${index}`}
              className={`relative overflow-hidden rounded-2xl border bg-gradient-to-br p-4 transition-all hover:shadow-md ${tone}`}
            >
              {Icon ? (
                <div className="absolute -right-4 -bottom-4 opacity-5 transition-opacity duration-500 hover:opacity-10">
                  <Icon className="h-20 w-20" />
                </div>
              ) : null}
              <div className={`relative z-10 mb-2 ${uiTokens.fieldLabel}`}>{tile.label}</div>
              <div className="relative z-10 text-2xl font-bold text-slate-900">{formatDisplayValue(tile.value)}</div>
              {tile.desc ? <div className={`relative z-10 mt-1 ${uiTokens.fieldValueXs}`}>{tile.desc}</div> : null}
            </div>
          );
        })}
      </div>
    );
  },

  PlannerInfoGrid: ({ element }) => {
    const { items = [], minColumnWidth } = element.props;
    const columnWidth = Math.max(Number(minColumnWidth) || 150, 120);
    return (
      <div
        className="grid gap-x-4 gap-y-4"
        style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${columnWidth}px, 1fr))` }}
      >
        {items.map((item: any, index: number) => (
          <div key={`${item.label}-${index}`} className="flex flex-col space-y-1">
            <span className={uiTokens.fieldLabel}>{item.label}</span>
            <span className={`truncate ${uiTokens.fieldValue}`} title={String(item.value ?? '')}>
              {formatDisplayValue(item.value)}
            </span>
          </div>
        ))}
      </div>
    );
  },

  PlannerSectionBlocks: ({ element }) => {
    const { sections = [], minColumnWidth } = element.props;
    const sectionColumnWidth = Math.max(Number(minColumnWidth) || 260, 220);

    return (
      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${sectionColumnWidth}px, 1fr))` }}
      >
        {sections.map((section: any, idx: number) => {
          const tone = toneClassMap[section.tone ?? 'blue'] ?? toneClassMap.blue;
          const Icon = getIconByName(section.icon);
          return (
            <div
              key={`${section.title}-${idx}`}
              className={`rounded-xl border bg-gradient-to-br p-4 ${tone}`}
            >
              <div className="mb-4 flex items-center space-x-2">
                {Icon ? (
                  <span className="rounded-lg bg-white/70 p-1.5">
                    <Icon className="h-4 w-4" />
                  </span>
                ) : null}
                <h5 className={uiTokens.sectionTitle}>{section.title}</h5>
              </div>
              <div className="grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-4">
                {(section.items ?? []).map((item: any, itemIdx: number) => (
                  <div key={`${item.label}-${itemIdx}`} className="flex flex-col space-y-1">
                    <span className={uiTokens.fieldValueXs}>{item.label}</span>
                    <span className={uiTokens.fieldValue}>{formatDisplayValue(item.value)}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  },

  PlannerHighlightNote: ({ element }) => {
    const { text, tone } = element.props;
    const toneClass =
      tone === 'success'
        ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
        : tone === 'warning'
          ? 'bg-amber-50 text-amber-700 border-amber-100'
          : tone === 'neutral'
            ? 'bg-slate-50 text-slate-700 border-slate-200'
            : 'bg-blue-50 text-blue-700 border-blue-100';

    return <div className={`${uiTokens.noteShell} ${toneClass}`}>{text}</div>;
  },

  PlannerOwnerMeta: ({ element }) => {
    const {
      name,
      executionDate,
      lastUpdateDate,
      executionLabel = '执行日期',
      updateLabel = '最近更新',
    } = element.props;

    return (
      <div className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 p-4">
        <div className="flex items-center space-x-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-600">
            {formatDisplayValue(name).charAt(0)}
          </div>
          <div>
            <div className={uiTokens.fieldLabel}>负责人</div>
            <div className={uiTokens.fieldValue}>{formatDisplayValue(name)}</div>
          </div>
        </div>
        <div className="space-y-1 text-right">
          <div>
            <span className={`mr-2 ${uiTokens.fieldLabel}`}>{executionLabel}</span>
            <span className={uiTokens.fieldValue}>{formatDisplayValue(executionDate)}</span>
          </div>
          <div>
            <span className={`mr-2 ${uiTokens.fieldLabel}`}>{updateLabel}</span>
            <span className="text-sm text-slate-900">{formatDisplayValue(lastUpdateDate)}</span>
          </div>
        </div>
      </div>
    );
  },

  PlannerForm: ({ element, children }) => {
    const { formCode } = element.props;
    const childArray = Children.toArray(children);
    const actionNodes = childArray.filter((node) => isFormActionNode(node));
    const fieldNodes = childArray.filter((node) => !isFormActionNode(node));

    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
        <form data-planner-form={formCode} onSubmit={(event) => event.preventDefault()} className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{fieldNodes}</div>
          {actionNodes.length > 0 ? (
            <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 pt-3">{actionNodes}</div>
          ) : null}
        </form>
      </div>
    );
  },

  PlannerInput: ({ element, bindings }) => {
    const { label, placeholder, required } = element.props;
    const [boundValue, setBoundValue] = useBoundProp<string | number | Record<string, unknown> | null>(
      element.props.value,
      bindings?.value,
    );
    const value = typeof boundValue === 'string' || typeof boundValue === 'number' ? String(boundValue) : '';
    const currentValueIsNumber = typeof boundValue === 'number';

    return (
      <label className="block rounded-xl border border-slate-200 bg-white px-3 py-2">
        <span className="block text-[11px] font-semibold text-slate-500">
          {label}
          {required ? <span className="ml-1 text-rose-500">*</span> : null}
        </span>
        <input
          value={value}
          required={Boolean(required)}
          onChange={(event) => {
            const nextValue = event.target.value;
            if (currentValueIsNumber) {
              const parsedValue = Number(nextValue);
              setBoundValue(Number.isNaN(parsedValue) ? null : parsedValue);
              return;
            }
            setBoundValue(nextValue);
          }}
          placeholder={placeholder ?? ''}
          className="mt-1 w-full border-0 bg-transparent text-xs text-slate-700 focus:outline-none"
        />
      </label>
    );
  },

  PlannerButton: ({ element, emit }) => {
    const label = element.props.label;
    const isSecondaryAction = /重置|取消|返回/i.test(label);

    return (
      <button
        type="button"
        data-planner-role="form-action"
        onClick={() => emit('press')}
        className={
          isSecondaryAction
            ? 'rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 transition-colors hover:bg-slate-50'
            : 'rounded-xl bg-brand px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-brand-dark'
        }
      >
        {label}
      </button>
    );
  },

  PlannerNotice: ({ element }) => {
    const { text, tone } = element.props;
    const className =
      tone === 'success'
        ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
        : tone === 'warning'
          ? 'bg-amber-50 text-amber-700 border-amber-100'
          : 'bg-brand/10 text-brand border-brand/15';

    return <div className={`rounded-xl border px-3 py-2 text-xs font-medium ${className}`}>{text}</div>;
  },

  PlannerSelect: ({ element, bindings }) => {
    const { label, dictCode, placeholder } = element.props;
    const [options, setOptions] = useState<DictOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
      if (!dictCode) {
        return;
      }
      setLoading(true);
      setError(false);
      fetchDictOptions(String(dictCode))
        .then((opts) => {
          setOptions(opts);
          setLoading(false);
        })
        .catch(() => {
          setError(true);
          setLoading(false);
        });
    }, [dictCode]);

    const [boundValue, setBoundValue] = useBoundProp<string | Record<string, unknown> | null>(
      element.props.value,
      bindings?.value,
    );
    const selectedValue = typeof boundValue === 'string' ? boundValue : '';

    return (
      <label className="block rounded-xl border border-slate-200 bg-white px-3 py-2">
        <span className="block text-[11px] font-semibold text-slate-500">{label}</span>
        <select
          value={selectedValue}
          onChange={(event) => setBoundValue(event.target.value)}
          disabled={loading || error}
          className="mt-1 w-full border-0 bg-transparent text-xs text-slate-700 focus:outline-none disabled:opacity-50"
        >
          <option value="" disabled>
            {loading ? '加载中…' : error ? '选项加载失败' : placeholder ?? '请选择'}
          </option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    );
  },

  PlannerTable: ({ element, bindings, emit }) => {
    const {
      title,
      api,
      columns = [],
      dataSource,
      rows,
      rowActions,
      total: staticTotal,
      pageSize: pageSizeProp,
      pageParam = 'pageNum',
      pageSizeParam = 'pageSize',
      queryParams = {},
      body = {},
      bizFieldKey
    } = element.props;

    const sourceRows = useMemo(() => {
      if (Array.isArray(rows)) {
        return rows;
      }
      if (Array.isArray(dataSource)) {
        return dataSource;
      }
      return EMPTY_ROWS;
    }, [rows, dataSource]);
    const normalizedRows = useMemo(() => attachPlannerTableRowKeys(sourceRows), [sourceRows]);

    const [data, setData] = useState<any[]>(normalizedRows);
    const [total, setTotal] = useState(typeof staticTotal === 'number' ? staticTotal : normalizedRows.length);
    const [hasPaginationMeta, setHasPaginationMeta] = useState(typeof staticTotal === 'number');
    const [loading, setLoading] = useState(false);
    const pageSize = Number(pageSizeProp) > 0 ? Number(pageSizeProp) : 10;

    const [boundPage, setBoundPage] = useBoundProp<number | Record<string, unknown> | null>(
      element.props.currentPage,
      bindings?.currentPage,
    );
    const page = typeof boundPage === 'number' ? boundPage : 1;
    const queryParamsKey = useMemo(() => JSON.stringify(queryParams ?? {}), [queryParams]);
    const bodyKey = useMemo(() => JSON.stringify(body ?? {}), [body]);

    useEffect(() => {
      if (api) {
        return;
      }

      setData(normalizedRows);
      setTotal(typeof staticTotal === 'number' ? staticTotal : normalizedRows.length);
      setHasPaginationMeta(typeof staticTotal === 'number');
    }, [api, normalizedRows, staticTotal]);

    useEffect(() => {
      if (!api) {
        return;
      }

      let active = true;
      setLoading(true);

      apiClient
        .post(api, {
          queryParams: {
            ...queryParams,
            [pageParam]: page,
            [pageSizeParam]: pageSize,
          },
          body,
        })
        .then((res) => {
          if (!active) {
            return;
          }

          const records =
            res.data?.data?.rows ??
            res.data?.data?.result ??
            res.data?.data?.data?.records ??
            res.data?.rows ??
            res.data?.data ??
            [];

          const nextRows = Array.isArray(records)
            ? records
            : (bizFieldKey && Array.isArray((records as Record<string, unknown>)[bizFieldKey]))
              ? ((records as Record<string, unknown>)[bizFieldKey] as any[])
              : EMPTY_ROWS;

          const rawTotalCount = res.data?.data?.total ?? res.data?.total;
          const hasServerPagination =
            rawTotalCount !== undefined ||
            res.data?.data?.pageNo !== undefined ||
            res.data?.data?.pageNum !== undefined ||
            res.data?.pageNo !== undefined ||
            res.data?.pageNum !== undefined ||
            res.data?.data?.pages !== undefined ||
            res.data?.pages !== undefined;
          const totalCount = rawTotalCount ?? nextRows.length;

          setData(attachPlannerTableRowKeys(nextRows));
          setHasPaginationMeta(hasServerPagination || typeof staticTotal === 'number');
          setTotal(typeof totalCount === 'number' ? totalCount : Number(totalCount) || 0);
          setLoading(false);
        })
        .catch((err) => {
          console.error('表格数据获取失败:', err);
          if (active) {
            setLoading(false);
          }
        });

      return () => {
        active = false;
      };
    }, [api, bodyKey, page, pageParam, pageSize, pageSizeParam, queryParamsKey, title, bizFieldKey]);

    useEffect(() => {
      const handleDataUpdate = (event: Event) => {
        const customEvent = event as CustomEvent;
        const resData = customEvent.detail?.resData;
        if (!resData) {
          return;
        }
        const records =
          resData?.data?.rows ??
          resData?.data?.data?.records ??
          resData?.rows ??
          resData?.data ??
          [];
        const totalCount =
          resData?.data?.total ??
          resData?.total ??
          (Array.isArray(records) ? records.length : 0);
        const hasServerPagination =
          resData?.data?.total !== undefined ||
          resData?.total !== undefined ||
          resData?.data?.pageNo !== undefined ||
          resData?.data?.pageNum !== undefined ||
          resData?.pageNo !== undefined ||
          resData?.pageNum !== undefined ||
          resData?.data?.pages !== undefined ||
          resData?.pages !== undefined;
        setData(attachPlannerTableRowKeys(Array.isArray(records) ? records : []));
        setHasPaginationMeta(hasServerPagination || typeof staticTotal === 'number');
        setTotal(typeof totalCount === 'number' ? totalCount : 0);
      };

      window.addEventListener('planner:table-data-update', handleDataUpdate);
      return () => window.removeEventListener('planner:table-data-update', handleDataUpdate);
    }, []);

    const tableColumns = useMemo(() => {
      const cols = Array.isArray(columns) ? [...columns] : [];
      if (Array.isArray(rowActions) && rowActions.length > 0) {
        cols.push({
          title: '操作',
          key: 'action',
          render: (_: unknown, record: any) => (
            <div className="flex gap-3">
              {rowActions.map((action: any, idx: number) => (
                <button
                  key={idx}
                  type="button"
                  className="text-brand text-[11px] font-bold transition-colors hover:text-brand-dark hover:underline"
                  onClick={() => emit(action.type || 'remoteQuery', { record: record?.[PLANNER_TABLE_RAW_RECORD] ?? record, action })}
                >
                  {action.label}
                </button>
              ))}
            </div>
          ),
        });
      }
      return cols;
    }, [columns, rowActions, emit]);

    const tablePagination = hasPaginationMeta
      ? {
        current: page,
        pageSize,
        total,
        onChange: (newPage: number) => setBoundPage(newPage),
        showSizeChanger: false,
      }
      : false;

    return (
      <div className={uiTokens.tableShell}>
        {title ? <h5 className={uiTokens.tableTitle}>{title}</h5> : null}
        <Table
          size="small"
          dataSource={data}
          columns={tableColumns}
          loading={loading}
          rowKey={(record: any) => record?.[PLANNER_TABLE_ROW_KEY] || record?.id || record?.uid || JSON.stringify(record)}
          pagination={tablePagination}
          scroll={hasPaginationMeta ? { x: 'max-content' } : { x: 'max-content', y: 420 }}
          className={uiTokens.tableClassName}
        />
      </div>
    );
  },

  PlannerPagination: ({ element, bindings }) => {
    const {
      enabled = true,
      total = 0,
      pageSize = 10,
    } = element.props;

    const [boundPage, setBoundPage] = useBoundProp<number | Record<string, unknown> | null>(
      element.props.currentPage,
      bindings?.currentPage,
    );
    const page = typeof boundPage === 'number' ? boundPage : 1;

    if (!enabled) {
      return null;
    }

    return (
      <div className="flex items-center justify-end rounded-xl border border-slate-200 bg-white px-3 py-2">
        <Pagination
          current={page}
          total={Number(total) || 0}
          pageSize={Number(pageSize) || 10}
          onChange={(newPage) => setBoundPage(newPage)}
          showSizeChanger={false}
          size="small"
        />
      </div>
    );
  },

  PlannerDetailCard: ({ element }) => {
    const { title, items } = element.props;
    return (
      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 border-b border-slate-100 pb-3">
          <h5 className="text-[14px] font-extrabold text-slate-800">{title || '详细资料'}</h5>
        </div>
        <Descriptions
          column={{ xxl: 3, xl: 3, lg: 2, md: 2, sm: 1, xs: 1 }}
          size="small"
          labelStyle={{ fontWeight: 600, color: '#475569', whiteSpace: 'nowrap' }}
          contentStyle={{ color: '#0F172A', wordBreak: 'break-all' }}
        >
          {items?.map((item: any, idx: number) => {
            const displayValue = item.value === '-' || !item.value ? '暂无' : item.value;
            const isLongJson =
              displayValue.length > 50 &&
              (displayValue.startsWith('{') || displayValue.startsWith('['));

            return (
              <Descriptions.Item key={idx} label={item.label} span={isLongJson ? 3 : 1}>
                {isLongJson ? (
                  <div
                    className="custom-scrollbar max-h-24 w-full overflow-y-auto rounded border border-slate-100 bg-slate-50 p-2 text-[11px]"
                    title={displayValue}
                  >
                    {displayValue}
                  </div>
                ) : (
                  <span className="text-[12px]">{displayValue}</span>
                )}
              </Descriptions.Item>
            );
          })}
        </Descriptions>
      </div>
    );
  },
});
