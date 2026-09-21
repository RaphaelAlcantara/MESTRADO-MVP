--Create Database
CREATE DATABASE cemaden_recife

--instala plugin do postgis
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT PostGIS_Version();

-- Criar schema do banco
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS spatial;

--testa se criou o schema
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name IN ('raw', 'dw', 'spatial');

--Criar dim_fonte
--Essa será a tabela que resolve as escolhas sobre APAC/INMET/CEMADEN.

CREATE TABLE dw.dim_fonte (
    fonte_id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    sigla VARCHAR(20) NOT NULL UNIQUE,
    descricao TEXT,
    url VARCHAR(500),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

--inserindo cemaden no dim_fonte
INSERT INTO dw.dim_fonte (
    nome,
    sigla,
    descricao,
    url
)
VALUES (
    'Centro Nacional de Monitoramento e Alertas de Desastres Naturais',
    'CEMADEN',
    'Fonte de dados ambientais e de monitoramento de estações.',
    'https://www.cemaden.gov.br'
);

--testando fontes
SELECT *
FROM dw.dim_fonte;

--Criar dim_estacao
CREATE TABLE dw.dim_estacao (
    estacao_id BIGSERIAL PRIMARY KEY,

    fonte_id INTEGER NOT NULL,

    codigo_estacao VARCHAR(100) NOT NULL,
    nome VARCHAR(255),

    uf CHAR(2),
    municipio VARCHAR(150),
    codibge INTEGER,

    tipo_estacao VARCHAR(100),

    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    geom GEOMETRY(Point, 4326),

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_estacao_fonte
        FOREIGN KEY (fonte_id)
        REFERENCES dw.dim_fonte(fonte_id),

    CONSTRAINT uq_estacao_fonte_codigo
        UNIQUE (fonte_id, codigo_estacao)
);

--index spacial
CREATE INDEX idx_estacao_geom
ON dw.dim_estacao
USING GIST (geom);

--variaveis dimensoes
CREATE TABLE dw.dim_variavel (
    variavel_id SERIAL PRIMARY KEY,

    nome VARCHAR(100) NOT NULL UNIQUE,

    descricao TEXT,

    unidade_padrao VARCHAR(30),

    categoria VARCHAR(50),

    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

--inserçao dos dados cemaden
INSERT INTO dw.dim_variavel
    (nome, descricao, unidade_padrao, categoria)
VALUES
    ('Precipitação', 'Precipitação atmosférica', 'mm', 'Hidrologia'),

    ('Umidade do Solo', 'Umidade volumétrica do solo', '%', 'Geotecnia'),

    ('Temperatura do Ar', 'Temperatura do ar', '°C', 'Meteorologia'),

    ('Umidade Relativa', 'Umidade relativa do ar', '%', 'Meteorologia'),

    ('Pressão Atmosférica', 'Pressão atmosférica', 'hPa', 'Meteorologia'),

    ('Velocidade do Vento', 'Velocidade do vento', 'm/s', 'Meteorologia');

--criar dim_sensor
CREATE TABLE dw.dim_sensor (
    sensor_id BIGSERIAL PRIMARY KEY,

    fonte_id INTEGER NOT NULL,

    codigo_sensor VARCHAR(100) NOT NULL,

    nome VARCHAR(255),

    descricao TEXT,

    variavel_id INTEGER,

    unidade_origem VARCHAR(30),

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_sensor_fonte
        FOREIGN KEY (fonte_id)
        REFERENCES dw.dim_fonte(fonte_id),

    CONSTRAINT fk_sensor_variavel
        FOREIGN KEY (variavel_id)
        REFERENCES dw.dim_variavel(variavel_id),

    CONSTRAINT uq_sensor_fonte_codigo
        UNIQUE (fonte_id, codigo_sensor)
);

--fato medicao
CREATE TABLE dw.fato_medicao (
    medicao_id BIGSERIAL PRIMARY KEY,

    fonte_id INTEGER NOT NULL,

    estacao_id BIGINT NOT NULL,

    sensor_id BIGINT NOT NULL,

    variavel_id INTEGER,

    data_hora_medicao TIMESTAMPTZ NOT NULL,

    valor DOUBLE PRECISION,

    unidade VARCHAR(30),

    data_hora_ingestao TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    fonte_dado VARCHAR(50) NOT NULL DEFAULT 'API',

    CONSTRAINT fk_medicao_fonte
        FOREIGN KEY (fonte_id)
        REFERENCES dw.dim_fonte(fonte_id),

    CONSTRAINT fk_medicao_estacao
        FOREIGN KEY (estacao_id)
        REFERENCES dw.dim_estacao(estacao_id),

    CONSTRAINT fk_medicao_sensor
        FOREIGN KEY (sensor_id)
        REFERENCES dw.dim_sensor(sensor_id),

    CONSTRAINT fk_medicao_variavel
        FOREIGN KEY (variavel_id)
        REFERENCES dw.dim_variavel(variavel_id)
);

--indices da fato
CREATE INDEX idx_medicao_data
ON dw.fato_medicao (data_hora_medicao);

CREATE INDEX idx_medicao_estacao
ON dw.fato_medicao (estacao_id);

CREATE INDEX idx_medicao_sensor
ON dw.fato_medicao (sensor_id);

CREATE INDEX idx_medicao_estacao_data
ON dw.fato_medicao (
    estacao_id,
    data_hora_medicao
);

CREATE TABLE raw.api_medicoes (
    raw_id BIGSERIAL PRIMARY KEY,

    fonte_id INTEGER,

    data_hora_ingestao TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    payload JSONB
);

