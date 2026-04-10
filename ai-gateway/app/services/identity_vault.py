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

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IdentityContext:
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
        self._jwt_secret = jwt_secret if jwt_secret is not None else settings.gateway_jwt_secret

    def extract_from_request(self, request: Request) -> IdentityContext | None:
        auth_header = request.headers.get("Authorization")
        return self.extract_from_auth_header(auth_header)

    def extract_from_auth_header(self, auth_header: str | None) -> IdentityContext | None:
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
