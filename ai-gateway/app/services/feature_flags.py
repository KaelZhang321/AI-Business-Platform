"""
Feature Flag 客户端 — AI 网关侧功能开关。

支持两种模式：
1. 本地模式（默认）：从环境变量 / Settings 读取，格式 FEATURE_{FLAG_NAME}=true
2. 远程模式：HTTP 调用业务编排层 /api/v1/feature-flags/{name} 获取实时状态

本地模式零依赖、零延迟；远程模式支持 Nacos 动态刷新 + 用户白名单。
"""

from __future__ import annotations

import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 内存缓存: {flag_name: (value, expire_ts)}
_cache: dict[str, tuple[bool, float]] = {}
_CACHE_TTL = 300  # 5 分钟


class FeatureFlagClient:
    """Feature Flag 查询客户端。"""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http = http_client

    def is_enabled_local(self, flag_name: str) -> bool:
        """本地模式：从 Settings.feature_flags 字典读取。"""
        return settings.feature_flags.get(flag_name, False)

    async def is_enabled(self, flag_name: str, user_id: str | None = None) -> bool:
        """
        查询 flag 是否启用。

        优先走内存缓存 → 本地配置 → 远程 API。
        远程模式需要 business_server_url 可达。
        """
        cache_key = f"{flag_name}:{user_id or '_'}"
        now = time.monotonic()

        # 1. 内存缓存
        if cache_key in _cache:
            value, expire_ts = _cache[cache_key]
            if now < expire_ts:
                return value

        # 2. 本地 flag 直接生效（不需要远程查询）
        local_val = settings.feature_flags.get(flag_name)
        if local_val is not None:
            result = bool(local_val)
            _cache[cache_key] = (result, now + _CACHE_TTL)
            return result

        # 3. 远程查询（带超时保护）
        if self._http and settings.business_server_url:
            try:
                params: dict[str, str] = {}
                if user_id:
                    params["userId"] = user_id
                resp = await self._http.get(
                    f"{settings.business_server_url}/api/v1/feature-flags/{flag_name}",
                    params=params,
                    timeout=3,
                )
                if resp.status_code == 200:
                    body = resp.json()
                    result = bool(body.get("data", False))
                    _cache[cache_key] = (result, now + _CACHE_TTL)
                    return result
            except Exception as exc:
                logger.debug("远程 Feature Flag 查询失败 (%s): %s", flag_name, exc)

        # 4. 默认关闭
        _cache[cache_key] = (False, now + _CACHE_TTL)
        return False

    @staticmethod
    def invalidate(flag_name: str | None = None) -> None:
        """清除缓存（配置变更后调用）。"""
        if flag_name:
            keys = [k for k in _cache if k.startswith(f"{flag_name}:")]
            for k in keys:
                _cache.pop(k, None)
        else:
            _cache.clear()
