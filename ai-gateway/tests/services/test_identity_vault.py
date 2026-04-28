from __future__ import annotations

import base64
import hashlib
import hmac
import json

from starlette.requests import Request

from app.services.identity_vault import IdentityVault


def _encode_part(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _build_hs256_token(claims: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _encode_part(header)
    encoded_claims = _encode_part(claims)
    signing_input = f"{encoded_header}.{encoded_claims}"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("utf-8")
    return f"{signing_input}.{encoded_signature}"


def test_identity_vault_extracts_verified_context() -> None:
    token = _build_hs256_token(
        {
            "sub": "u_001",
            "username": "alice",
            "role": "admin",
            "department": "sales",
            "abilities": ["read:all", "update:all"],
            "type": "access",
        },
        secret="stage1-secret",
    )

    identity = IdentityVault(jwt_secret="stage1-secret").extract_from_auth_header(f"Bearer {token}")

    assert identity is not None
    assert identity.verified is True
    assert identity.user_id == "u_001"
    assert identity.employee_id == "u_001"
    assert identity.username == "alice"
    assert identity.role == "admin"
    assert identity.roles == ["admin"]
    assert identity.department == "sales"
    assert identity.data_scopes == ["read:all", "update:all"]
    assert identity.to_request_context()["tokenVerified"] is True


def test_identity_vault_extracts_unverified_context_without_secret() -> None:
    token = _build_hs256_token(
        {
            "sub": "u_002",
            "username": "bob",
            "roles": ["viewer"],
            "departmentName": "ops",
            "region": "east",
            "dataScopes": ["read:documents"],
        },
        secret="another-secret",
    )

    identity = IdentityVault(jwt_secret="").extract_from_auth_header(f"Bearer {token}")

    assert identity is not None
    assert identity.verified is False
    assert identity.user_id == "u_002"
    assert identity.role == "viewer"
    assert identity.roles == ["viewer"]
    assert identity.department == "ops"
    assert identity.region == "east"
    assert identity.data_scopes == ["read:documents"]


def test_identity_vault_returns_none_for_invalid_header() -> None:
    assert IdentityVault(jwt_secret="stage1-secret").extract_from_auth_header("Token abc") is None


def test_identity_vault_prefers_trusted_user_id_header_over_token_user_id() -> None:
    token = _build_hs256_token(
        {
            "sub": "u_003",
            "userId": "token-user-003",
            "employeeId": "emp_003",
            "role": "viewer",
        },
        secret="stage1-secret",
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/api-query",
            "headers": [
                (b"authorization", f"Bearer {token}".encode("utf-8")),
                (b"x-user-id", b"header-user-003"),
            ],
        }
    )

    identity = IdentityVault(jwt_secret="stage1-secret").extract_from_request(request)

    assert identity is not None
    assert identity.user_id == "header-user-003"
    assert identity.employee_id == "emp_003"
    assert identity.role == "viewer"
    assert identity.to_request_context()["userId"] == "header-user-003"


def test_identity_vault_builds_minimal_identity_from_trusted_user_id_header() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/api-query",
            "headers": [(b"x-user-id", b"header-user-004")],
        }
    )

    identity = IdentityVault(jwt_secret="stage1-secret").extract_from_request(request)

    assert identity is not None
    assert identity.user_id == "header-user-004"
    assert identity.subject_id == "header-user-004"
    assert identity.verified is False
    assert identity.role is None
    assert identity.to_request_context()["userId"] == "header-user-004"
