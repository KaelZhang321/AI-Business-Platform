import { apiClient, businessClient } from '../api'

type ApiEnvelope<T> = {
  code?: number
  message?: string
  data?: T
}

export type CardGroup = {
  id?: string
  groupName?: string
  groupSort?: number
  visibleFlag?: number
  status?: string
  remark?: string
  createdBy?: string
  createdByName?: string
  updatedBy?: string
  updatedByName?: string
  createdAt?: string
  updatedAt?: string
}

export type CardGroupQueryInput = {
  page?: number | string
  size?: number | string
  groupName?: string
  status?: string
  visibleFlag?: number
  offset?: number
  [key: string]: unknown
}

export type CardGroupPageResult = {
  data?: CardGroup[]
  total?: number
  page?: number
  size?: number
}

export type CardGroupRelation = {
  id?: string
  groupId?: string
  cardConfigId?: string
  cardSort?: number
  visibleFlag?: number
  status?: string
  remark?: string
  createdAt?: string
  updatedAt?: string
}

export type AuthRole = {
  id?: string
  appCode?: string
  roleName?: string
  roleCode?: string
  roleDesc?: string | null
  sortOrder?: number
  status?: number
  createTime?: string
  updateTime?: string
}

export type AuthRolePageResult = {
  records?: AuthRole[]
  total?: number
  size?: number
  current?: number
  pages?: number
}

export type AuthRoleQueryInput = {
  appCode?: string
  pageNo?: number
  pageSize?: number
}

export type RoleCardConfig = {
  id?: string
  roleId?: string
  roleCode?: string
  roleName?: string
  cardSchemaJson?: string
  visibleFlag?: number
  status?: string
  remark?: string
  createdBy?: string
  createdByName?: string
  updatedBy?: string
  updatedByName?: string
  createdAt?: string
  updatedAt?: string
}

export type RoleCardConfigSaveInput = {
  roleId: string
  cardSchemaJson: string
}

export type CustomerCardCustomize = {
  id?: string
  employeeId?: string
  employeeName?: string
  customerIdCard?: string
  favoriteName?: string
  cardJson?: string
  status?: string
  remark?: string
  createdAt?: string
  updatedAt?: string
  createTime?: string
  updateTime?: string
}

export type CustomerCardCustomizeCreateInput = {
  customerIdCard: string
  favoriteName: string
  cardJson: string
  status?: string
  remark?: string
}

export type CustomerCardCustomizeByCustomerQueryInput = {
  customerIdCard: string
}

export type CustomerCardCustomizeRenameInput = {
  favoriteName: string
  customerIdCard: string
}

const unwrapApiData = <T>(payload: T | ApiEnvelope<T>): T => {
  if (
    payload &&
    typeof payload === 'object' &&
    'data' in (payload as ApiEnvelope<T>) &&
    (payload as ApiEnvelope<T>).data !== undefined
  ) {
    return (payload as ApiEnvelope<T>).data as T
  }
  return payload as T
}

/**
 * AI 组件管理页相关接口
 */
export const aiComponentViewApi = {
  /**
   * 查询当前登录员工可用卡片
   * GET /bs/api/v1/doctor-workbench/role-card-configs/mine
   */
  async queryCurrentLoginAvailableCards() {
    const response = await apiClient.get<ApiEnvelope<unknown>>('/bs/api/v1/doctor-workbench/role-card-configs/mine')
    return unwrapApiData<unknown>(response.data)
  },

  /**
   * 新增客户定制卡片
   * POST /bs/api/v1/doctor-workbench/customer-card-customizes
   */
  async createCustomerCardCustomize(params: CustomerCardCustomizeCreateInput) {
    const response = await apiClient.post<ApiEnvelope<CustomerCardCustomize>>(
      '/bs/api/v1/doctor-workbench/customer-card-customizes',
      {
        customerIdCard: params.customerIdCard,
        favoriteName: params.favoriteName,
        cardJson: params.cardJson,
        status: params.status ?? 'active',
        remark: params.remark ?? '',
      },
    )

    return unwrapApiData<CustomerCardCustomize>(response.data)
  },

  /**
   * 按员工和客户查询定制卡片
   * GET /bs/api/v1/doctor-workbench/customer-card-customizes/by-customer?customerIdCard=
   */
  async listCustomerCardCustomizesByCustomer(params: CustomerCardCustomizeByCustomerQueryInput) {
    const response = await apiClient.get<ApiEnvelope<CustomerCardCustomize[]>>(
      '/bs/api/v1/doctor-workbench/customer-card-customizes/by-customer',
      {
        params: {
          customerIdCard: params.customerIdCard,
        },
      },
    )

    return unwrapApiData<CustomerCardCustomize[]>(response.data)
  },

  /**
   * 更新客户定制卡片（仅修改收藏名称）
   * PUT /bs/api/v1/doctor-workbench/customer-card-customizes/{id}
   */
  async renameCustomerCardCustomize(id: string, params: CustomerCardCustomizeRenameInput) {
    const response = await apiClient.put<ApiEnvelope<CustomerCardCustomize>>(
      `/bs/api/v1/doctor-workbench/customer-card-customizes/${encodeURIComponent(id)}`,
      {
        favoriteName: params.favoriteName,
        customerIdCard: params.customerIdCard,
      },
    )

    return unwrapApiData<CustomerCardCustomize>(response.data)
  },

  /**
   * 删除客户定制卡片
   * DELETE /bs/api/v1/doctor-workbench/customer-card-customizes/{id}
   */
  async deleteCustomerCardCustomize(id: string) {
    const response = await apiClient.delete<ApiEnvelope<unknown>>(
      `/bs/api/v1/doctor-workbench/customer-card-customizes/${encodeURIComponent(id)}`,
    )

    return unwrapApiData<unknown>(response.data)
  },

  /**
   * 查询应用角色列表
   * GET /api/v1/auth/roles?appCode=AI-RND-WORKFLOW&pageNo=1&pageSize=200
   */
  async queryAuthRoles(params: AuthRoleQueryInput = {}) {
    const response = await businessClient.get<ApiEnvelope<AuthRolePageResult>>('/api/v1/auth/roles', {
      params: {
        appCode: params.appCode ?? 'AI-RND-WORKFLOW',
        pageNo: params.pageNo ?? 1,
        pageSize: params.pageSize ?? 200,
      },
    })

    return unwrapApiData<AuthRolePageResult>(response.data)
  },

  /**
   * 按角色查询可用卡片
   * GET /bs/api/v1/doctor-workbench/role-card-configs/by-role/${roleId}
   */
  async listRoleCardConfigsByRole(roleId: string) {
    const response = await apiClient.get<ApiEnvelope<RoleCardConfig[]>>(
      `/bs/api/v1/doctor-workbench/role-card-configs/by-role/${roleId}`
    )

    return unwrapApiData<RoleCardConfig[]>(response.data)
  },

  /**
   * 新增角色卡片配置
   * POST /bs/api/v1/doctor-workbench/role-card-configs
   */
  async createRoleCardConfig(params: RoleCardConfigSaveInput) {
    const response = await apiClient.post<ApiEnvelope<RoleCardConfig>>(
      '/bs/api/v1/doctor-workbench/role-card-configs',
      {
        roleId: params.roleId,
        cardSchemaJson: params.cardSchemaJson,
      },
    )

    return unwrapApiData<RoleCardConfig>(response.data)
  },

  /**
   * 更新角色卡片配置
   * PUT /bs/api/v1/doctor-workbench/role-card-configs/{id}
   */
  async updateRoleCardConfig(id: string, params: RoleCardConfigSaveInput) {
    const response = await apiClient.put<ApiEnvelope<RoleCardConfig>>(
      `/bs/api/v1/doctor-workbench/role-card-configs/${encodeURIComponent(id)}`,
      {
        roleId: params.roleId,
        cardSchemaJson: params.cardSchemaJson,
      },
    )

    return unwrapApiData<RoleCardConfig>(response.data)
  },

  /**
   * 分页查询卡片分组
   * POST /bs/api/v1/doctor-workbench/card-groups/query
   */
  async queryCardGroupsPage(params: CardGroupQueryInput = {}) {
    const response = await apiClient.post<ApiEnvelope<CardGroupPageResult>>(
      '/bs/api/v1/doctor-workbench/card-groups/query',
      {
        page: params.page ?? 1,
        size: params.size ?? 100,
        ...params,
      },
    )

    return unwrapApiData<CardGroupPageResult>(response.data)
  },

  /**
   * 新增卡片分组
   * POST /bs/api/v1/doctor-workbench/card-groups
   */
  async createCardGroup(groupName: string) {
    const response = await apiClient.post<ApiEnvelope<CardGroup>>(
      '/bs/api/v1/doctor-workbench/card-groups',
      {
        groupName,
      },
    )

    return unwrapApiData<CardGroup>(response.data)
  },

  /**
   * 新增分组卡片关系
   * POST /bs/api/v1/doctor-workbench/card-group-relations
   */
  async createCardGroupRelation(params: { groupId: string; cardConfigId: string }) {
    const response = await apiClient.post<ApiEnvelope<CardGroupRelation>>(
      '/bs/api/v1/doctor-workbench/card-group-relations',
      {
        groupId: params.groupId,
        cardConfigId: params.cardConfigId,
      },
    )

    return unwrapApiData<CardGroupRelation>(response.data)
  },

  /**
   * 按分组查询卡片关系
   * GET /bs/api/v1/doctor-workbench/card-group-relations/by-group/{groupId}
   */
  async listCardGroupRelationsByGroup(groupId: string) {
    const response = await apiClient.get<ApiEnvelope<CardGroupRelation[]>>(
      `/bs/api/v1/doctor-workbench/card-group-relations/by-group/${encodeURIComponent(groupId)}`,
    )

    return unwrapApiData<CardGroupRelation[]>(response.data)
  },
}
