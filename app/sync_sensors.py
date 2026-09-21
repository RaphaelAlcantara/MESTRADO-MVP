"""Comando único para sincronizar o catálogo de sensores do CEMADEN."""

from __future__ import annotations

import logging

from app.cemaden import CemadenClient
from app.config import ConfigurationError, Settings
from app.database import check_database_connection, create_database_engine
from app.ingestion import sync_sensor_catalog
from app.main import configure_logging


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    try:
        settings = Settings.from_env()
        engine = create_database_engine(settings.database_url)
        check_database_connection(engine)
    except (ConfigurationError, ConnectionError) as exc:
        logger.critical("Não foi possível iniciar sincronização: %s", exc)
        raise SystemExit(2) from exc

    client = CemadenClient(settings)
    try:
        total = sync_sensor_catalog(engine, client.get_sensor_catalog())
        logger.info("Sincronização concluída: %s sensores ativos.", total)
    finally:
        client.close()
        engine.dispose()


if __name__ == "__main__":
    main()
