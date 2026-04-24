package com.lzke.ai.application.ui;

import com.lzke.ai.application.dto.UiBuilderAuthTypeResponse;
import com.lzke.ai.application.dto.UiBuilderFeatureResponse;
import com.lzke.ai.application.dto.UiBuilderFieldResponse;
import com.lzke.ai.application.dto.UiBuilderNodeTypeResponse;
import com.lzke.ai.application.dto.UiBuilderOverviewResponse;
import com.lzke.ai.application.dto.UiBuilderTableSchemaResponse;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * UI Builder 元数据服务。
 *
 * <p>这个服务只负责维护“不会随着业务数据变化而变化”的静态描述信息，例如：
 *
 * <ul>
 *     <li>模块概览文案</li>
 *     <li>前端可用节点类型</li>
 *     <li>支持的认证方式</li>
 *     <li>DDL 设计说明</li>
 * </ul>
 *
 * <p>这样做的目的是把“静态能力说明”与“运行时编排逻辑”拆开：
 *
 * <ul>
 *     <li>{@link UiBuilderApplicationService} 只保留应用编排、持久化和转换流程</li>
 *     <li>当前类专门承载页面展示和产品说明所需的元数据</li>
 * </ul>
 */
@Service
public class UiBuilderMetadataService {

    /**
     * 构造 UI Builder 的总览响应。
     *
     * <p>该方法返回的是页面级概览信息，主要给前端“流程与模型”页签使用，
     * 用于解释 UI Builder 的目标、使用步骤、组件类型和后端表结构。
     *
     * @return UI Builder 的静态概览对象
     */
    public UiBuilderOverviewResponse buildOverview() {
        return new UiBuilderOverviewResponse(
                "JSON Render Builder",
                "围绕三方接口文档导入、接口联调、卡片编排和 json-render 生成的配置中心。",
                featureDefinitions(),
                workflowSteps(),
                authTypes(),
                nodeTypes(),
                tableSchemas()
        );
    }

    /**
     * 返回当前前端支持的组件节点类型。
     *
     * <p>这里返回的节点类型需要和 `frontend/src/components/dynamic-ui/catalog.ts`
     * 中已经注册的组件保持一致，否则后端生成的 spec 无法被前端正确渲染。
     *
     * @return 可选节点类型列表
     */
    public List<UiBuilderNodeTypeResponse> nodeTypes() {
        return List.of(
                new UiBuilderNodeTypeResponse("Card", "容器卡片，用于承载子节点。", true, List.of("title", "subtitle")),
                new UiBuilderNodeTypeResponse("Metric", "指标卡，展示单个关键数值。", false, List.of("label", "value", "format")),
                new UiBuilderNodeTypeResponse("Table", "二维表格，适合榜单和明细。", false, List.of("title", "columns", "data")),
                new UiBuilderNodeTypeResponse("List", "对象列表，适合待办、任务和文档。", false, List.of("title", "items", "emptyText")),
                new UiBuilderNodeTypeResponse("Form", "查询或触发表单，支持 text/number/date/select。", false, List.of("fields", "submitLabel")),
                new UiBuilderNodeTypeResponse("Tag", "单个标签节点。", false, List.of("label", "color")),
                new UiBuilderNodeTypeResponse("Chart", "图表节点，底层对接 ECharts option。", false, List.of("title", "kind", "option"))
        );
    }

    /**
     * 返回 UI Builder 支持的接口认证方式。
     *
     * <p>这些类型既用于前端表单下拉，也会参与后端联调请求头/Query 参数的自动拼装。
     *
     * @return 可选认证方式列表
     */
    public List<UiBuilderAuthTypeResponse> authTypes() {
        return List.of(
                new UiBuilderAuthTypeResponse("none", "无认证"),
                new UiBuilderAuthTypeResponse("api_key", "API Key 认证"),
                new UiBuilderAuthTypeResponse("bearer_token", "Bearer Token 认证"),
                new UiBuilderAuthTypeResponse("basic_auth", "Basic Auth 认证"),
                new UiBuilderAuthTypeResponse("oauth2_client", "OAuth2 Client Credentials")
        );
    }

    /**
     * 返回 UI Builder 模块的功能说明。
     *
     * @return 产品能力点列表
     */
    public List<UiBuilderFeatureResponse> featureDefinitions() {
        return List.of(
                new UiBuilderFeatureResponse("接口源管理", "导入 OpenAPI/Swagger、手工录入接口并配置认证方式。"),
                new UiBuilderFeatureResponse("接口联调", "对三方接口做参数配置、测试调用和样例响应固化。"),
                new UiBuilderFeatureResponse("运行时调用", "按 endpointId 发起真实接口调用，并记录 flowNum 级别的调用日志。"),
                new UiBuilderFeatureResponse("角色关联", "把已导入的接口定义绑定到 IAM 角色，支持按角色筛选接口。"),
                new UiBuilderFeatureResponse("语义转换", "维护标准字段、字段别名和值映射，为字段编排和 AI 理解提供上下文。"),
                new UiBuilderFeatureResponse("卡片管理", "统一维护工作台卡片，并按卡片管理接口编排。"),
                new UiBuilderFeatureResponse("卡片接口关联", "为卡片绑定多个接口定义，支持后续动态渲染和调用。")
        );
    }

    /**
     * 返回推荐操作流程，供前端流程页签直接展示。
     *
     * @return UI Builder 的标准使用步骤
     */
    public List<String> workflowSteps() {
        return List.of(
                "1. 导入接口文档并生成标准化接口定义",
                "2. 配置接口认证、环境和测试样例",
                "3. 新建卡片并维护卡片元信息",
                "4. 为卡片关联接口定义并调整排序",
                "5. 运行时按卡片聚合接口数据并生成 json-render"
        );
    }

    /**
     * 返回后端表结构说明，用于帮助前端和研发理解各张表在 UI Builder 中的职责。
     *
     * @return DDL 设计说明
     */
    public List<UiBuilderTableSchemaResponse> tableSchemas() {
        return List.of(
                new UiBuilderTableSchemaResponse("ui_api_sources", "接口源与文档地址配置", List.of(
                        new UiBuilderFieldResponse("id", "varchar(64)", "主键"),
                        new UiBuilderFieldResponse("source_type", "varchar(32)", "来源类型"),
                        new UiBuilderFieldResponse("auth_type", "varchar(32)", "认证方式"),
                        new UiBuilderFieldResponse("auth_config", "json", "认证配置")
                )),
                new UiBuilderTableSchemaResponse("ui_api_tags", "接口源下的标签分组", List.of(
                        new UiBuilderFieldResponse("source_id", "varchar(64)", "所属接口源"),
                        new UiBuilderFieldResponse("name", "varchar(128)", "标签名称"),
                        new UiBuilderFieldResponse("code", "varchar(128)", "标签编码")
                )),
                new UiBuilderTableSchemaResponse("ui_api_endpoints", "标准化后的接口定义", List.of(
                        new UiBuilderFieldResponse("source_id", "varchar(64)", "所属接口源"),
                        new UiBuilderFieldResponse("tag_id", "varchar(64)", "所属标签"),
                        new UiBuilderFieldResponse("method", "varchar(16)", "HTTP 方法"),
                        new UiBuilderFieldResponse("operation_safety", "varchar(16)", "操作安全等级 query/list/mutation"),
                        new UiBuilderFieldResponse("request_schema", "json", "请求结构"),
                        new UiBuilderFieldResponse("response_schema", "json", "响应结构"),
                        new UiBuilderFieldResponse("field_orchestration", "json", "字段编排配置")
                )),
                new UiBuilderTableSchemaResponse("ui_api_endpoint_roles", "接口定义与 IAM 角色关系", List.of(
                        new UiBuilderFieldResponse("endpoint_id", "varchar(64)", "所属接口定义"),
                        new UiBuilderFieldResponse("role_id", "varchar(64)", "角色 ID"),
                        new UiBuilderFieldResponse("role_name", "varchar(128)", "角色名称"),
                        new UiBuilderFieldResponse("field_orchestration", "json", "角色侧字段编排配置")
                )),
                new UiBuilderTableSchemaResponse("semantic_field_dict", "语义字段字典主表", List.of(
                        new UiBuilderFieldResponse("standard_key", "varchar(64)", "标准字段 key"),
                        new UiBuilderFieldResponse("label", "varchar(64)", "展示名"),
                        new UiBuilderFieldResponse("field_type", "varchar(32)", "组件类型"),
                        new UiBuilderFieldResponse("value_map", "json", "全局值映射")
                )),
                new UiBuilderTableSchemaResponse("semantic_field_alias", "字段别名映射表", List.of(
                        new UiBuilderFieldResponse("standard_key", "varchar(64)", "标准字段 key"),
                        new UiBuilderFieldResponse("alias", "varchar(64)", "接口原始字段名"),
                        new UiBuilderFieldResponse("api_id", "varchar(64)", "所属接口定义")
                )),
                new UiBuilderTableSchemaResponse("semantic_field_value_map", "字段值映射扩展表", List.of(
                        new UiBuilderFieldResponse("standard_key", "varchar(64)", "标准字段 key"),
                        new UiBuilderFieldResponse("api_id", "varchar(64)", "接口级覆盖的接口 ID"),
                        new UiBuilderFieldResponse("standard_value", "varchar(64)", "标准值"),
                        new UiBuilderFieldResponse("raw_value", "varchar(64)", "接口原始值")
                )),
                new UiBuilderTableSchemaResponse("ui_api_test_logs", "接口联调与样例响应记录", List.of(
                        new UiBuilderFieldResponse("endpoint_id", "varchar(64)", "所属接口定义"),
                        new UiBuilderFieldResponse("request_url", "varchar(255)", "实际请求地址"),
                        new UiBuilderFieldResponse("response_status", "int", "响应状态码"),
                        new UiBuilderFieldResponse("success_flag", "tinyint(1)", "联调是否成功")
                )),
                new UiBuilderTableSchemaResponse("ui_api_flow_logs", "运行时接口调用日志", List.of(
                        new UiBuilderFieldResponse("flow_num", "varchar(64)", "流程编号"),
                        new UiBuilderFieldResponse("endpoint_id", "varchar(64)", "所属接口定义"),
                        new UiBuilderFieldResponse("request_body", "json", "实际请求体"),
                        new UiBuilderFieldResponse("response_body", "json", "实际响应体"),
                        new UiBuilderFieldResponse("invoke_status", "varchar(32)", "接口调用状态")
                )),
                new UiBuilderTableSchemaResponse("ui_cards", "工作台卡片定义", List.of(
                        new UiBuilderFieldResponse("name", "varchar(128)", "卡片名称"),
                        new UiBuilderFieldResponse("code", "varchar(64)", "卡片编码"),
                        new UiBuilderFieldResponse("card_type", "varchar(32)", "卡片类型"),
                        new UiBuilderFieldResponse("status", "varchar(32)", "状态")
                )),
                new UiBuilderTableSchemaResponse("ui_card_endpoint_relations", "卡片和接口关系", List.of(
                        new UiBuilderFieldResponse("card_id", "varchar(64)", "卡片ID"),
                        new UiBuilderFieldResponse("endpoint_id", "varchar(64)", "接口定义ID"),
                        new UiBuilderFieldResponse("sort_order", "int", "显示排序")
                ))
        );
    }
}
