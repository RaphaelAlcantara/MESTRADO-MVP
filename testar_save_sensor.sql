WITH ultimo_payload AS (
    SELECT payload
    FROM raw.api_medicoes
    ORDER BY raw_id DESC
    LIMIT 1
),
medicoes AS (
    SELECT jsonb_array_elements(payload) AS medicao
    FROM ultimo_payload
)
SELECT
    (medicao->>'datahora')::timestamp AS data_hora,
    medicao->>'codestacao' AS codigo_estacao,
    medicao->>'nome' AS estacao,
    (medicao->>'id_sensor')::integer AS codigo_sensor,
    sensor.nome AS nome_sensor,
    NULLIF(medicao->>'valor', '')::double precision AS valor,
    medicao->>'uf' AS uf
FROM medicoes
JOIN dw.dim_fonte AS fonte
    ON fonte.sigla = 'CEMADEN'
LEFT JOIN dw.dim_sensor AS sensor
    ON sensor.fonte_id = fonte.fonte_id
   AND sensor.codigo_sensor = medicao->>'id_sensor'
ORDER BY data_hora DESC;