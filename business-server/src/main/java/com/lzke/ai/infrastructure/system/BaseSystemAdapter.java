package com.lzke.ai.infrastructure.system;

import java.util.List;
import java.util.Map;

/**
 * 外部系统适配器基类
 * 各业务系统（ERP、CRM、OA等）的对接适配器需继承此类
 */
public abstract class BaseSystemAdapter {

    /**
     * 获取系统标识名称
     */
    public abstract String getSystemName();

    /**
     * 拉取指定用户的待办任务
     */
    public abstract List<Map<String, Object>> fetchTasks(String userId);

    /**
     * 执行系统操作
     */
    public abstract Map<String, Object> executeAction(String action, Map<String, Object> params);
}
