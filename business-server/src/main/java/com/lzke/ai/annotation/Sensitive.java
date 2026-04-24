package com.lzke.ai.annotation;

import com.fasterxml.jackson.annotation.JacksonAnnotationsInside;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.lzke.ai.serializer.SensitiveJsonSerializer;

import java.lang.annotation.*;

/**
 * 敏感字段标注 — 标记在 VO/DTO 的 getter 或字段上，
 * Jackson 序列化时自动脱敏。
 *
 * 示例: @Sensitive(type = SensitiveType.PHONE)
 */
@Target({ElementType.FIELD, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
@Documented
@JacksonAnnotationsInside
@JsonSerialize(using = SensitiveJsonSerializer.class)
public @interface Sensitive {
    SensitiveType type();
}
