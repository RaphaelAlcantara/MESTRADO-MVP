"""Persistência RAW e transformação auditável para a camada DW."""
from __future__ import annotations

import json, logging, math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

LOGGER = logging.getLogger(__name__)
RECIFE_TIMEZONE = ZoneInfo("America/Recife")

@dataclass(frozen=True)
class RawPayload:
    raw_id: int
    data_hora_ingestao: datetime

def classificar_tipo_dado(referencia: datetime, ingestao: datetime, tolerancia_observacao_minutos: int = 2) -> str:
    """A PED não traz flag: referências até a tolerância são observadas; futuras, previstas."""
    if referencia.tzinfo is None or ingestao.tzinfo is None:
        raise ValueError("Timestamps devem conter timezone.")
    return "OBSERVADO" if referencia.astimezone(UTC) <= ingestao.astimezone(UTC) + timedelta(minutes=tolerancia_observacao_minutos) else "PREVISTO"

def parse_datahora_cemaden(value: Any) -> datetime:
    """`datahora` sem offset da PED é horário civil America/Recife."""
    if not isinstance(value, str) or not value.strip(): raise ValueError("Campo datahora ausente ou inválido.")
    try: result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc: raise ValueError(f"Timestamp CEMADEN inválido: {value!r}") from exc
    return (result if result.tzinfo else result.replace(tzinfo=RECIFE_TIMEZONE)).astimezone(UTC)

def save_raw_payload(engine: Engine, payload: Any, source_sigla: str = "CEMADEN", *, data_hora_requisicao: datetime | None = None, endpoint: str | None = None, status_http: int | None = None, tempo_resposta_ms: int | None = None, mensagem_erro: str | None = None) -> RawPayload:
    """Preserva resposta original e seus metadados de auditoria."""
    try: serialized = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as exc: raise ValueError("Payload não serializável como JSON.") from exc
    ingestao = datetime.now(UTC)
    try:
        with engine.begin() as c:
            fonte = c.execute(text("SELECT fonte_id FROM dw.dim_fonte WHERE UPPER(sigla)=UPPER(:s)"), {"s":source_sigla}).scalar_one_or_none()
            if fonte is None: raise LookupError(f"Fonte {source_sigla!r} não encontrada.")
            row = c.execute(text("""
              INSERT INTO raw.api_medicoes (fonte_id,data_hora_ingestao,data_hora_requisicao,endpoint,status_http,tempo_resposta_ms,quantidade_registros,mensagem_erro,payload)
              VALUES (:f,:i,:r,:e,:s,:t,:q,:m,CAST(:p AS jsonb)) RETURNING raw_id,data_hora_ingestao
            """), {"f":fonte,"i":ingestao,"r":data_hora_requisicao,"e":endpoint,"s":status_http,"t":tempo_resposta_ms,"q":len(payload) if isinstance(payload,list) else None,"m":mensagem_erro,"p":serialized}).one()
    except SQLAlchemyError as exc: raise ConnectionError("Erro de persistência RAW no PostgreSQL.") from exc
    LOGGER.info("Payload RAW salvo: raw_id=%s.", row.raw_id)
    return RawPayload(row.raw_id, row.data_hora_ingestao)

_FACT_UPSERT = text("""
INSERT INTO dw.fato_medicao (fonte_id,estacao_id,sensor_id,variavel_id,data_hora_medicao,valor,unidade,data_hora_ingestao,fonte_dado,tipo_dado,qualificacao,raw_id)
VALUES (:f,:e,:s,:v,:ref,:valor,:unidade,:ing,'API',:tipo,:qual,:raw)
ON CONFLICT (fonte_id,estacao_id,sensor_id,COALESCE(variavel_id,-1),data_hora_medicao,data_hora_ingestao,tipo_dado,COALESCE(qualificacao,''),COALESCE(valor,'NaN'::double precision)) DO NOTHING
""")

def process_payload_to_dw(engine: Engine, payload: Any, raw: RawPayload, source_sigla: str = "CEMADEN") -> tuple[int,int]:
    """Resolve dimensões; registra erros por registro e continua o lote."""
    if not isinstance(payload,list):
        LOGGER.error("RAW %s não é uma lista JSON.",raw.raw_id); return 0,1
    inserted = errors = 0
    try:
      with engine.begin() as c:
        fonte=c.execute(text("SELECT fonte_id FROM dw.dim_fonte WHERE UPPER(sigla)=UPPER(:s)"),{"s":source_sigla}).scalar_one_or_none()
        if fonte is None: raise LookupError(f"Fonte {source_sigla!r} não encontrada.")
        for pos, record in enumerate(payload):
          try:
            params=_params(c,fonte,record,raw)
            inserted += c.execute(_FACT_UPSERT,params).rowcount
          except (ValueError,LookupError,SQLAlchemyError) as exc:
            errors += 1; LOGGER.warning("RAW %s registro %s não processado: %s",raw.raw_id,pos,exc)
    except SQLAlchemyError as exc: raise ConnectionError("Erro de persistência DW no PostgreSQL.") from exc
    LOGGER.info("RAW %s transformado: inseridos=%s inválidos=%s.",raw.raw_id,inserted,errors)
    return inserted,errors

def _params(c: Any, fonte: int, record: Any, raw: RawPayload) -> dict[str,Any]:
    if not isinstance(record,dict): raise ValueError("Registro não é um objeto JSON.")
    estacao=_text(record.get("codestacao"),"codestacao"); sensor_code=_text(record.get("id_sensor"),"id_sensor")
    ref=parse_datahora_cemaden(record.get("datahora")); valor=_number(record.get("valor"),"valor")
    lat=_optional_number(record.get("latitude")); lon=_optional_number(record.get("longitude"))
    station=c.execute(text("""
      INSERT INTO dw.dim_estacao (fonte_id,codigo_estacao,nome,uf,municipio,latitude,longitude,geom,ativo)
      VALUES (:f,:code,:nome,:uf,:cidade,:lat,:lon,CASE WHEN :lat IS NULL OR :lon IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(:lon,:lat),4326) END,TRUE)
      ON CONFLICT (fonte_id,codigo_estacao) DO UPDATE SET nome=COALESCE(EXCLUDED.nome,dw.dim_estacao.nome),uf=COALESCE(EXCLUDED.uf,dw.dim_estacao.uf),municipio=COALESCE(EXCLUDED.municipio,dw.dim_estacao.municipio),latitude=COALESCE(EXCLUDED.latitude,dw.dim_estacao.latitude),longitude=COALESCE(EXCLUDED.longitude,dw.dim_estacao.longitude),geom=COALESCE(EXCLUDED.geom,dw.dim_estacao.geom),ativo=TRUE RETURNING estacao_id
    """),{"f":fonte,"code":estacao,"nome":_optional_text(record.get("nome")),"uf":_optional_text(record.get("uf")),"cidade":_optional_text(record.get("cidade")),"lat":lat,"lon":lon}).one().estacao_id
    sensor=c.execute(text("SELECT sensor_id,variavel_id,unidade_origem FROM dw.dim_sensor WHERE fonte_id=:f AND codigo_sensor=:s"),{"f":fonte,"s":sensor_code}).one_or_none()
    if sensor is None: raise LookupError(f"Sensor {sensor_code} inexistente; sincronize o catálogo.")
    return {"f":fonte,"e":station,"s":sensor.sensor_id,"v":sensor.variavel_id,"ref":ref,"valor":valor,"unidade":sensor.unidade_origem,"ing":raw.data_hora_ingestao,"tipo":classificar_tipo_dado(ref,raw.data_hora_ingestao),"qual":_optional_text(record.get("qualificacao")),"raw":raw.raw_id}

def _optional_text(value: Any) -> str|None:
    if value is None:return None
    value=str(value).strip(); return value or None
def _text(value: Any,name: str) -> str:
    result=_optional_text(value)
    if result is None: raise ValueError(f"Campo {name} ausente ou inválido.")
    return result
def _optional_number(value: Any) -> float|None:
    if value is None or value=="": return None
    return _number(value,"número")
def _number(value: Any,name: str) -> float:
    try: result=float(value)
    except (TypeError,ValueError) as exc: raise ValueError(f"Campo {name} inválido.") from exc
    if not math.isfinite(result): raise ValueError(f"Campo {name} não finito.")
    return result

def sync_sensor_catalog(engine: Engine, catalog: Any, source_sigla: str = "CEMADEN") -> int:
    """Sincroniza o catálogo oficial sem duplicar sensores."""
    if not isinstance(catalog,list): raise ValueError("Catálogo de sensores deve ser uma lista JSON.")
    sensors:dict[str,str]={}
    for group in catalog:
      if not isinstance(group,dict) or not isinstance(group.get("sensor"),list): raise ValueError("Item inválido no catálogo.")
      for item in group["sensor"]:
        if not isinstance(item,dict) or item.get("sensor") is None or not _optional_text(item.get("sensordescricao")): raise ValueError("Sensor inválido no catálogo.")
        sensors.setdefault(str(item["sensor"]),_optional_text(item["sensordescricao"]) or "")
    try:
      with engine.begin() as c:
        fonte=c.execute(text("SELECT fonte_id FROM dw.dim_fonte WHERE UPPER(sigla)=UPPER(:s)"),{"s":source_sigla}).scalar_one_or_none()
        if fonte is None: raise LookupError(f"Fonte {source_sigla!r} não encontrada.")
        c.execute(text("INSERT INTO dw.dim_sensor (fonte_id,codigo_sensor,nome,descricao,ativo) VALUES (:f,:code,:name,:name,TRUE) ON CONFLICT (fonte_id,codigo_sensor) DO UPDATE SET nome=EXCLUDED.nome,descricao=EXCLUDED.descricao,ativo=TRUE"),[{"f":fonte,"code":code,"name":name} for code,name in sensors.items()])
    except SQLAlchemyError as exc: raise ConnectionError("Erro de persistência no PostgreSQL.") from exc
    LOGGER.info("Catálogo sincronizado: %s sensores.",len(sensors)); return len(sensors)
