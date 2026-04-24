package com.lzke.ai.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RBloomFilter;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

/**
 * 缓存防护服务 — BloomFilter 防穿透 + Redisson 互斥锁防击穿 + TTL 随机化防雪崩。
 * <p>
 * 缓存键命名规范：{产品}:{模块}:{实体}:{ID}
 * 示例：aiplatform:knowledge:doc:abc123
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CacheProtectedService {

    private static final String BLOOM_FILTER_KEY = "aiplatform:bloom:ids";
    private static final long BLOOM_EXPECTED_INSERTIONS = 100_000L;
    private static final double BLOOM_FALSE_POSITIVE_RATE = 0.01;
    private static final String NULL_PLACEHOLDER = "__NULL__";
    private static final Duration NULL_TTL = Duration.ofMinutes(2);
    private static final int TTL_JITTER_SECONDS = 300;

    private final RedissonClient redissonClient;
    private final StringRedisTemplate redisTemplate;

    /**
     * 获取或初始化 BloomFilter
     */
    public RBloomFilter<String> getBloomFilter() {
        RBloomFilter<String> bloom = redissonClient.getBloomFilter(BLOOM_FILTER_KEY);
        bloom.tryInit(BLOOM_EXPECTED_INSERTIONS, BLOOM_FALSE_POSITIVE_RATE);
        return bloom;
    }

    /**
     * 将 ID 加入 BloomFilter（创建新记录时调用）
     */
    public void addToBloom(String id) {
        getBloomFilter().add(id);
    }

    /**
     * 带完整防护的缓存查询：
     * 1. BloomFilter 判存 → 不存在直接返回 null（防穿透）
     * 2. Redis 缓存命中 → 返回缓存值
     * 3. 缓存未命中 → 分布式锁保护回源（防击穿）
     * 4. 回源结果为 null → 缓存 NULL_PLACEHOLDER 短 TTL（防穿透）
     * 5. 正常结果 → 缓存 + 随机 TTL 偏移（防雪崩）
     *
     * @param cacheKey    缓存键（遵循命名规范 {产品}:{模块}:{实体}:{ID}）
     * @param entityId    实体 ID（用于 BloomFilter 判存）
     * @param baseTtl     基准 TTL
     * @param dbLoader    回源数据库加载函数
     * @return 缓存值或 null
     */
    public String getWithProtection(String cacheKey, String entityId, Duration baseTtl, Supplier<String> dbLoader) {
        // 1. BloomFilter 防穿透
        if (!getBloomFilter().contains(entityId)) {
            log.debug("BloomFilter 命中: {} 不存在，跳过回源", entityId);
            return null;
        }

        // 2. 查 Redis 缓存
        String cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) {
            return NULL_PLACEHOLDER.equals(cached) ? null : cached;
        }

        // 3. 缓存未命中 → 互斥锁防击穿
        String lockKey = "lock:" + cacheKey;
        RLock lock = redissonClient.getLock(lockKey);
        try {
            boolean acquired = lock.tryLock(3, 10, TimeUnit.SECONDS);
            if (!acquired) {
                // 等锁超时，直接回源（降级）
                log.warn("获取缓存锁超时: {}", lockKey);
                return dbLoader.get();
            }

            try {
                // double-check：拿到锁后再查一次缓存
                cached = redisTemplate.opsForValue().get(cacheKey);
                if (cached != null) {
                    return NULL_PLACEHOLDER.equals(cached) ? null : cached;
                }

                // 4. 回源
                String value = dbLoader.get();

                if (value == null) {
                    // 防穿透：空值短缓存
                    redisTemplate.opsForValue().set(cacheKey, NULL_PLACEHOLDER, NULL_TTL);
                    return null;
                }

                // 5. 防雪崩：基准 TTL + 随机偏移
                Duration jitteredTtl = baseTtl.plusSeconds(
                        ThreadLocalRandom.current().nextInt(TTL_JITTER_SECONDS));
                redisTemplate.opsForValue().set(cacheKey, value, jitteredTtl);
                return value;
            } finally {
                if (lock.isHeldByCurrentThread()) {
                    lock.unlock();
                }
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.warn("缓存锁被中断: {}", lockKey);
            return dbLoader.get();
        }
    }

    /**
     * 主动删除缓存（数据更新时调用）
     */
    public void evict(String cacheKey) {
        redisTemplate.delete(cacheKey);
    }
}
