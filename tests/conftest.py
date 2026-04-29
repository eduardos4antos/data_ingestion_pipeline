"""
Fixtures compartilhadas para os testes do CSV Validator.

Este arquivo contem fixtures que serao utilizadas pelos testes.
NAO MODIFIQUE ESTE ARQUIVO - ele faz parte do desafio.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

# Diretorio raiz do projeto
ROOT_DIR = Path(__file__).parent.parent
SAMPLE_DATA_DIR = ROOT_DIR / "sample_data"
DATABASE_DIR = ROOT_DIR / "database"


@pytest.fixture
def template_schema():
    """Carrega o schema de validacao do template.json"""
    template_path = DATABASE_DIR / "template.json"
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def db_connection():
    """Cria uma conexao SQLite em memoria para testes."""
    conn = sqlite3.connect(":memory:")

    # Executa o schema para criar as tabelas
    schema_path = DATABASE_DIR / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    yield conn
    conn.close()


@pytest.fixture
def sample_csv_perfeito():
    """Retorna o caminho para o CSV perfeito."""
    return SAMPLE_DATA_DIR / "perfeito.csv"


@pytest.fixture
def sample_csv_colunas_extras():
    """Retorna o caminho para o CSV com colunas extras."""
    return SAMPLE_DATA_DIR / "colunas_extras.csv"


@pytest.fixture
def sample_csv_colunas_faltando():
    """Retorna o caminho para o CSV com colunas faltando."""
    return SAMPLE_DATA_DIR / "colunas_faltando.csv"


@pytest.fixture
def sample_csv_nomes_diferentes():
    """Retorna o caminho para o CSV com nomes de colunas diferentes."""
    return SAMPLE_DATA_DIR / "nomes_diferentes.csv"


@pytest.fixture
def sample_csv_formato_data_br():
    """Retorna o caminho para o CSV com datas em formato brasileiro."""
    return SAMPLE_DATA_DIR / "formato_data_br.csv"


@pytest.fixture
def sample_csv_formato_valor_br():
    """Retorna o caminho para o CSV com valores em formato brasileiro."""
    return SAMPLE_DATA_DIR / "formato_valor_br.csv"


@pytest.fixture
def sample_csv_encoding_latin1():
    """Retorna o caminho para o CSV em encoding Latin-1."""
    return SAMPLE_DATA_DIR / "encoding_latin1.csv"


@pytest.fixture
def sample_csv_delimitador_pv():
    """Retorna o caminho para o CSV com delimitador ponto-e-virgula."""
    return SAMPLE_DATA_DIR / "delimitador_pv.csv"


@pytest.fixture
def sample_csv_multiplos_problemas():
    """Retorna o caminho para o CSV com multiplos problemas."""
    return SAMPLE_DATA_DIR / "multiplos_problemas.csv"


@pytest.fixture
def temp_output_dir():
    """Cria um diretorio temporario para outputs de teste."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def colunas_obrigatorias(template_schema):
    """Retorna lista de colunas obrigatorias baseada no template."""
    return [
        nome for nome, config in template_schema["colunas"].items()
        if config.get("obrigatorio", False)
    ]


@pytest.fixture
def categorias_validas(template_schema):
    """Retorna lista de categorias validas."""
    return template_schema["colunas"]["categoria"]["validacao"]["valores_permitidos"]


@pytest.fixture
def tipos_validos(template_schema):
    """Retorna lista de tipos de transacao validos."""
    return template_schema["colunas"]["tipo"]["validacao"]["valores_permitidos"]


@pytest.fixture
def status_validos(template_schema):
    """Retorna lista de status validos."""
    return template_schema["colunas"]["status"]["validacao"]["valores_permitidos"]
