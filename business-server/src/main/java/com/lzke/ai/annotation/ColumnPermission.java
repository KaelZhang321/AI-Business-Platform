package com.lzke.ai.annotation;

import java.lang.annotation.*;

/**
 * 列级权限注解 — 标注在 VO 字段上，控制返回字段可见性。
 * <p>
 * 只有拥有指定角色的用户才能看到该字段的实际值，
 * 其他角色看到的是 null 或脱敏后的值。
 *
 * @see com.lzke.ai.serializer.ColumnPermissionSerializer
 */
@Target(ElementType.FIELD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface ColumnPermission {

    /**
     * 允许查看该字段的角色列表，默认仅 admin
     */
    String[] roles() default {"admin"};

    /**
     * 不满足权限时的替换值（字符串类型字段有效），
     * 默认为空字符串表示返回 null
     */
    String fallback() default "";
}
