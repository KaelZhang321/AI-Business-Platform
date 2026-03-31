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

export const PAGE_PATHS = Object.fromEntries(
  Object.entries(PAGE_DEFINITIONS).map(([page, definition]) => [page, definition.path]),
) as Record<keyof typeof PAGE_DEFINITIONS, string>;

export const PAGE_TITLES = Object.fromEntries(
  Object.entries(PAGE_DEFINITIONS).map(([page, definition]) => [page, definition.title]),
) as Record<keyof typeof PAGE_DEFINITIONS, string>;

export const IMPLEMENTED_PAGES = Object.entries(PAGE_DEFINITIONS)
  .filter(([, definition]) => definition.implemented)
  .map(([page]) => page) as Array<keyof typeof PAGE_DEFINITIONS>;

export const PLACEHOLDER_PAGE_DESCRIPTIONS = Object.fromEntries(
  Object.entries(PAGE_DEFINITIONS)
    .filter(([, definition]) => Boolean(definition.placeholderDescription))
    .map(([page, definition]) => [page, definition.placeholderDescription]),
) as Partial<Record<keyof typeof PAGE_DEFINITIONS, string>>;

const PATH_TO_PAGE = new Map<string, keyof typeof PAGE_DEFINITIONS>(
  Object.entries(PAGE_DEFINITIONS).map(([page, definition]) => [definition.path, page as keyof typeof PAGE_DEFINITIONS]),
);

const NAVIGATION_GROUPS = [...NAVIGATION_ITEMS, ...FOOTER_NAVIGATION_ITEMS];

export function getPageByPath(pathname: string): keyof typeof PAGE_DEFINITIONS | null {
  return PATH_TO_PAGE.get(pathname) ?? null;
}

export function isKnownPath(pathname: string): boolean {
  return PATH_TO_PAGE.has(pathname);
}

export function isImplementedPage(page: keyof typeof PAGE_DEFINITIONS): boolean {
  return PAGE_DEFINITIONS[page].implemented;
}

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
