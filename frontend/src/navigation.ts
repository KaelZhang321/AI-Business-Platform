// 路由工具：基于导航数据源派生路径映射、标题映射以及常用查询方法。
import {
  FOOTER_NAVIGATION_ITEMS,
  NAVIGATION_ITEMS,
  PAGE_DEFINITIONS,
} from './data/navigationData';

export type {
  AppPage,
  NavigationIcon,
  NavigationItemDefinition,
  PageDefinition,
} from './data/navigationData';

export {
  FOOTER_NAVIGATION_ITEMS,
  NAVIGATION_ITEMS,
  PAGE_DEFINITIONS,
} from './data/navigationData';

/** 页面路径映射：页面标识 → URL 路径（如 'dashboard' → '/dashboard'） */
export const PAGE_PATHS = Object.fromEntries(
  Object.entries(PAGE_DEFINITIONS).map(([page, definition]) => [page, definition.path]),
) as Record<keyof typeof PAGE_DEFINITIONS, string>;

/** 页面标题映射：页面标识 → 中文名称（如 'function-square' → '功能广场'） */
export const PAGE_TITLES = Object.fromEntries(
  Object.entries(PAGE_DEFINITIONS).map(([page, definition]) => [page, definition.title]),
) as Record<keyof typeof PAGE_DEFINITIONS, string>;

/** 已实现页面列表：过滤出 implemented=true 的页面标识数组 */
export const IMPLEMENTED_PAGES = Object.entries(PAGE_DEFINITIONS)
  .filter(([, definition]) => definition.implemented)
  .map(([page]) => page) as Array<keyof typeof PAGE_DEFINITIONS>;

/** 占位页描述映射：尚未实现的页面标识 → 描述文案（用于 PlaceholderPage 展示） */
export const PLACEHOLDER_PAGE_DESCRIPTIONS = Object.fromEntries(
  Object.entries(PAGE_DEFINITIONS)
    .filter(([, definition]) => Boolean(definition.placeholderDescription))
    .map(([page, definition]) => [page, definition.placeholderDescription]),
) as Partial<Record<keyof typeof PAGE_DEFINITIONS, string>>;

/** 反向映射：URL 路径 → 页面标识，用于从浏览器地址解析当前页面 */
const PATH_TO_PAGE = new Map<string, keyof typeof PAGE_DEFINITIONS>(
  Object.entries(PAGE_DEFINITIONS).map(([page, definition]) => [definition.path, page as keyof typeof PAGE_DEFINITIONS]),
);

/** 所有导航组（主导航 + 底部导航）合并，用于判断导航分组激活态 */
const NAVIGATION_GROUPS = [...NAVIGATION_ITEMS, ...FOOTER_NAVIGATION_ITEMS];

/**
 * 根据 URL 路径查找对应的页面标识。
 * @param pathname - 当前浏览器路径
 * @returns 页面标识，未找到返回 null
 */
export function getPageByPath(pathname: string): keyof typeof PAGE_DEFINITIONS | null {
  return PATH_TO_PAGE.get(pathname) ?? null;
}

/**
 * 判断给定路径是否是已注册的页面路径。
 * @param pathname - 需要检测的 URL 路径
 */
export function isKnownPath(pathname: string): boolean {
  return PATH_TO_PAGE.has(pathname);
}

/**
 * 判断某个页面是否已有真实视图实现（非占位页）。
 * @param page - 页面标识
 */
export function isImplementedPage(page: keyof typeof PAGE_DEFINITIONS): boolean {
  return PAGE_DEFINITIONS[page].implemented;
}

/**
 * 判断侧边栏中某个导航分组是否处于激活状态。
 * 当前页面等于该分组或属于其子页面时返回 true。
 * @param currentPage - 当前活动页面标识
 * @param page - 要判断的导航分组页面标识
 */
export function isNavigationGroupActive(
  currentPage: keyof typeof PAGE_DEFINITIONS,
  page: keyof typeof PAGE_DEFINITIONS,
): boolean {
  const item = NAVIGATION_GROUPS.find((navigationItem) => navigationItem.page === page);
  if (!item) {
    return currentPage === page;
  }

  return item.page === currentPage || item.children?.includes(currentPage) === true;
}
