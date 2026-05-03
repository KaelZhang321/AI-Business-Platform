from __future__ import annotations

from pydantic import SecretStr

from app.core.config import Settings, reveal_secret


def test_sensitive_settings_are_secretstr_and_masked() -> None:
    settings = Settings()

    for field_name in (
        "business_mysql_password",
        "health_quadrant_ods_mysql_password",
        "redis_url",
        "elasticsearch_password",
        "minio_access_key",
        "minio_secret_key",
        "neo4j_password",
        "text2sql_api_key",
        "meeting_bi_api_key",
        "ark_api_key",
        "gateway_jwt_secret",
        "openai_api_key",
        "langsmith_api_key",
        "rabbitmq_url",
    ):
        value = getattr(settings, field_name)
        assert isinstance(value, SecretStr)
        assert "SecretStr" in repr(value)


def test_reveal_secret_accepts_secretstr_raw_string_and_none() -> None:
    assert reveal_secret(SecretStr("secret-value")) == "secret-value"
    assert reveal_secret("plain-value") == "plain-value"
    assert reveal_secret(None) == ""


def test_cors_allow_origins_accepts_comma_separated_env_value() -> None:
    settings = Settings(cors_allow_origins="https://app.example.com,http://localhost:5173")

    assert settings.cors_allow_origins == ["https://app.example.com", "http://localhost:5173"]
