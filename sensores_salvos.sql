SELECT
    sensor.codigo_sensor,
    sensor.nome,
    sensor.descricao,
    sensor.ativo
FROM dw.dim_sensor AS sensor
JOIN dw.dim_fonte AS fonte
    ON fonte.fonte_id = sensor.fonte_id
WHERE fonte.sigla = 'CEMADEN'
ORDER BY sensor.codigo_sensor::integer;