"""Aplica as migrations SQL do projeto sem recriar o banco."""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import ConfigurationError, Settings
from app.database import create_database_engine


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        raise SystemExit(f"Configuração inválida: {exc}") from exc
    migrations = sorted((Path(__file__).resolve().parent.parent / "migrations").glob("*_up.sql"))
    if not migrations:
        raise SystemExit("Nenhuma migration encontrada.")
    engine = create_database_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            for migration in migrations:
                logging.info("Aplicando %s", migration.name)
                connection.exec_driver_sql(migration.read_text(encoding="utf-8"))
                connection.commit()
    finally:
        engine.dispose()
    logging.info("Migrations aplicadas com sucesso.")


if __name__ == "__main__":
    main()
