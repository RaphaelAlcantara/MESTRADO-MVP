-- Evolução não destrutiva da ingestão CEMADEN.
-- Execute uma única vez no banco cemaden_recife, depois do script base.
BEGIN;

ALTER TABLE raw.api_medicoes
    ADD COLUMN IF NOT EXISTS data_hora_requisicao TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS endpoint VARCHAR(500),
    ADD COLUMN IF NOT EXISTS status_http INTEGER,
    ADD COLUMN IF NOT EXISTS tempo_resposta_ms INTEGER,
    ADD COLUMN IF NOT EXISTS quantidade_registros INTEGER,
    ADD COLUMN IF NOT EXISTS mensagem_erro TEXT;

ALTER TABLE dw.fato_medicao
    ADD COLUMN IF NOT EXISTS tipo_dado VARCHAR(20),
    ADD COLUMN IF NOT EXISTS qualificacao VARCHAR(100),
    ADD COLUMN IF NOT EXISTS raw_id BIGINT;

-- Não se infere o passado: linhas existentes recebem DESCONHECIDO.
UPDATE dw.fato_medicao
SET tipo_dado = 'DESCONHECIDO'
WHERE tipo_dado IS NULL;

ALTER TABLE dw.fato_medicao
    ALTER COLUMN tipo_dado SET DEFAULT 'DESCONHECIDO',
    ALTER COLUMN tipo_dado SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_fato_medicao_tipo_dado'
    ) THEN
        ALTER TABLE dw.fato_medicao
            ADD CONSTRAINT ck_fato_medicao_tipo_dado
            CHECK (tipo_dado IN ('OBSERVADO', 'PREVISTO', 'DESCONHECIDO'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_medicao_raw'
    ) THEN
        ALTER TABLE dw.fato_medicao
            ADD CONSTRAINT fk_medicao_raw
            FOREIGN KEY (raw_id) REFERENCES raw.api_medicoes(raw_id);
    END IF;
END $$;

-- A qualificação participa da identidade pois a API pode devolvê-la diferente.
-- O valor também participa para não descartar leituras conflitantes recebidas no
-- mesmo instante; a repetição idêntica é ignorada pelo ON CONFLICT do coletor.
CREATE UNIQUE INDEX IF NOT EXISTS uq_fato_medicao_versao_api
ON dw.fato_medicao (
    fonte_id, estacao_id, sensor_id, variavel_id,
    data_hora_medicao, data_hora_ingestao, tipo_dado,
    COALESCE(qualificacao, ''), COALESCE(valor, 'NaN'::double precision)
);

CREATE INDEX IF NOT EXISTS idx_fato_medicao_previsao_consulta
ON dw.fato_medicao (estacao_id, sensor_id, variavel_id,
                    data_hora_medicao, data_hora_ingestao)
WHERE tipo_dado = 'PREVISTO';

CREATE INDEX IF NOT EXISTS idx_fato_medicao_observado_consulta
ON dw.fato_medicao (estacao_id, sensor_id, variavel_id, data_hora_medicao)
WHERE tipo_dado = 'OBSERVADO';

CREATE INDEX IF NOT EXISTS idx_raw_api_medicoes_requisicao
ON raw.api_medicoes (data_hora_requisicao DESC);

COMMIT;
