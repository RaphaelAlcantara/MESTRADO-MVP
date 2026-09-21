"""Persistência da camada RAW, sem transformação analítica do payload."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

LOGGER = logging.getLogger(__name__)


def save_raw_payload(engine: Engine, payload: Any, source_sigla: str = "CEMADEN") -> None:
    """Grava o JSON original associado à fonte cadastrada em ``dw.dim_fonte``."""
    try:
        serialized_payload = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("O payload recebido não pode ser serializado como JSON.") from exc

    source_query = text(
        "SELECT fonte_id FROM dw.dim_fonte WHERE UPPER(sigla) = UPPER(:sigla)"
    )
    insert_query = text(
        """
        INSERT INTO raw.api_medicoes (fonte_id, data_hora_ingestao, payload)
        VALUES (:fonte_id, CURRENT_TIMESTAMP, CAST(:payload AS jsonb))
        """
    )
    try:
        with engine.begin() as connection:
            fonte_id = connection.execute(source_query, {"sigla": source_sigla}).scalar_one_or_none()
            if fonte_id is None:
                raise LookupError(
                    f"Fonte {source_sigla!r} não encontrada em dw.dim_fonte."
                )
            connection.execute(
                insert_query, {"fonte_id": fonte_id, "payload": serialized_payload}
            )
    except SQLAlchemyError as exc:
        raise ConnectionError("Erro de conexão ou persistência no PostgreSQL.") from exc
    LOGGER.info("Payload salvo no PostgreSQL.")


def sync_sensor_catalog(
    engine: Engine, catalog: Any, source_sigla: str = "CEMADEN"
) -> int:
    """Sincroniza o catálogo da PED em ``dw.dim_sensor`` sem duplicar sensores.

    O endpoint agrupa sensores por tipo de estação. Como o modelo atual não possui
    uma tabela de associação sensor--tipo, esta função mantém o catálogo global de
    cada código de sensor por fonte.
    """
    if not isinstance(catalog, list):
        raise ValueError("Catálogo de sensores deve ser uma lista JSON.")

    sensors: dict[str, str] = {}
    for station_type in catalog:
        if not isinstance(station_type, dict):
            raise ValueError("Item inválido no catálogo de sensores.")
        sensor_list = station_type.get("sensor")
        if not isinstance(sensor_list, list):
            raise ValueError("Catálogo sem lista 'sensor' válida.")
        for item in sensor_list:
            if not isinstance(item, dict):
                raise ValueError("Sensor inválido no catálogo.")
            code = item.get("sensor")
            description = item.get("sensordescricao")
            if code is None or not isinstance(description, str) or not description.strip():
                raise ValueError("Sensor sem código ou descrição válida.")
            code_as_text = str(code)
            previous = sensors.setdefault(code_as_text, description.strip())
            if previous != description.strip():
                LOGGER.warning(
                    "Código de sensor %s tem descrições divergentes; mantendo a primeira.",
                    code_as_text,
                )

    source_query = text(
        "SELECT fonte_id FROM dw.dim_fonte WHERE UPPER(sigla) = UPPER(:sigla)"
    )
    upsert_query = text(
        """
        INSERT INTO dw.dim_sensor
            (fonte_id, codigo_sensor, nome, descricao, ativo, data_cadastro)
        VALUES
            (:fonte_id, :codigo_sensor, :nome, :descricao, TRUE, CURRENT_TIMESTAMP)
        ON CONFLICT (fonte_id, codigo_sensor) DO UPDATE
        SET nome = EXCLUDED.nome,
            descricao = EXCLUDED.descricao,
            ativo = TRUE
        """
    )
    try:
        with engine.begin() as connection:
            fonte_id = connection.execute(source_query, {"sigla": source_sigla}).scalar_one_or_none()
            if fonte_id is None:
                raise LookupError(
                    f"Fonte {source_sigla!r} não encontrada em dw.dim_fonte."
                )
            connection.execute(
                upsert_query,
                [
                    {
                        "fonte_id": fonte_id,
                        "codigo_sensor": code,
                        "nome": description,
                        "descricao": description,
                    }
                    for code, description in sensors.items()
                ],
            )
    except SQLAlchemyError as exc:
        raise ConnectionError("Erro de conexão ou persistência no PostgreSQL.") from exc
    LOGGER.info("Catálogo de sensores sincronizado: %s sensores.", len(sensors))
    return len(sensors)
