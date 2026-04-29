"""
Execução segura de scripts gerados pela IA.

Por que exec() em vez de subprocess?
  - O script manipula um DataFrame em memória. Não há arquivo para ler/escrever.
  - subprocess exigiria serializar/deserializar o DataFrame (lento, complexo).
  - exec() com escopo isolado é suficiente e direto.

Segurança implementada:
  - __builtins__ substituído por whitelist explícita
  - Sem acesso a os, sys, open, __import__
  - Captura completa de erros com traceback
"""

import traceback
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)

# Apenas o que um script de transformação de dados precisa
_BUILTINS_SEGUROS = {
    "abs": abs, "all": all, "any": any, "bool": bool,
    "dict": dict, "enumerate": enumerate, "filter": filter,
    "float": float, "int": int, "isinstance": isinstance,
    "len": len, "list": list, "map": map, "max": max,
    "min": min, "range": range, "round": round, "set": set,
    "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
    "type": type, "zip": zip,
    "None": None, "True": True, "False": False,
}


def executar_script(
    script: str,
    df_original: pd.DataFrame,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Executa o script num escopo isolado.

    O script recebe `df` (cópia do original) e `pd` (pandas).
    Deve devolver o resultado na variável `df`.

    Returns:
        (DataFrame corrigido, None)   → sucesso
        (None, traceback completo)   → falha
    """
    escopo_local: dict = {"df": df_original.copy(), "pd": pd}
    escopo_global: dict = {"__builtins__": _BUILTINS_SEGUROS, "pd": pd}

    try:
        exec(script, escopo_global, escopo_local)  # noqa: S102

        resultado = escopo_local.get("df")

        if resultado is None:
            return None, "Script executado, mas variável 'df' não foi definida."
        if not isinstance(resultado, pd.DataFrame):
            return None, f"'df' não é um DataFrame (tipo: {type(resultado).__name__})"
        if resultado.empty:
            return None, "DataFrame retornado está vazio."

        logger.info("[SUCCESS] Script executou com sucesso. Linhas: %d", len(resultado))
        return resultado, None

    except SyntaxError as e:
        tb = f"SyntaxError: {e}\n{traceback.format_exc()}"
        logger.error("[ERROR] %s", tb)
        return None, tb
    except Exception:
        tb = traceback.format_exc()
        logger.error("[ERROR] Falha na execução:\n%s", tb)
        return None, tb


def limpar_markdown(script: str) -> str:
    """Remove blocos ```python ... ``` que a IA às vezes inclui."""
    linhas = script.strip().splitlines()
    limpas = []
    for linha in linhas:
        if linha.strip().startswith("```"):
            continue
        limpas.append(linha)
    return "\n".join(limpas).strip()