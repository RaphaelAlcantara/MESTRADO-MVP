# CEMADEN Recife — Ingestão RAW e DW

Coletor contínuo dos dados recentes do CEMADEN para o Recife. Cada resposta é preservada em `raw.api_medicoes` e seus registros válidos são carregados em `dw.fato_medicao`.

## Migration obrigatória

Antes de iniciar esta versão, aplique `migrations/001_observado_previsto_up.sql` e `migrations/002_chave_nula_variavel_up.sql`, nesta ordem, no banco existente. As migrations só usam `ALTER TABLE` e índices/constraints, e conservam os dados; registros históricos recebem `DESCONHECIDO`, pois não há base segura para classificá-los retroativamente. O rollback estrutural da primeira está em `migrations/001_observado_previsto_down.sql`.

Com o ambiente virtual ativado, a forma recomendada de aplicá-las é:

```powershell
python -m app.migrate
```

`data_hora_medicao` é a hora de referência do fenômeno; `data_hora_ingestao` é quando o coletor recebeu o registro. A API entrega `datahora` sem offset, portanto ela é interpretada como `America/Recife` e armazenada como `TIMESTAMPTZ` em UTC. Como a API não traz uma flag, referências até dois minutos após a ingestão são `OBSERVADO` (tolerância para atraso/arredondamento); referências posteriores são `PREVISTO`.

Previsões não são sobrescritas: a identidade inclui estação, sensor, variável, referência, ingestão, tipo, qualificação e valor. A mesma leitura reprocessada no mesmo instante é ignorada; uma nova previsão para a mesma referência com outra ingestão é mantida. `qualificacao` fica guardada e também participa da identidade para não ocultar retornos distintos. Consulte `sql/validacao_observado_previsto.sql` para histórico e relação previsão × observado.

## Pré-requisitos

- Python 3.10 ou superior;
- PostgreSQL/PostGIS com o banco `cemaden_recife`, schemas e tabelas já existentes;
- uma linha `CEMADEN` em `dw.dim_fonte`, com a sigla `CEMADEN`.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Crie/preencha o arquivo local `.env` com as variáveis apresentadas na seção de configurações abaixo. Ele é ignorado pelo Git e nunca deve ser versionado.

## Execução

```powershell
python -m app.main
```

O processo valida a conexão com o banco antes de iniciar. Em cada ciclo, ele obtém ou reutiliza um token em memória, consulta a PED, persiste o JSON e transforma os itens válidos. Falhas por item são registradas e não interrompem o lote; falhas transitórias de API ou banco não encerram o processo. Interrompa com `Ctrl+C`.

Na inicialização, o processo também sincroniza o catálogo oficial de sensores em
`dw.dim_sensor`. Para executar somente essa sincronização, sem iniciar a coleta
contínua, use:

```powershell
python -m app.sync_sensors
```

## Configurações importantes

- `INTERVAL_SECONDS=60`: uma coleta por minuto durante o desenvolvimento. Para dez minutos, altere apenas para `INTERVAL_SECONDS=600`.
- `TOKEN_REFRESH_MARGIN_SECONDS=300`: margem para renovar o token antes da expiração informada em `timeToExp`.
- `REQUEST_TIMEOUT_SECONDS=30`: limite de cada chamada HTTP.
- `CODIBGE=2611606`, `UF=PE` e `CEMADEN_REDE=11`: parâmetros usados na consulta do Recife. A PED exige `rede` e `uf`; `codibge` restringe a resposta ao município.
- `CEMADEN_SENSOR_URL`: endpoint do catálogo de sensores, usado para preencher e atualizar `dw.dim_sensor` sem duplicidades.

## Consulta de validação

```sql
SELECT raw_id, fonte_id, data_hora_ingestao
FROM raw.api_medicoes
ORDER BY raw_id DESC;

SELECT payload
FROM raw.api_medicoes
ORDER BY raw_id DESC
LIMIT 1;
```

Não execute o script `script_banco_criacao.sql` como parte deste coletor: ele não é necessário para a ingestão e o programa não emite DDL.
