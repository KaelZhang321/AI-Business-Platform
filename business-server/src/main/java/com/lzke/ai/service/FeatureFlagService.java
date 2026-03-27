package com.lzke.ai.service;

import com.lzke.ai.config.FeatureFlagProperties;
import com.lzke.ai.config.FeatureFlagProperties.FlagDefinition;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Feature Flag 服务 — 全局开关 + 用户白名单两种模式。
 * <p>
 * 判断优先级：
 * 1. 全局总开关关闭 → false
 * 2. flag 未定义 → false
 * 3. 用户在白名单中 → true
 * 4. flag enabled → true/false
 * <p>
 * 结果缓存在 Redis（TTL 5分钟），Nacos 刷新配置后下次查询自动生效。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FeatureFlagService {

    private static final String CACHE_PREFIX = "aiplatform:feature-flag:";
    private static final Duration CACHE_TTL = Duration.ofMinutes(5);

    private final FeatureFlagProperties properties;
    private final StringRedisTemplate redisTemplate;

    /**
     * 判断某 flag 对指定用户是否开启。
     *
     * @param flagName flag 名称（如 "semantic-cache"）
     * @param userId   用户 ID，可为 null（仅判断全局开关）
     * @return true = 开启
     */
    public boolean isEnabled(String flagName, String userId) {
        if (!properties.isGlobalEnabled()) {
            return false;
        }

        FlagDefinition flag = properties.getFlags().get(flagName);
        if (flag == null) {
            return false;
        }

        // 白名单优先
        if (userId != null && flag.getWhitelist().contains(userId)) {
            return true;
        }

        return flag.isEnabled();
    }

    /**
     * 判断某 flag 是否全局开启（不考虑用户白名单）。
     */
    public boolean isEnabled(String flagName) {
        return isEnabled(flagName, null);
    }

    /**
     * 获取所有 flag 的当前状态（供管理端/API 查询）。
     */
    public Map<String, Object> getAllFlags() {
        Map<String, Object> result = new HashMap<>();
        result.put("globalEnabled", properties.isGlobalEnabled());

        Map<String, Object> flagDetails = new HashMap<>();
        for (var entry : properties.getFlags().entrySet()) {
            FlagDefinition def = entry.getValue();
            Map<String, Object> detail = new HashMap<>();
            detail.put("enabled", def.isEnabled());
            detail.put("whitelistSize", def.getWhitelist().size());
            detail.put("description", def.getDescription());
            flagDetails.put(entry.getKey(), detail);
        }
        result.put("flags", flagDetails);
        return result;
    }

    /**
     * 带 Redis 缓存的判断（高频调用场景，减轻配置读取压力）。
     */
    public boolean isEnabledCached(String flagName, String userId) {
        String cacheKey = CACHE_PREFIX + flagName + ":" + (userId != null ? userId : "_global_");
        String cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) {
            return "1".equals(cached);
        }

        boolean enabled = isEnabled(flagName, userId);
        redisTemplate.opsForValue().set(cacheKey, enabled ? "1" : "0", CACHE_TTL);
        return enabled;
    }
}
