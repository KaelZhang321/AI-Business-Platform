package com.lzke.ai.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * Feature Flag 配置属性 — 支持 Nacos 动态刷新。
 * <p>
 * 配置示例（application-dev.yml 或 Nacos common.yml）：
 * <pre>
 * app:
 *   feature-flags:
 *     flags:
 *       semantic-cache:
 *         enabled: true
 *         whitelist: [user-001, user-002]
 *       spring-ai:
 *         enabled: false
 * </pre>
 */
@Getter
@Setter
@ConfigurationProperties(prefix = "app.feature-flags")
public class FeatureFlagProperties {

    /**
     * 全局总开关，false 则忽略所有 flag 直接返回 false。
     */
    private boolean globalEnabled = true;

    /**
     * 各 flag 定义：key = flag名称，value = 开关配置。
     */
    private Map<String, FlagDefinition> flags = new HashMap<>();

    @Getter
    @Setter
    public static class FlagDefinition {
        /**
         * 是否全局启用该 flag。
         */
        private boolean enabled = false;

        /**
         * 白名单用户 ID 集合 — 即使 enabled=false，白名单用户也视为开启。
         */
        private Set<String> whitelist = new HashSet<>();

        /**
         * 可选描述。
         */
        private String description = "";
    }
}
