"""Cliente HTTP para autenticação e consulta à PED/CEMADEN."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from app.config import Settings

LOGGER = logging.getLogger(__name__)


class CemadenClient:
    """Mantém token exclusivamente em memória e renova-o quando necessário."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = requests.Session()
        self._token: str | None = None
        self._expires_at: float | None = None

    def close(self) -> None:
        self._session.close()

    def token_is_valid(self) -> bool:
        """Retorna se há token com margem de segurança antes do vencimento."""
        return bool(
            self._token
            and self._expires_at
            and time.monotonic()
            < self._expires_at - self._settings.token_refresh_margin_seconds
        )

    def get_token(self) -> None:
        """Solicita um token novo. Nunca registra credenciais ou token em log."""
        try:
            response = self._session.post(
                self._settings.cemaden_token_url,
                json={
                    "email": self._settings.cemaden_email,
                    "password": self._settings.cemaden_password,
                },
                timeout=self._settings.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            raise RuntimeError("Timeout ao obter token do CEMADEN.") from exc
        except requests.RequestException as exc:
            raise RuntimeError("Falha HTTP ao obter token do CEMADEN.") from exc
        except ValueError as exc:
            raise RuntimeError("Resposta de token do CEMADEN não contém JSON válido.") from exc

        token = payload.get("token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError("Resposta de token do CEMADEN não contém o campo token.")

        seconds_to_expiry = self._parse_time_to_exp(payload.get("timeToExp"))
        self._token = token
        self._expires_at = time.monotonic() + seconds_to_expiry
        LOGGER.info("Novo token obtido.")

    def ensure_token(self) -> None:
        if not self.token_is_valid():
            self.get_token()

    def get_recent_data(self) -> Any:
        """Consulta dados recentes e refaz uma única vez após 400/401."""
        self.ensure_token()
        # A PED exige ``rede`` e ``uf`` neste endpoint; codibge restringe a consulta
        # ao Recife. Os campos do retorno continuam sem qualquer normalização.
        params = {
            "rede": self._settings.cemaden_rede,
            "codibge": self._settings.codibge,
            "uf": self._settings.uf,
        }
        return self._request_json(
            url=self._settings.cemaden_data_url,
            params=params,
            resource_name="dados do CEMADEN",
            refresh_attempted=False,
        )

    def get_sensor_catalog(self) -> Any:
        """Obtém o catálogo oficial de sensores e tipos de estação da PED."""
        self.ensure_token()
        return self._request_json(
            url=self._settings.cemaden_sensor_url,
            params={},
            resource_name="catálogo de sensores do CEMADEN",
            refresh_attempted=False,
        )

    def _request_json(
        self,
        url: str,
        params: dict[str, str],
        resource_name: str,
        refresh_attempted: bool,
    ) -> Any:
        try:
            LOGGER.info("Consultando %s.", resource_name)
            response = self._session.get(
                url,
                headers={"token": self._token or ""},
                params=params,
                timeout=self._settings.request_timeout_seconds,
            )
        except requests.Timeout as exc:
            raise RuntimeError("Timeout na comunicação com o CEMADEN.") from exc
        except requests.ConnectionError as exc:
            raise RuntimeError("Erro de conexão com o CEMADEN.") from exc
        except requests.RequestException as exc:
            raise RuntimeError("Falha ao consultar dados do CEMADEN.") from exc

        if response.status_code in (400, 401) and not refresh_attempted:
            LOGGER.warning("Token rejeitado pela API. Renovando.")
            self._token = None
            self._expires_at = None
            self.get_token()
            return self._request_json(
                url=url,
                params=params,
                resource_name=resource_name,
                refresh_attempted=True,
            )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"CEMADEN respondeu com HTTP {response.status_code}."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Resposta de dados do CEMADEN não contém JSON válido.") from exc
        LOGGER.info("Consulta realizada com sucesso. HTTP %s.", response.status_code)
        return payload

    @staticmethod
    def _parse_time_to_exp(value: Any) -> float:
        """Converte timeToExp para segundos, com fallback explícito de quatro horas."""
        fallback_seconds = 4 * 60 * 60
        if value is None:
            LOGGER.warning("timeToExp ausente; usando fallback de 4 horas.")
            return fallback_seconds
        try:
            seconds = float(value)
            if seconds <= 0:
                raise ValueError
            return seconds
        except (TypeError, ValueError):
            LOGGER.warning("timeToExp inválido; usando fallback de 4 horas.")
            return fallback_seconds
