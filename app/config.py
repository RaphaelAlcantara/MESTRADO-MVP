"""Leitura e validação das configurações da aplicação."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Indica uma configuração ausente ou inválida."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Configuração obrigatória ausente: {name}")
    return value


def _positive_int(name: str) -> int:
    raw_value = _required(name)
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} deve ser um número inteiro positivo.") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} deve ser maior que zero.")
    return value


@dataclass(frozen=True)
class Settings:
    cemaden_email: str
    cemaden_password: str
    cemaden_token_url: str
    cemaden_data_url: str
    cemaden_sensor_url: str
    codibge: str
    uf: str
    cemaden_rede: str
    database_url: str
    interval_seconds: int
    token_refresh_margin_seconds: int
    request_timeout_seconds: int

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "Settings":
        """Carrega o arquivo .env e valida as configurações obrigatórias."""
        load_dotenv(dotenv_path=env_file)
        settings = cls(
            cemaden_email=_required("CEMADEN_EMAIL"),
            cemaden_password=_required("CEMADEN_PASSWORD"),
            cemaden_token_url=_required("CEMADEN_TOKEN_URL"),
            cemaden_data_url=_required("CEMADEN_DATA_URL"),
            cemaden_sensor_url=_required("CEMADEN_SENSOR_URL"),
            codibge=_required("CODIBGE"),
            uf=_required("UF"),
            cemaden_rede=_required("CEMADEN_REDE"),
            database_url=_required("DATABASE_URL"),
            interval_seconds=_positive_int("INTERVAL_SECONDS"),
            token_refresh_margin_seconds=_positive_int(
                "TOKEN_REFRESH_MARGIN_SECONDS"
            ),
            request_timeout_seconds=_positive_int("REQUEST_TIMEOUT_SECONDS"),
        )
        return settings
