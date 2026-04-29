"""
Inicialização e acesso ao banco SQLite.
Usa o schema.sql oficial do desafio — sem alterações.
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "database" / "pipeline.db"
SCHEMA_PATH = ROOT / "database" / "schema.sql"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_banco(db_path: Path = DB_PATH) -> None:
    """Cria todas as tabelas usando o schema.sql oficial."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    with get_connection(db_path) as conn:
        conn.executescript(schema)
    logger.info("[INFO] Banco inicializado: %s", db_path)