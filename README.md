# CEMADEN Recife — Ingestão RAW

Coletor contínuo dos dados recentes do CEMADEN para o Recife. Esta primeira versão armazena exclusivamente o JSON original em `raw.api_medicoes`; não há carga para `dw.fato_medicao`.

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

O processo valida a conexão com o banco antes de iniciar. Em cada ciclo, ele obtém ou reutiliza um token em memória, consulta a PED e persiste o JSON sem transformação. Falhas transitórias de API ou banco são registradas e não encerram o processo. Interrompa com `Ctrl+C`.

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
