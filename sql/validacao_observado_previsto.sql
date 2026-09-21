-- Histórico de versões previstas/observadas para uma referência.
SELECT * FROM dw.fato_medicao
WHERE estacao_id = :estacao_id AND sensor_id = :sensor_id
  AND data_hora_medicao = :data_hora_referencia
ORDER BY data_hora_ingestao;

SELECT tipo_dado, COUNT(*) FROM dw.fato_medicao GROUP BY tipo_dado;

SELECT data_hora_ingestao, data_hora_medicao, valor, qualificacao, tipo_dado
FROM dw.fato_medicao
WHERE estacao_id = :estacao_id AND sensor_id = :sensor_id
ORDER BY data_hora_medicao, data_hora_ingestao;

-- Base para erro: uma previsão é ligada à observação de mesma chave espacial,
-- variável e hora de referência. Há uma linha por versão da previsão.
SELECT p.estacao_id, p.sensor_id, p.variavel_id,
       p.data_hora_medicao AS data_hora_referencia,
       p.data_hora_ingestao AS data_hora_previsao,
       p.valor AS valor_previsto, o.valor AS valor_observado,
       ABS(o.valor - p.valor) AS erro_absoluto,
       EXTRACT(EPOCH FROM (p.data_hora_medicao - p.data_hora_ingestao)) / 60
           AS horizonte_minutos
FROM dw.fato_medicao p
JOIN dw.fato_medicao o
  ON o.estacao_id = p.estacao_id
 AND o.sensor_id = p.sensor_id
 AND o.variavel_id IS NOT DISTINCT FROM p.variavel_id
 AND o.data_hora_medicao = p.data_hora_medicao
 AND o.tipo_dado = 'OBSERVADO'
WHERE p.tipo_dado = 'PREVISTO';
