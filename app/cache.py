"""
Cache de scripts de transformação — tabela scripts_transformacao.

Estratégia de identificação de CSVs similares:
  hash = SHA-256( sorted(colunas) + sorted(tipos_de_erro_detectados) )

Isso garante que dois arquivos com a mesma estrutura de colunas E os
mesmos tipos de problema reutilizem o mesmo script, independente do
conteúdo. É mais preciso do que usar só as colunas, porque um arquivo
com nomes errados E data errada precisa de um script diferente de um
que só tem data errada.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .database import get_connection, DB_PATH

logger = logging.getLogger(__name__)


# ── Hash ──────────────────────────────────────────────────────────────

def gerar_hash_estrutura(df: pd.DataFrame, tipos_erro: list[str]) -> str:
    """
    Gera hash baseado em:
    - Colunas do CSV (ordenadas)
    - Tipos de erro detectados (ordenados)

    Dois CSVs com a mesma estrutura E mesmos problemas → mesmo hash → mesmo script.
    """
    payload = {
        "colunas": sorted(df.columns.tolist()),
        "erros": sorted(set(tipos_erro)),
    }
    serializado = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


# ── Cache de Scripts ──────────────────────────────────────────────────

def buscar_script_cache(hash_estrutura: str, db_path: Path = DB_PATH) -> Optional[str]:
    """Busca script salvo para este hash. Retorna None se não encontrado."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT script_python FROM scripts_transformacao WHERE hash_estrutura = ?",
            (hash_estrutura,),
        ).fetchone()

        if row:
            # Incrementa contador de reutilizações
            conn.execute(
                """UPDATE scripts_transformacao
                   SET vezes_utilizado = vezes_utilizado + 1,
                       updated_at = ?
                   WHERE hash_estrutura = ?""",
                (datetime.now().isoformat(), hash_estrutura),
            )
            logger.info("[INFO] Cache HIT — hash: %s", hash_estrutura[:16])
            return row["script_python"]

    logger.info("[INFO] Cache MISS — hash: %s", hash_estrutura[:16])
    return None


def salvar_script_cache(
    hash_estrutura: str,
    script: str,
    descricao: str = "",
    db_path: Path = DB_PATH,
) -> None:
    """Persiste script validado no cache. INSERT OR REPLACE para idempotência."""
    now = datetime.now().isoformat()
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO scripts_transformacao
                   (hash_estrutura, script_python, descricao, vezes_utilizado, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?)
               ON CONFLICT(hash_estrutura) DO UPDATE SET
                   script_python    = excluded.script_python,
                   descricao        = excluded.descricao,
                   vezes_utilizado  = vezes_utilizado + 1,
                   updated_at       = excluded.updated_at""",
            (hash_estrutura, script, descricao, now, now),
        )
    logger.info("[INFO] Script salvo no cache — hash: %s", hash_estrutura[:16])


# ── Log de Ingestão ───────────────────────────────────────────────────

def registrar_log_ingestao(
    arquivo_nome: str,
    registros_total: int,
    registros_sucesso: int,
    registros_erro: int,
    usou_ia: bool,
    script_id: Optional[int],
    duracao_segundos: float,
    db_path: Path = DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO log_ingestao
               (arquivo_nome, registros_total, registros_sucesso, registros_erro,
                usou_ia, script_id, duracao_segundos)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (arquivo_nome, registros_total, registros_sucesso, registros_erro,
             int(usou_ia), script_id, duracao_segundos),
        )


def buscar_id_script(hash_estrutura: str, db_path: Path = DB_PATH) -> Optional[int]:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM scripts_transformacao WHERE hash_estrutura = ?",
            (hash_estrutura,),
        ).fetchone()
        return row["id"] if row else None