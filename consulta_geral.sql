WITH ultimo_payload AS (
    SELECT
        raw_id,
        fonte_id,
        data_hora_requisicao,
        data_hora_ingestao,
        status_http,
        tempo_resposta_ms,
        quantidade_registros,
        payload
    FROM raw.api_medicoes
    ORDER BY raw_id DESC
    LIMIT 1
),
medicoes AS (
    SELECT
        up.*,
        jsonb_array_elements(up.payload) AS medicao
    FROM ultimo_payload up
)
SELECT
    m.raw_id,
    m.data_hora_requisicao,
    m.data_hora_ingestao AS data_hora_ingestao_raw,
    m.status_http,
    m.tempo_resposta_ms,

    (m.medicao->>'datahora')::timestamp AS data_hora_local_api,

    -- Interpretação correta do horário sem timezone da API:
    (m.medicao->>'datahora')::timestamp
        AT TIME ZONE 'America/Recife' AS data_hora_referencia_utc,

    m.medicao->>'codestacao' AS codigo_estacao,
    estacao.nome AS estacao,

    (m.medicao->>'id_sensor')::integer AS codigo_sensor,
    sensor.nome AS nome_sensor,

    NULLIF(m.medicao->>'valor', '')::double precision AS valor_raw,
    m.medicao->>'qualificacao' AS qualificacao_raw,
    m.medicao->>'uf' AS uf,

    fato.medicao_id,
    fato.tipo_dado,
    fato.data_hora_medicao AS data_hora_medicao_dw,
    fato.data_hora_ingestao AS data_hora_ingestao_dw,
    fato.valor AS valor_dw,
    fato.qualificacao AS qualificacao_dw,

    CASE
        WHEN fato.medicao_id IS NULL THEN 'NAO_CARREGADO_NO_DW'
        ELSE 'CARREGADO_NO_DW'
    END AS status_processamento
FROM medicoes m
LEFT JOIN dw.dim_estacao estacao
    ON estacao.fonte_id = m.fonte_id
   AND estacao.codigo_estacao = m.medicao->>'codestacao'
LEFT JOIN dw.dim_sensor sensor
    ON sensor.fonte_id = m.fonte_id
   AND sensor.codigo_sensor = m.medicao->>'id_sensor'
LEFT JOIN dw.fato_medicao fato
    ON fato.raw_id = m.raw_id
   AND fato.estacao_id = estacao.estacao_id
   AND fato.sensor_id = sensor.sensor_id
ORDER BY data_hora_referencia_utc DESC, codigo_estacao, codigo_sensor;