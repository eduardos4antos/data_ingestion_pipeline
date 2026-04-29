"""
Ingestão de dados na tabela transacoes_financeiras.

Mapeia as colunas do DataFrame corrigido para as colunas do schema.sql.
Usa INSERT OR IGNORE para evitar duplicatas (id_transacao é PRIMARY KEY).
"""

import logging
from typing import Optional
import pandas as pd

from .database import get_connection, DB_PATH
from pathlib import Path

logger = logging.getLogger(__name__)

# Colunas que existem na tabela transacoes_financeiras (schema.sql)
COLUNAS_TABELA = [
    "id_transacao",
    "data_transacao",
    "valor",
    "tipo",
    "categoria",
    "descricao",
    "conta_origem",
    "conta_destino",
    "status",
]


def ingesting_dataframe(
    df: pd.DataFrame,
    db_path: Path = DB_PATH,
) -> tuple[int, int, list[str]]:
    """
    Insere as linhas do DataFrame na tabela transacoes_financeiras.

    Estratégia linha a linha para capturar erros individuais sem abortar tudo.

    Returns:
        (sucesso, erros, lista_de_mensagens_de_erro)
    """
    # Garante que só tentamos inserir colunas que existem na tabela
    cols_disponiveis = [c for c in COLUNAS_TABELA if c in df.columns]
    df_para_inserir = df[cols_disponiveis].copy()

    # Preenche NaN com None (SQLite aceita NULL)
    df_para_inserir = df_para_inserir.where(pd.notna(df_para_inserir), other=None)

    sucesso = 0
    erros = 0
    mensagens_erro = []

    placeholders = ", ".join(["?"] * len(cols_disponiveis))
    colunas_sql = ", ".join(cols_disponiveis)
    sql = f"INSERT OR IGNORE INTO transacoes_financeiras ({colunas_sql}) VALUES ({placeholders})"

    with get_connection(db_path) as conn:
        for idx, row in df_para_inserir.iterrows():
            valores = tuple(row[c] for c in cols_disponiveis)
            try:
                conn.execute(sql, valores)
                sucesso += 1
            except Exception as e:
                erros += 1
                msg = f"Linha {idx}: {e}"
                mensagens_erro.append(msg)
                logger.warning("[WARN] Falha ao inserir linha %d: %s", idx, e)

    logger.info("[SUCCESS] Ingestão: %d inseridos, %d erros", sucesso, erros)
    return sucesso, erros, mensagens_erro