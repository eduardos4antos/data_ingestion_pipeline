"""
Modulo de validacao de arquivos CSV.

Este e um modulo de REFERENCIA para testar a estrutura do desafio.
NAO deve ser entregue ao candidato.
"""

import re
from pathlib import Path
from typing import Any

import chardet
import pandas as pd


def detectar_encoding(filepath: Path | str) -> str:
    """Detecta o encoding de um arquivo."""
    with open(filepath, "rb") as f:
        raw_data = f.read(10000)
    result = chardet.detect(raw_data)
    return result["encoding"] or "utf-8"


def detectar_delimitador(filepath: Path | str, encoding: str = None) -> str:
    """Detecta o delimitador de um arquivo CSV."""
    if encoding is None:
        encoding = detectar_encoding(filepath)

    with open(filepath, "r", encoding=encoding) as f:
        primeira_linha = f.readline()

    # Conta ocorrencias de delimitadores comuns
    delimitadores = [",", ";", "\t", "|"]
    contagens = {d: primeira_linha.count(d) for d in delimitadores}

    # Retorna o mais frequente
    return max(contagens, key=contagens.get)


def carregar_csv(filepath: Path | str) -> pd.DataFrame:
    """Carrega um CSV com deteccao automatica de encoding e delimitador."""
    encoding = detectar_encoding(filepath)
    delimitador = detectar_delimitador(filepath, encoding)

    return pd.read_csv(filepath, encoding=encoding, delimiter=delimitador)


def validar_colunas_obrigatorias(df: pd.DataFrame, template: dict) -> dict:
    """Valida se todas as colunas obrigatorias estao presentes."""
    colunas_obrigatorias = [
        nome for nome, config in template["colunas"].items()
        if config.get("obrigatorio", False)
    ]

    colunas_presentes = set(df.columns)
    colunas_faltando = []

    for col in colunas_obrigatorias:
        if col not in colunas_presentes:
            # Verifica aliases
            aliases = template["colunas"][col].get("aliases", [])
            if not any(alias in colunas_presentes for alias in aliases):
                colunas_faltando.append(col)

    return {
        "valido": len(colunas_faltando) == 0,
        "colunas_faltando": colunas_faltando
    }


def validar_nomes_colunas(df: pd.DataFrame, template: dict) -> dict:
    """Valida nomes de colunas e sugere mapeamentos."""
    colunas_presentes = set(df.columns)
    colunas_template = set(template["colunas"].keys())

    mapeamento_sugerido = {}
    colunas_desconhecidas = []

    for col in colunas_presentes:
        if col in colunas_template:
            continue

        # Procura nos aliases
        encontrado = False
        for nome_template, config in template["colunas"].items():
            aliases = config.get("aliases", [])
            if col in aliases:
                mapeamento_sugerido[col] = nome_template
                encontrado = True
                break

        if not encontrado:
            colunas_desconhecidas.append(col)

    return {
        "valido": len(mapeamento_sugerido) == 0,
        "mapeamento_sugerido": mapeamento_sugerido,
        "colunas_desconhecidas": colunas_desconhecidas
    }


def validar_formato_data(df: pd.DataFrame, coluna: str, template: dict) -> dict:
    """Valida o formato das datas em uma coluna."""
    if coluna not in df.columns:
        return {"valido": False, "formato_detectado": None, "linhas_invalidas": []}

    valores = df[coluna].astype(str)

    # Padroes de data
    padroes = {
        "YYYY-MM-DD": r"^\d{4}-\d{2}-\d{2}$",
        "DD/MM/YYYY": r"^\d{2}/\d{2}/\d{4}$",
        "DD-MM-YYYY": r"^\d{2}-\d{2}-\d{4}$",
        "MM/DD/YYYY": r"^\d{2}/\d{2}/\d{4}$",
    }

    formato_detectado = None
    linhas_invalidas = []

    for formato, padrao in padroes.items():
        matches = valores.str.match(padrao)
        if matches.sum() > len(valores) * 0.5:
            formato_detectado = formato
            linhas_invalidas = df.index[~matches].tolist()
            break

    return {
        "valido": formato_detectado == "YYYY-MM-DD",
        "formato_detectado": formato_detectado,
        "linhas_invalidas": linhas_invalidas
    }


def validar_formato_valor(df: pd.DataFrame, coluna: str, template: dict) -> dict:
    """Valida o formato dos valores monetarios."""
    if coluna not in df.columns:
        return {"valido": False, "formato_detectado": None, "linhas_invalidas": []}

    valores = df[coluna].astype(str)

    # Verifica se contem R$ ou virgula como decimal
    tem_rs = valores.str.contains(r"R\$", regex=True).any()
    tem_virgula_decimal = valores.str.contains(r"\d,\d", regex=True).any()

    if tem_rs:
        formato_detectado = "brasileiro (R$)"
    elif tem_virgula_decimal:
        formato_detectado = "brasileiro (virgula)"
    else:
        formato_detectado = "decimal"

    # Tenta converter para numerico
    linhas_invalidas = []
    for idx, val in valores.items():
        try:
            # Remove R$, pontos de milhar, troca virgula por ponto
            val_limpo = val.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
            float(val_limpo)
        except ValueError:
            linhas_invalidas.append(idx)

    return {
        "valido": formato_detectado == "decimal" and len(linhas_invalidas) == 0,
        "formato_detectado": formato_detectado,
        "linhas_invalidas": linhas_invalidas
    }


def validar_enum(df: pd.DataFrame, coluna: str, template: dict) -> dict:
    """Valida se os valores de uma coluna enum sao validos."""
    if coluna not in df.columns:
        return {"valido": False, "valores_invalidos": [], "mapeamento_sugerido": {}}

    config = template["colunas"].get(coluna, {})
    validacao = config.get("validacao", {})
    valores_permitidos = validacao.get("valores_permitidos", [])
    mapeamento = validacao.get("mapeamento", {})

    valores_unicos = df[coluna].dropna().unique()
    valores_invalidos = []
    mapeamento_sugerido = {}

    for val in valores_unicos:
        val_str = str(val).strip()
        if val_str in valores_permitidos:
            continue
        if val_str in mapeamento:
            mapeamento_sugerido[val_str] = mapeamento[val_str]
        else:
            # Tenta case insensitive
            val_upper = val_str.upper()
            if val_upper in valores_permitidos:
                mapeamento_sugerido[val_str] = val_upper
            elif val_str.lower() in mapeamento:
                mapeamento_sugerido[val_str] = mapeamento[val_str.lower()]
            else:
                valores_invalidos.append(val_str)

    return {
        "valido": len(valores_invalidos) == 0 and len(mapeamento_sugerido) == 0,
        "valores_invalidos": valores_invalidos,
        "mapeamento_sugerido": mapeamento_sugerido
    }


def validar_csv_completo(filepath: Path | str, template: dict) -> dict:
    """Executa todas as validacoes em um CSV."""
    try:
        df = carregar_csv(filepath)
    except Exception as e:
        return {
            "valido": False,
            "total_erros": 1,
            "detalhes": [{"tipo": "erro_leitura", "mensagem": str(e)}]
        }

    detalhes = []

    # Validar colunas obrigatorias
    resultado_colunas = validar_colunas_obrigatorias(df, template)
    if not resultado_colunas["valido"]:
        detalhes.append({
            "tipo": "colunas_faltando",
            "colunas": resultado_colunas["colunas_faltando"]
        })

    # Validar nomes de colunas
    resultado_nomes = validar_nomes_colunas(df, template)
    if not resultado_nomes["valido"]:
        detalhes.append({
            "tipo": "nomes_colunas",
            "mapeamento": resultado_nomes["mapeamento_sugerido"]
        })

    # Validar formato de data (se a coluna existir)
    coluna_data = "data_transacao"
    if coluna_data not in df.columns:
        # Procura alias
        for alias in template["colunas"][coluna_data].get("aliases", []):
            if alias in df.columns:
                coluna_data = alias
                break

    if coluna_data in df.columns:
        resultado_data = validar_formato_data(df, coluna_data, template)
        if not resultado_data["valido"]:
            detalhes.append({
                "tipo": "formato_data",
                "formato_detectado": resultado_data["formato_detectado"]
            })

    # Validar formato de valor
    coluna_valor = "valor"
    if coluna_valor not in df.columns:
        for alias in template["colunas"][coluna_valor].get("aliases", []):
            if alias in df.columns:
                coluna_valor = alias
                break

    if coluna_valor in df.columns:
        resultado_valor = validar_formato_valor(df, coluna_valor, template)
        if not resultado_valor["valido"]:
            detalhes.append({
                "tipo": "formato_valor",
                "formato_detectado": resultado_valor["formato_detectado"]
            })

    return {
        "valido": len(detalhes) == 0,
        "total_erros": len(detalhes),
        "detalhes": detalhes
    }


def gerar_relatorio_divergencias(filepath: Path | str, template: dict) -> str:
    """Gera um relatorio textual das divergencias encontradas."""
    resultado = validar_csv_completo(filepath, template)

    if resultado["valido"]:
        return "Nenhuma divergencia encontrada. O arquivo esta em conformidade com o template."

    linhas = ["=== RELATORIO DE DIVERGENCIAS ===\n"]

    for detalhe in resultado["detalhes"]:
        tipo = detalhe.get("tipo", "desconhecido")

        if tipo == "colunas_faltando":
            linhas.append(f"COLUNAS OBRIGATORIAS FALTANDO:")
            for col in detalhe["colunas"]:
                linhas.append(f"  - {col}")

        elif tipo == "nomes_colunas":
            linhas.append(f"COLUNAS COM NOMES DIFERENTES:")
            for origem, destino in detalhe["mapeamento"].items():
                linhas.append(f"  - '{origem}' -> '{destino}'")

        elif tipo == "formato_data":
            linhas.append(f"FORMATO DE DATA INCORRETO:")
            linhas.append(f"  Detectado: {detalhe['formato_detectado']}")
            linhas.append(f"  Esperado: YYYY-MM-DD")

        elif tipo == "formato_valor":
            linhas.append(f"FORMATO DE VALOR INCORRETO:")
            linhas.append(f"  Detectado: {detalhe['formato_detectado']}")
            linhas.append(f"  Esperado: decimal (ex: 1234.56)")

        elif tipo == "erro_leitura":
            linhas.append(f"ERRO AO LER ARQUIVO:")
            linhas.append(f"  {detalhe['mensagem']}")

        linhas.append("")

    linhas.append(f"Total de problemas: {resultado['total_erros']}")

    return "\n".join(linhas)
