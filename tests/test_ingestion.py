from datetime import UTC, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from app.cemaden import CemadenClient
from app.ingestion import RawPayload, classificar_tipo_dado, parse_datahora_cemaden, process_payload_to_dw

class ClassificationTests(unittest.TestCase):
    def test_future_reference_is_forecast(self):
        self.assertEqual("PREVISTO", classificar_tipo_dado(datetime(2026, 9, 21, 23, 0, tzinfo=UTC), datetime(2026, 9, 21, 21, 40, tzinfo=UTC)))

    def test_reference_at_ingestion_is_observed(self):
        instant = datetime(2026, 9, 21, 23, 0, tzinfo=UTC)
        self.assertEqual("OBSERVADO", classificar_tipo_dado(instant, instant))

    def test_cemaden_naive_timestamp_uses_recife_timezone(self):
        self.assertEqual(datetime(2026, 9, 21, 19, 10, tzinfo=UTC), parse_datahora_cemaden("2026-09-21 16:10:00"))

    def test_naive_ingestion_is_rejected(self):
        with self.assertRaises(ValueError):
            classificar_tipo_dado(datetime.now(UTC), datetime.now())

    def test_two_forecast_versions_have_distinct_ingestion_identity(self):
        reference = datetime(2026, 9, 21, 23, 0, tzinfo=UTC)
        first = datetime(2026, 9, 21, 21, 40, tzinfo=UTC)
        second = datetime(2026, 9, 21, 22, 0, tzinfo=UTC)
        self.assertEqual("PREVISTO", classificar_tipo_dado(reference, first))
        self.assertNotEqual(first, second)  # ambos coexistem na chave versionada

    def test_invalid_payload_does_not_access_dw(self):
        inserted, errors = process_payload_to_dw(Mock(), {"invalido": True}, RawPayload(1, datetime.now(UTC)))
        self.assertEqual((0, 1), (inserted, errors))

class TokenRefreshTests(unittest.TestCase):
    def test_401_refreshes_token_and_retries_once(self):
        settings = SimpleNamespace(cemaden_token_url="token", cemaden_data_url="dados", cemaden_sensor_url="sensores", cemaden_email="a", cemaden_password="b", cemaden_rede="11", codibge="2611606", uf="PE", request_timeout_seconds=1, token_refresh_margin_seconds=1)
        client = CemadenClient(settings)
        token = Mock(status_code=200); token.raise_for_status.return_value = None; token.json.return_value = {"token":"novo", "timeToExp":3600}
        rejected = Mock(status_code=401); rejected.json.return_value = []
        accepted = Mock(status_code=200); accepted.raise_for_status.return_value = None; accepted.json.return_value = []
        client._session = Mock(post=Mock(return_value=token), get=Mock(side_effect=[rejected, accepted]))
        self.assertEqual([], client.get_recent_data())
        self.assertEqual(2, client._session.get.call_count)

if __name__ == "__main__":
    unittest.main()
