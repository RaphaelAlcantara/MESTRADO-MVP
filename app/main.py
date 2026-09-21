"""Ponto de entrada do processo contínuo de ingestão."""

from __future__ import annotations

import logging
import time

from app.cemaden import CemadenClient
from app.config import ConfigurationError, Settings
from app.database import check_database_connection, create_database_engine
from app.ingestion import process_payload_to_dw, save_raw_payload, sync_sensor_catalog


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        logger.critical("Erro de configuração: %s", exc)
        raise SystemExit(2) from exc

    engine = create_database_engine(settings.database_url)
    try:
        check_database_connection(engine)
    except ConnectionError as exc:
        logger.critical("%s", exc)
        raise SystemExit(3) from exc

    logger.info("=" * 60)
    logger.info("CEMADEN INGESTOR")
    logger.info("=" * 60)
    logger.info("Intervalo de coleta: %s segundos", settings.interval_seconds)

    client = CemadenClient(settings)
    try:
        try:
            sensor_catalog = client.get_sensor_catalog()
            sync_sensor_catalog(engine, sensor_catalog)
        except Exception:
            logger.exception("Falha ao sincronizar catálogo de sensores; a coleta continuará.")

        while True:
            cycle_started = time.monotonic()
            try:
                payload = client.get_recent_data()
                raw = save_raw_payload(engine, payload, **client.last_response_metadata)
                process_payload_to_dw(engine, payload, raw)
            except Exception:  # mantém o serviço ativo; detalhes ficam no log
                logger.exception("Falha no ciclo de ingestão; o próximo ciclo será tentado.")

            elapsed = time.monotonic() - cycle_started
            wait_seconds = max(0.0, settings.interval_seconds - elapsed)
            logger.info("Próxima coleta em aproximadamente %.1f segundos.", wait_seconds)
            time.sleep(wait_seconds)
    except KeyboardInterrupt:
        logger.info("Encerramento solicitado pelo usuário.")
    finally:
        client.close()
        engine.dispose()


if __name__ == "__main__":
    main()
