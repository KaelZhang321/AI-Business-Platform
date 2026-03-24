package com.lzke.ai.annotation;

import java.lang.annotation.*;

/**
 * API 限流注解 — 基于 Redis 滑动窗口。
 *
 * 示例: @RateLimit(permits = 100, period = 60)  // 每分钟100次
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface RateLimit {
    /** 时间窗口内允许的最大请求数 */
    int permits() default 100;

    /** 时间窗口（秒） */
    int period() default 60;

    /** 限流 key 前缀，默认使用方法全限定名 */
    String key() default "";
}
