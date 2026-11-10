"""Tests para core.config — validación estricta al startup."""

import pytest
from pydantic import ValidationError

from core.config import Settings


def _valid_kwargs(**overrides):
    base = dict(
        anthropic_api_key="sk-ant-test-key",
        database_url="postgresql+psycopg://kisabella_app:pw@db:5432/kisabella_test",
        secret_key="x" * 32,
    )
    base.update(overrides)
    return base


class TestSettingsValid:
    def test_loads_with_valid_inputs(self):
        s = Settings(_env_file=None, **_valid_kwargs())
        assert s.anthropic_api_key.get_secret_value() == "sk-ant-test-key"
        assert s.secret_key.get_secret_value() == "x" * 32

    def test_defaults_applied_for_optional_fields(self):
        s = Settings(_env_file=None, **_valid_kwargs())
        assert s.anthropic_model == "claude-sonnet-4-6"
        assert s.log_level == "INFO"
        assert s.allowed_ips == "127.0.0.1"
        assert s.tavily_api_key.get_secret_value() == ""
        assert s.banxico_token.get_secret_value() == ""

    def test_app_user_id_is_uuid_string(self):
        s = Settings(_env_file=None, **_valid_kwargs())
        assert s.app_user_id == "00000000-0000-0000-0000-000000000001"


class TestSettingsRequiredFields:
    def test_missing_anthropic_api_key_fails(self):
        kwargs = _valid_kwargs()
        del kwargs["anthropic_api_key"]
        with pytest.raises(ValidationError) as exc:
            Settings(_env_file=None, **kwargs)
        assert "anthropic_api_key" in str(exc.value)

    def test_missing_database_url_fails(self):
        kwargs = _valid_kwargs()
        del kwargs["database_url"]
        with pytest.raises(ValidationError) as exc:
            Settings(_env_file=None, **kwargs)
        assert "database_url" in str(exc.value)

    def test_missing_secret_key_fails(self):
        kwargs = _valid_kwargs()
        del kwargs["secret_key"]
        with pytest.raises(ValidationError) as exc:
            Settings(_env_file=None, **kwargs)
        assert "secret_key" in str(exc.value)


class TestSettingsValidators:
    def test_secret_key_too_short_fails(self):
        with pytest.raises(ValidationError, match="32"):
            Settings(_env_file=None, **_valid_kwargs(secret_key="too_short"))

    def test_secret_key_exactly_32_chars_ok(self):
        s = Settings(_env_file=None, **_valid_kwargs(secret_key="a" * 32))
        assert s.secret_key.get_secret_value() == "a" * 32

    def test_database_url_wrong_scheme_fails(self):
        with pytest.raises(ValidationError, match="postgresql"):
            Settings(
                _env_file=None,
                **_valid_kwargs(database_url="mysql://u:p@db:3306/x"),
            )

    def test_database_url_accepts_psycopg_async(self):
        s = Settings(
            _env_file=None,
            **_valid_kwargs(
                database_url="postgresql+psycopg://u:p@db:5432/x"
            ),
        )
        assert "psycopg" in s.database_url

    def test_database_url_accepts_plain_postgresql(self):
        s = Settings(
            _env_file=None,
            **_valid_kwargs(database_url="postgresql://u:p@db:5432/x"),
        )
        assert s.database_url.startswith("postgresql://")

    def test_log_level_invalid_fails(self):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **_valid_kwargs(log_level="VERBOSE"))

    def test_log_level_accepts_standard_levels(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
            s = Settings(_env_file=None, **_valid_kwargs(log_level=level))
            assert s.log_level == level


class TestSettingsSecretLeakage:
    def test_secret_key_not_in_repr(self):
        """SecretStr no debe filtrar el valor en logs/repr."""
        s = Settings(_env_file=None, **_valid_kwargs())
        assert "x" * 32 not in repr(s)
        assert "x" * 32 not in str(s)

    def test_anthropic_key_not_in_repr(self):
        s = Settings(_env_file=None, **_valid_kwargs())
        assert "sk-ant-test-key" not in repr(s)


class TestMigrationsUrl:
    def test_falls_back_to_database_url(self):
        s = Settings(_env_file=None, **_valid_kwargs())
        assert s.migrations_url == s.database_url

    def test_prefers_migration_database_url_when_set(self):
        owner = "postgresql+asyncpg://kisabella:pw@db:5432/kisabella"
        s = Settings(_env_file=None, **_valid_kwargs(migration_database_url=owner))
        assert s.migrations_url == owner
