import { businessClient } from '../api'

/** 员工菜单节点，后端字段可能随 IAM 菜单配置略有差异，前端做宽松兼容 */
export type EmployeeMenuItem = {
  id?: string | number
  menuId?: string | number
  parentId?: string | number
  name?: string
  title?: string
  label?: string
  menuName?: string
  menuTitle?: string
  code?: string
  menuCode?: string
  permission?: string
  perms?: string
  path?: string
  route?: string
  routePath?: string
  url?: string
  icon?: string
  sort?: number
  sortOrder?: number
  orderNum?: number
  visible?: boolean | number | string
  hidden?: boolean | number | string
  status?: number | string
  children?: EmployeeMenuItem[]
  childList?: EmployeeMenuItem[]
  routes?: EmployeeMenuItem[]
  [key: string]: unknown
}

const pickEmployeeMenus = (payload: unknown): EmployeeMenuItem[] => {
  if (Array.isArray(payload)) {
    return payload as EmployeeMenuItem[]
  }

  if (!payload || typeof payload !== 'object') {
    return []
  }

  const record = payload as Record<string, unknown>
  const nestedCandidates = [
    record.data,
    record.result,
    record.records,
    record.rows,
    record.list,
    record.menus,
    record.menuList,
  ]

  for (const candidate of nestedCandidates) {
    const menus = pickEmployeeMenus(candidate)
    if (menus.length > 0) {
      return menus
    }
  }

  return []
}

/**
 * 首页/工作台相关接口
 */
export const homeApi = {
  /**
   * 获取当前员工菜单
   * GET /api/v1/auth/getEmployeeMenus
   */
  async getEmployeeMenus() {
    const response = await businessClient.get<unknown>(
      '/api/v1/auth/getEmployeeMenus',
    )
    return pickEmployeeMenus(response.data)
  },
}
