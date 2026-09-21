"""Acesso ao PostgreSQL sem alteração do esquema existente."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def create_database_engine(database_url: str) -> Engine:
    """Cria um engine com verificação de conexões reaproveitadas."""
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
    )


def check_database_connection(engine: Engine) -> None:
    """Falha cedo se o PostgreSQL estiver indisponível."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ConnectionError("Não foi possível conectar ao PostgreSQL.") from exc
