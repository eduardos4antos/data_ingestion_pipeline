"""
Fallback Manual — Correção de CSV sem IA.

Este módulo é ativado quando:
1. A API da IA excede a quota (429 RESOURCE_EXHAUSTED)
2. A API key não está configurada
3. O usuário opta por não usar a IA

O fallback aplica correções rigorosas baseadas nos erros detectados:
- Renomeação de colunas via aliases do template
- Conversão de formato de data (DD/MM/YYYY → YYYY-MM-DD)
- Conversão de valores monetários (R$ 1.234,56 → 1234.56)
- Mapeamento de valores enum (C → CREDITO, D → DEBITO)
- Remoção de colunas extras
"""

import logging
import re
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def aplicar_fallback_manual(
    df: pd.DataFrame,
    detalhes_validacao: list[dict],
    template: dict,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Aplica correções manuais rigorosas baseadas nos erros detectados.
    
    Returns:
        (DataFrame corrigido, lista de correções aplicadas)
    """
    correcoes = []
    df_corrigido = df.copy()
    
    # 1. Renomear colunas pelos aliases
    df_corrigido, ops = _renomear_colunas(df_corrigido, template)
    correcoes.extend(ops)
    
    # 2. Converter formato de data
    df_corrigido, ops = _converter_data(df_corrigido, template)
    correcoes.extend(ops)
    
    # 3. Converter formato de valor
    df_corrigido, ops = _converter_valor(df_corrigido, template)
    correcoes.extend(ops)
    
    # 4. Mapear valores enum
    df_corrigido, ops = _mapear_enum(df_corrigido, template)
    correcoes.extend(ops)
    
    # 5. Remover colunas extras (não presentes no template)
    df_corrigido, ops = _remover_colunas_extras(df_corrigido, template)
    correcoes.extend(ops)
    
    # 6. Preencher colunas faltantes com默认值
    df_corrigido, ops = _preencher_colunas_faltantes(df_corrigido, template)
    correcoes.extend(ops)
    
    return df_corrigido, correcoes


def _renomear_colunas(df: pd.DataFrame, template: dict) -> tuple[pd.DataFrame, list[str]]:
    correcoes = []
    colunas_template = template.get("colunas", {})
    
    for nome_coluna, config in colunas_template.items():
        aliases = config.get("aliases", [])
        
        for alias in aliases:
            if alias in df.columns and alias != nome_coluna:
                
                # 🔥 Se já existe a coluna destino → faz MERGE
                if nome_coluna in df.columns:
                    df[nome_coluna] = df[nome_coluna].fillna(df[alias])
                    df = df.drop(columns=[alias])
                    correcoes.append(f"Mesclar '{alias}' em '{nome_coluna}'")
                else:
                    df = df.rename(columns={alias: nome_coluna})
                    correcoes.append(f"Renomear '{alias}' → '{nome_coluna}'")
                
                break  # evita múltiplos aliases para mesma coluna
    
    return df, correcoes


def _converter_data(df: pd.DataFrame, template: dict) -> tuple[pd.DataFrame, list[str]]:
    """Converte datas para formato YYYY-MM-DD."""
    correcoes = []
    colunas_template = template.get("colunas", {})
    
    # Identificar coluna de data
    coluna_data = None
    for nome_coluna, config in colunas_template.items():
        if config.get("tipo") == "date":
            if nome_coluna in df.columns:
                coluna_data = nome_coluna
                break
    
    if coluna_data is None:
        return df, correcoes
    
    coluna = df[coluna_data]
    
    # Tentar múltiplos formatos
    formatos = [
        "%d/%m/%Y",      # 27/04/2026
        "%d-%m-%Y",      # 27-04-2026
        "%d.%m.%Y",      # 27.04.2026
        "%Y-%m-%d",      # 2026-04-27 (já correto)
        "%m/%d/%Y",      # 04/27/2026
        "%Y/%m/%d",      # 2026/04/27
    ]
    
    for fmt in formatos:
        try:
            df[coluna_data] = pd.to_datetime(coluna, format=fmt, dayfirst=True)
            df[coluna_data] = df[coluna_data].dt.strftime("%Y-%m-%d")
            correcoes.append(f"Converter '{coluna_data}' de {fmt} → YYYY-MM-DD")
            logger.info("[FALLBACK] Data convertida: formato %s", fmt)
            break
        except:
            continue
    
    return df, correcoes


def _converter_valor(df: pd.DataFrame, template: dict) -> tuple[pd.DataFrame, list[str]]:
    """Converte valores monetários para decimal."""
    correcoes = []
    colunas_template = template.get("colunas", {})
    
    # Identificar coluna de valor
    coluna_valor = None
    for nome_coluna, config in colunas_template.items():
        if config.get("tipo") == "decimal":
            if nome_coluna in df.columns:
                coluna_valor = nome_coluna
                break
    
    if coluna_valor is None:
        return df, correcoes
    
    coluna = df[coluna_valor].astype(str)
    
    # Aplicar transformação: R$ 1.234,56 → 1234.56
    # 1. Remover "R$" e espaços
    coluna = coluna.str.replace(r"R\$\s*", "", regex=True)
    # 2. Remover pontos de milhar (.)
    coluna = coluna.str.replace(r"\.", "", regex=True)
    # 3. Trocar vírgula por ponto
    coluna = coluna.str.replace(",", ".", regex=False)
    # 4. Converter para float
    coluna = pd.to_numeric(coluna, errors="coerce")
    
    df[coluna_valor] = coluna
    correcoes.append(f"Converter '{coluna_valor}' de formato BR para decimal")
    logger.info("[FALLBACK] Valor convertido para decimal")
    
    return df, correcoes


def _mapear_enum(df: pd.DataFrame, template: dict) -> tuple[pd.DataFrame, list[str]]:
    """Mapeia valores enum usando os mapeamentos do template."""
    correcoes = []
    colunas_template = template.get("colunas", {})
    
    for nome_coluna, config in colunas_template.items():
        if config.get("tipo") == "enum":
            if nome_coluna not in df.columns:
                continue
            
            mapeamento = config.get("validacao", {}).get("mapeamento", {})
            if not mapeamento:
                continue
            
            # Aplicar mapeamento (case insensitive)
            coluna = df[nome_coluna].astype(str).str.upper()
            
            for valor_antigo, valor_novo in mapeamento.items():
                mask = coluna == valor_antigo.upper()
                if mask.any():
                    df.loc[mask, nome_coluna] = valor_novo
                    correcoes.append(f"Mapear '{nome_coluna}': '{valor_antigo}' → '{valor_novo}'")
    
    if correcoes:
        logger.info("[FALLBACK] Valores enum mapeados: %d alterações", len(correcoes))
    
    return df, correcoes


def _remover_colunas_extras(df: pd.DataFrame, template: dict) -> tuple[pd.DataFrame, list[str]]:
    """Remove colunas que não existem no template."""
    correcoes = []
    
    colunas_template = set(template.get("colunas", {}).keys())
    colunas_df = set(df.columns)
    
    colunas_extras = colunas_df - colunas_template
    
    if colunas_extras:
        df = df.drop(columns=list(colunas_extras))
        correcoes.append(f"Remover colunas extras: {list(colunas_extras)}")
        logger.info("[FALLBACK] Colunas extras removidas: %s", colunas_extras)
    
    return df, correcoes


def _preencher_colunas_faltantes(df: pd.DataFrame, template: dict) -> tuple[pd.DataFrame, list[str]]:
    """Preenche colunas obrigatórias faltantes com valores padrão."""
    correcoes = []
    
    colunas_template = template.get("colunas", {})
    colunas_df = set(df.columns)
    
    for nome_coluna, config in colunas_template.items():
        if config.get("obrigatorio") and nome_coluna not in colunas_df:
            # Definir valor padrão baseado no tipo
            tipo = config.get("tipo")
            
            if tipo == "date":
                df[nome_coluna] = datetime.now().strftime("%Y-%m-%d")
            elif tipo == "decimal":
                df[nome_coluna] = 0.0
            elif tipo == "enum":
                valores = config.get("validacao", {}).get("valores_permitidos", [])
                df[nome_coluna] = valores[0] if valores else "OUTROS"
            else:
                df[nome_coluna] = None
            
            correcoes.append(f"Preencher coluna '{nome_coluna}' com padrão: {df[nome_coluna].iloc[0]}")
    
    if correcoes:
        logger.info("[FALLBACK] Colunas faltantes preenchidas: %d", len(correcoes))
    
    return df, correcoes


def gerar_resumo_fallback(correcoes: list[str]) -> str:
    """Gera um resumo textual das correções aplicadas."""
    if not correcoes:
        return "Nenhuma correção necessária."
    
    linhas = ["### Correções Aplicadas:", ""]
    for i, correcao in enumerate(correcoes, 1):
        linhas.append(f"{i}. {correcao}")
    
    return "\n".join(linhas)