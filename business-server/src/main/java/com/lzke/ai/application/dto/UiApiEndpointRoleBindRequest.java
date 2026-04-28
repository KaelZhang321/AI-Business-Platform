package com.lzke.ai.application.dto;

import lombok.Data;

import java.util.List;

/**
 * 接口与角色关系绑定请求。
 *
 * <p>前端会先从 IAM 角色接口中选择一个角色，再选择当前系统里已经存在的接口定义。
 * 提交时带上角色快照信息和待绑定的接口 ID 集合，后端负责幂等写入关系表。
 */
@Data
public class UiApiEndpointRoleBindRequest {

    /**
     * 角色 ID。
     */
    private String roleId;

    /**
     * 角色编码。
     */
    private String roleCode;

    /**
     * 角色名称。
     */
    private String roleName;

    /**
     * 待绑定的接口定义 ID 列表。
     */
    private List<String> endpointIds;

    /**
     * 发起人。
     */
    private String createdBy;
}
