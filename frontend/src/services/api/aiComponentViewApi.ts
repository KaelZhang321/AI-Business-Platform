import { apiClient, businessClient } from '../api'

/** 后端统一响应包装 */
type ApiEnvelope<T> = {
  /** 业务状态码 */
  code?: number
  /** 提示消息 */
  message?: string
  /** 业务数据 */
  data?: T
}

/** 卡片分组 */
export type CardGroup = {
  /** 分组 ID */
  id?: string
  /** 分组名称 */
  groupName?: string
  /** 分组排序 */
  groupSort?: number
  /** 是否可见（1=可见） */
  visibleFlag?: number
  /** 状态（active/inactive） */
  status?: string
  /** 备注 */
  remark?: string
  /** 创建人 ID */
  createdBy?: string
  /** 创建人姓名 */
  createdByName?: string
  /** 更新人 ID */
  updatedBy?: string
  /** 更新人姓名 */
  updatedByName?: string
  /** 创建时间 */
  createdAt?: string
  /** 更新时间 */
  updatedAt?: string
}

/** 卡片分组查询参数 */
export type CardGroupQueryInput = {
  /** 页码 */
  page?: number | string
  /** 每页条数 */
  size?: number | string
  /** 分组名称（模糊查询） */
  groupName?: string
  /** 状态筛选 */
  status?: string
  /** 可见标志 */
  visibleFlag?: number
  /** 偏移量 */
  offset?: number
  [key: string]: unknown
}

/** 卡片分组分页查询结果 */
export type CardGroupPageResult = {
  /** 分组列表 */
  data?: CardGroup[]
  /** 总记录数 */
  total?: number
  /** 当前页 */
  page?: number
  /** 每页条数 */
  size?: number
}

/** 卡片分组关联关系（分组与卡片配置的多对多中间表） */
export type CardGroupRelation = {
  id?: string
  /** 所属分组 ID */
  groupId?: string
  /** 关联的卡片配置 ID */
  cardConfigId?: string
  /** 卡片在分组内的排序 */
  cardSort?: number
  visibleFlag?: number
  status?: string
  remark?: string
  createdAt?: string
  updatedAt?: string
}

/** IAM 角色信息 */
export type AuthRole = {
  id?: string
  /** 应用编码 */
  appCode?: string
  /** 角色名称 */
  roleName?: string
  /** 角色编码 */
  roleCode?: string
  /** 角色描述 */
  roleDesc?: string | null
  /** 排序 */
  sortOrder?: number
  /** 状态（1=启用） */
  status?: number
  createTime?: string
  updateTime?: string
}

/** 角色分页查询结果 */
export type AuthRolePageResult = {
  records?: AuthRole[]
  total?: number
  size?: number
  current?: number
  pages?: number
}

/** 角色查询参数 */
export type AuthRoleQueryInput = {
  appCode?: string
  pageNo?: number
  pageSize?: number
}

/** 角色卡片配置（角色绱定的卡片 Schema + 接口关联） */
export type RoleCardConfig = {
  id?: string
  /** 角色 ID */
  roleId?: string
  /** 角色编码 */
  roleCode?: string
  /** 角色名称 */
  roleName?: string
  /** 卡片 JSON Schema 字符串 */
  cardSchemaJson?: string
  /** 卡片与接口的关联关系映射 */
  cardEndpointRelations?: RoleCardEndpointRelations
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

/** 卡片与接口的关联关系单项 */
export type RoleCardEndpointRelation = {
  id?: string
  /** 卡片 ID */
  cardId?: string
  /** 接口 ID */
  endpointId?: string
  /** 操作安全等级（query/list/mutation） */
  operationSafety?: 'query' | 'list' | 'mutation' | string | null
  /** 接口维度操作安全等级（兼容字段） */
  endpointOperationSafety?: 'query' | 'list' | 'mutation' | string | null
  /** 排序 */
  sortOrder?: number
  /** 接口名称 */
  endpointName?: string | null
  /** 接口路径 */
  endpointPath?: string | null
  /** HTTP 方法 */
  endpointMethod?: string | null
  /** 接口状态 */
  endpointStatus?: string | null
  /** 数据源 ID */
  sourceId?: string | null
  /** 数据源名称 */
  sourceName?: string | null
  /** 标签名称 */
  tagName?: string | null
  createdAt?: string
  updatedAt?: string
}

/** 卡片-接口关联映射：键为卡片 ID，值为该卡片关联的接口列表 */
export type RoleCardEndpointRelations = Record<string, RoleCardEndpointRelation[]>

/** 运行时接口调用载荷 */
export type RuntimeInvokePayload = {
  /** 流程编号 */
  flowNum: number
  /** URL 查询参数 */
  queryParams: Record<string, unknown>
  /** 请求体 */
  body: Record<string, unknown>
  /** 创建人 */
  createdBy: string
}

/** 角色卡片配置保存输入 */
export type RoleCardConfigSaveInput = {
  /** 角色 ID */
  roleId: string
  /** 卡片 Schema JSON 字符串 */
  cardSchemaJson: string
}

/** 客户定制卡片（员工为某客户保存的卡片布局） */
export type CustomerCardCustomize = {
  id?: string
  /** 员工 ID */
  employeeId?: string
  /** 员工姓名 */
  employeeName?: string
  /** 客户身份证号 */
  customerIdCard?: string
  /** 收藏名称 */
  favoriteName?: string
  /** 卡片布局 JSON */
  cardJson?: string
  status?: string
  remark?: string
  createdAt?: string
  updatedAt?: string
  createTime?: string
  updateTime?: string
}

/** 创建客户定制卡片的输入参数 */
export type CustomerCardCustomizeCreateInput = {
  /** 客户身份证号 */
  customerIdCard: string
  /** 收藏名称 */
  favoriteName: string
  /** 卡片布局 JSON */
  cardJson: string
  status?: string
  remark?: string
}

/** 按客户查询定制卡片的输入参数 */
export type CustomerCardCustomizeByCustomerQueryInput = {
  /** 客户身份证号 */
  customerIdCard: string
}

/** 重命名客户定制卡片的输入参数 */
export type CustomerCardCustomizeRenameInput = {
  /** 新收藏名称 */
  favoriteName: string
  /** 客户身份证号 */
  customerIdCard: string
}

/**
 * 拆包工具：统一提取响应中的 data 字段。
 * 如果响应是 ApiEnvelope 包装格式则返回 data，否则结果原样返回。
 */
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

  /**
   * 运行时调用 endpoint
   * POST /api/v1/ui-builder/runtime/endpoints/${endpointId}/invoke
   */
  async invokeRuntimeEndpoint(endpointId: string, payload: RuntimeInvokePayload) {
    const response = await businessClient.post<ApiEnvelope<unknown>>(
      `/api/v1/ui-builder/runtime/endpoints/${encodeURIComponent(endpointId)}/invoke`,
      payload,
    )

    return unwrapApiData<unknown>(response.data)
  },
}
