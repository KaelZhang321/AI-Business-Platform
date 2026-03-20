package com.lzke.ai.security;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Getter
@Setter
@ConfigurationProperties(prefix = "app.security.jwt")
public class JwtProperties {

    /**
     * HMAC secret，至少 32 字节。
     */
    private String secret = "change_me_super_secret_key_please";

    /**
     * 过期时间（毫秒）。
     */
    private long expiration = 86400000L;
}
