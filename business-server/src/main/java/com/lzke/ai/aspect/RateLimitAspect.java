package com.lzke.ai.aspect;

import com.lzke.ai.annotation.RateLimit;
import com.lzke.ai.exception.BusinessException;
import com.lzke.ai.exception.ErrorCode;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.time.Duration;

/**
 * 限流 AOP 切面 — 基于 Redis INCR + EXPIRE 实现滑动窗口限流。
 */
@Slf4j
@Aspect
@Component
@RequiredArgsConstructor
public class RateLimitAspect {

    private final StringRedisTemplate redisTemplate;

    @Around("@annotation(rateLimit)")
    public Object around(ProceedingJoinPoint joinPoint, RateLimit rateLimit) throws Throwable {
        String key = buildKey(joinPoint, rateLimit);
        long count = increment(key, rateLimit.period());

        if (count > rateLimit.permits()) {
            log.warn("限流触发: key={}, count={}, limit={}", key, count, rateLimit.permits());
            throw new BusinessException(ErrorCode.RATE_LIMITED,
                    String.format("请求过于频繁，请 %d 秒后重试", rateLimit.period()));
        }

        return joinPoint.proceed();
    }

    private String buildKey(ProceedingJoinPoint joinPoint, RateLimit rateLimit) {
        String prefix;
        if (!rateLimit.key().isEmpty()) {
            prefix = rateLimit.key();
        } else {
            MethodSignature signature = (MethodSignature) joinPoint.getSignature();
            prefix = signature.getDeclaringTypeName() + "." + signature.getName();
        }
        String clientIp = getClientIp();
        return "rate_limit:" + prefix + ":" + clientIp;
    }

    private long increment(String key, int periodSeconds) {
        Long count = redisTemplate.opsForValue().increment(key);
        if (count != null && count == 1) {
            redisTemplate.expire(key, Duration.ofSeconds(periodSeconds));
        }
        return count != null ? count : 0;
    }

    private static String getClientIp() {
        ServletRequestAttributes attrs =
                (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attrs == null) return "unknown";
        HttpServletRequest request = attrs.getRequest();
        String xff = request.getHeader("X-Forwarded-For");
        if (xff != null && !xff.isEmpty()) {
            return xff.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}
