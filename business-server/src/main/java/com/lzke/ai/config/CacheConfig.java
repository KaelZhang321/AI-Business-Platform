package com.lzke.ai.config;

import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.caffeine.CaffeineCacheManager;
import org.springframework.cache.support.CompositeCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;

import java.time.Duration;

@Configuration
@EnableCaching
public class CacheConfig {

    @Bean
    public Caffeine<Object, Object> caffeineSpec() {
        return Caffeine.newBuilder()
                .initialCapacity(200)
                .maximumSize(2_000)
                .expireAfterWrite(Duration.ofMinutes(10))
                .softValues();
    }

    @Bean
    public CacheManager cacheManager(RedisConnectionFactory factory, Caffeine<Object, Object> caffeine) {
        var caffeineManager = new CaffeineCacheManager("knowledge:documents", "audit:logs");
        caffeineManager.setCaffeine(caffeine);

        RedisCacheConfiguration redisConfiguration = RedisCacheConfiguration.defaultCacheConfig()
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(new GenericJackson2JsonRedisSerializer()))
                .entryTtl(Duration.ofMinutes(30));

        CacheManager redisManager = RedisCacheManager.builder(factory)
                .cacheDefaults(redisConfiguration)
                .build();

        CompositeCacheManager compositeCacheManager = new CompositeCacheManager(caffeineManager, redisManager);
        compositeCacheManager.setFallbackToNoOpCache(true);
        return compositeCacheManager;
    }
}
