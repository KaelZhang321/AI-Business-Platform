from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import Request

from app.core.config import reveal_secret, settings

logger = logging.getLogger(__name__)
_TRUSTED_USER_ID_HEADER = "X-User-Id"


@dataclass(slots=True)
class IdentityContext:
    """请求级身份事实快照。

    功能：
        统一承载网关从 JWT 与可信头里收敛出的用户事实，避免 route、workflow、executor
        各自拼装身份字段，导致“谁是最终用户”在不同阶段出现口径漂移。

    返回值约束：
        该对象只描述当前请求期可用的身份事实，不承担持久化职责。
    """

    subject_id: str | None = None
    user_id: str | None = None
    employee_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    role: str | None = None
    roles: list[str] = field(default_factory=list)
    department: str | None = None
    region: str | None = None
    data_scopes: list[str] = field(default_factory=list)
    token_type: str | None = None
    verified: bool = False
    raw_claims: dict[str, Any] = field(default_factory=dict)

    def to_request_context(self) -> dict[str, Any]:
        """转换成 workflow 约定的轻量用户上下文。

        功能：
            route 与 workflow 更关心稳定的业务字段，而不是完整 JWT claims。这里收敛成
            轻量字典，是为了降低下游对 token 结构的耦合，后续即使认证供应方调整 claims，
            只要这一层保持兼容，查询链路就不需要联动改动。

        Returns:
            仅包含 workflow / executor 真正依赖字段的请求级用户上下文。
        """
        return {
            "userId": self.user_id,
            "employeeId": self.employee_id,
            "username": self.username,
            "displayName": self.display_name,
            "role": self.role,
            "roles": list(self.roles),
            "department": self.department,
            "region": self.region,
            "dataScopes": list(self.data_scopes),
            "tokenVerified": self.verified,
        }


class IdentityVault:
    """请求级身份金库。

    当前实现优先做 JWT claims 冻结，能基于共享密钥完成 HS256 验签时会标记 verified。
    若部署环境未提供共享密钥，则仍保留最小 claims 解析结果，供读链路做上下文补全。
    """

    def __init__(self, *, jwt_secret: str | None = None) -> None:
        self._jwt_secret = jwt_secret if jwt_secret is not None else reveal_secret(settings.gateway_jwt_secret)

    def extract_from_request(self, request: Request) -> IdentityContext | None:
        """基于请求头组装当前请求的最终身份上下文。

        功能：
            `ai-gateway` 位于 Java/IAM 之后时，`X-User-Id` 已经代表上游确认过的最终用户主键。
            这里仍然先解析 `Authorization`，保留 token 中的角色、部门等扩展画像，但最终
            `user_id` 允许被可信头覆盖，避免网关继续沿用过时或不一致的 token subject。

        Args:
            request: 当前 FastAPI 请求对象，承载 Bearer token 与可信身份头。

        Returns:
            归一化后的 `IdentityContext`；若 token 与可信头都缺失，则返回 `None`。

        Edge Cases:
            - token 无法解析但 `X-User-Id` 存在时，仍返回最小身份上下文，保证查询链路可继续
            - `X-User-Id` 只覆盖最终 `user_id`，不覆盖 token 中的角色/部门等画像字段
        """
        auth_header = request.headers.get("Authorization")
        identity = self.extract_from_auth_header(auth_header)
        trusted_user_id = _extract_trusted_user_id(request)
        if trusted_user_id is None:
            return identity

        if identity is None:
            return _build_trusted_header_identity(trusted_user_id)

        # Java/IAM 已经完成统一认证；网关层保留 token 画像，但最终 user_id 以可信头为准。
        identity.user_id = trusted_user_id
        return identity

    def extract_from_auth_header(self, auth_header: str | None) -> IdentityContext | None:
        """从 Bearer Token 提取可复用的身份画像。

        功能：
            即使 `X-User-Id` 会覆盖最终 `user_id`，查询链路仍然需要 token 中的角色、部门、
            数据域等扩展画像来补全上下文。因此这里单独保留 token 解析逻辑，让“用户主键”
            与“扩展画像”可以按职责拆分并最终合并。

        Args:
            auth_header: 原始 `Authorization` 请求头。

        Returns:
            成功时返回解析后的身份上下文；格式非法或无法解码时返回 `None`。

        Edge Cases:
            - 未配置共享密钥时仍会返回未验签 claims，供只读链路做最小画像补全
            - 非 `Bearer` 头会直接忽略，避免把其它认证方案误判成 JWT
        """
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return None

        try:
            header, claims, verified = _decode_jwt(token, self._jwt_secret)
        except ValueError as exc:
            logger.debug("IdentityVault failed to decode JWT: %s", exc)
            return None

        role = claims.get("role") or _first_or_none(_coerce_list(claims.get("roles")))
        roles = _coerce_list(claims.get("roles"))
        if role and role not in roles:
            roles.insert(0, role)

        employee_id = _first_non_empty(
            claims.get("employee_id"),
            claims.get("employeeId"),
            claims.get("accountId"),
            claims.get("workNo"),
        )
        user_id = _first_non_empty(claims.get("user_id"), claims.get("userId"), claims.get("sub"))
        identity = IdentityContext(
            subject_id=claims.get("sub"),
            user_id=user_id,
            employee_id=employee_id or user_id,
            username=_first_non_empty(claims.get("username"), claims.get("preferred_username"), claims.get("loginName")),
            display_name=_first_non_empty(claims.get("display_name"), claims.get("displayName"), claims.get("name")),
            role=role,
            roles=roles,
            department=_first_non_empty(claims.get("department"), claims.get("departmentName")),
            region=_first_non_empty(claims.get("region"), claims.get("area"), claims.get("areaName")),
            data_scopes=_coerce_list(
                claims.get("data_scopes") or claims.get("dataScopes") or claims.get("abilities")
            ),
            token_type=claims.get("type") or header.get("typ"),
            verified=verified,
            raw_claims=claims,
        )
        return identity


def _extract_trusted_user_id(request: Request) -> str | None:
    """读取并规范化可信用户头。

    功能：
        Starlette 的 `request.headers` 已经是大小写不敏感映射，因此这里集中做一次空白规整，
        避免后续在 route、middleware、workflow 多处重复写同样的脏值防御逻辑。

    Args:
        request: 当前请求对象。

    Returns:
        去除首尾空白后的可信用户 ID；若头不存在或为空字符串，则返回 `None`。

    Edge Cases:
        - 仅包含空白字符的 header 会被视为缺失，避免把脏值写进 `request.state.user_id`
    """
    header_value = request.headers.get(_TRUSTED_USER_ID_HEADER)
    if header_value is None:
        return None
    normalized_user_id = header_value.strip()
    return normalized_user_id or None


def _build_trusted_header_identity(trusted_user_id: str) -> IdentityContext:
    """为“只有可信头、没有可用 token”的场景构造最小身份上下文。

    功能：
        查询链路真正依赖的是最终 `user_id`，而不是完整 token 画像。这里显式构造最小对象，
        是为了让 `request.state.identity`、`request.state.user_id` 和 `to_request_context()`
        继续走统一通道，而不是在 route 层散落“缺 token 时手写 userId 回填”的特例。

    Args:
        trusted_user_id: 上游可信认证链路已经确认过的用户主键。

    Returns:
        仅携带最小身份事实的 `IdentityContext`。

    Edge Cases:
        - 不伪造角色、部门等扩展画像，避免把“只有 user_id”误装成“完整认证用户”
    """
    return IdentityContext(
        subject_id=trusted_user_id,
        user_id=trusted_user_id,
        raw_claims={_TRUSTED_USER_ID_HEADER: trusted_user_id},
    )


def _decode_jwt(token: str, secret: str | None) -> tuple[dict[str, Any], dict[str, Any], bool]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("token is not a 3-part JWT")

    encoded_header, encoded_payload, encoded_signature = parts
    header = _decode_segment(encoded_header)
    claims = _decode_segment(encoded_payload)
    verified = False

    algorithm = header.get("alg")
    if secret and algorithm == "HS256":
        verified = _verify_hs256_signature(
            signing_input=f"{encoded_header}.{encoded_payload}",
            encoded_signature=encoded_signature,
            secret=secret,
        )
        exp = claims.get("exp")
        if verified and isinstance(exp, (int, float)) and exp < time.time():
            verified = False

    return header, claims, verified


def _verify_hs256_signature(*, signing_input: str, encoded_signature: str, secret: str) -> bool:
    signature = _urlsafe_b64decode(encoded_signature)
    expected = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return hmac.compare_digest(signature, expected)


def _decode_segment(segment: str) -> dict[str, Any]:
    decoded = _urlsafe_b64decode(segment)
    try:
        payload = json.loads(decoded.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("JWT segment is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("JWT segment must decode to an object")
    return payload


def _urlsafe_b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value)]


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, "") and not isinstance(value, str):
            return str(value)
    return None


def _first_or_none(values: list[str]) -> str | None:
    return values[0] if values else None
