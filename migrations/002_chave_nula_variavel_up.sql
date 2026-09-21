-- PostgreSQL considera NULL distinto em índices UNIQUE. Sensores sem variável
-- mapeada precisam usar uma sentinela somente na expressão de identidade.
BEGIN;
DROP INDEX IF EXISTS dw.uq_fato_medicao_versao_api;
CREATE UNIQUE INDEX uq_fato_medicao_versao_api
ON dw.fato_medicao (
    fonte_id, estacao_id, sensor_id, COALESCE(variavel_id, -1),
    data_hora_medicao, data_hora_ingestao, tipo_dado,
    COALESCE(qualificacao, ''), COALESCE(valor, 'NaN'::double precision)
);
COMMIT;
