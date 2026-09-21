-- Rollback estrutural. Não remove dados em raw.api_medicoes.
BEGIN;
DROP INDEX IF EXISTS dw.idx_raw_api_medicoes_requisicao;
DROP INDEX IF EXISTS dw.idx_fato_medicao_observado_consulta;
DROP INDEX IF EXISTS dw.idx_fato_medicao_previsao_consulta;
DROP INDEX IF EXISTS dw.uq_fato_medicao_versao_api;
ALTER TABLE dw.fato_medicao DROP CONSTRAINT IF EXISTS fk_medicao_raw;
ALTER TABLE dw.fato_medicao DROP CONSTRAINT IF EXISTS ck_fato_medicao_tipo_dado;
ALTER TABLE dw.fato_medicao DROP COLUMN IF EXISTS raw_id;
ALTER TABLE dw.fato_medicao DROP COLUMN IF EXISTS qualificacao;
ALTER TABLE dw.fato_medicao DROP COLUMN IF EXISTS tipo_dado;
ALTER TABLE raw.api_medicoes DROP COLUMN IF EXISTS mensagem_erro;
ALTER TABLE raw.api_medicoes DROP COLUMN IF EXISTS quantidade_registros;
ALTER TABLE raw.api_medicoes DROP COLUMN IF EXISTS tempo_resposta_ms;
ALTER TABLE raw.api_medicoes DROP COLUMN IF EXISTS status_http;
ALTER TABLE raw.api_medicoes DROP COLUMN IF EXISTS endpoint;
ALTER TABLE raw.api_medicoes DROP COLUMN IF EXISTS data_hora_requisicao;
COMMIT;
