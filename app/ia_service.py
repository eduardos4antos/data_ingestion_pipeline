"""
Serviço de IA — geração de scripts de correção via Google Gemini.
"""

import json
import logging
import os
import tempfile
import traceback as tb_mod

import pandas as pd

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

SYSTEM_PROMPT = """Você é um engenheiro de dados sênior especializado em transformação de CSVs com pandas.

REGRAS ABSOLUTAS — nunca viole nenhuma delas:
1. O DataFrame de entrada já está disponível como variável `df`
2. O pandas já está disponível como `pd` — NÃO importe nada
3. Sobrescreva `df` com o resultado final (ex: `df = df.rename(...)`)
4. NUNCA use print(), open(), import, ou caminhos de arquivo
5. O código será executado com exec() — deve ser autocontido
6. Responda APENAS com código Python puro, sem markdown, sem explicações
"""


def _formatar_erros(detalhes: list[dict]) -> str:
    linhas = []
    for d in detalhes:
        tipo = d.get("tipo", "desconhecido")
        if tipo == "colunas_faltando":
            linhas.append(
                f"- COLUNAS OBRIGATÓRIAS FALTANDO: {d['colunas']}\n"
                f"  -> Estas colunas são obrigatórias mas não existem no arquivo."
            )
        elif tipo == "nomes_colunas":
            mapa = d.get("mapeamento", {})
            linhas.append(
                f"- NOMES DE COLUNAS INCORRETOS. Renomear:\n"
                + "\n".join(f"    '{k}' -> '{v}'" for k, v in mapa.items())
            )
        elif tipo == "formato_data":
            linhas.append(
                f"- FORMATO DE DATA ERRADO: detectado '{d.get('formato_detectado')}', "
                f"esperado 'YYYY-MM-DD'.\n"
                f"  -> Converter com pd.to_datetime e strftime('%Y-%m-%d')"
            )
        elif tipo == "formato_valor":
            linhas.append(
                f"- FORMATO DE VALOR ERRADO: detectado '{d.get('formato_detectado')}'.\n"
                f"  -> Remover R$, pontos de milhar, trocar virgula por ponto, converter para float"
            )
        else:
            linhas.append(f"- {tipo}: {json.dumps(d, ensure_ascii=False)}")
    return "\n".join(linhas)


def montar_prompt_inicial(detalhes_validacao, df, template, encoding_detectado, delimitador_detectado):
    erros_texto = _formatar_erros(detalhes_validacao)
    amostra = df.head(5).to_string(index=False)
    colunas_atuais = df.columns.tolist()
    colunas_template = {
        nome: {
            "obrigatorio": cfg.get("obrigatorio"),
            "tipo": cfg.get("tipo"),
            "aliases": cfg.get("aliases", []),
            "validacao": cfg.get("validacao", {}),
        }
        for nome, cfg in template["colunas"].items()
    }
    return f"""{SYSTEM_PROMPT}

Corrija o DataFrame `df` para que passe na validacao do template abaixo.

CONTEXTO DO ARQUIVO:
- Encoding detectado: {encoding_detectado}
- Delimitador detectado: {repr(delimitador_detectado)}
- Colunas atuais: {colunas_atuais}

ERROS DETECTADOS:
{erros_texto}

AMOSTRA DAS PRIMEIRAS LINHAS:
{amostra}

TEMPLATE ESPERADO:
{json.dumps(colunas_template, ensure_ascii=False, indent=2)}

INSTRUCOES:
- Renomear colunas usando os aliases quando necessario
- Remover colunas extras que nao existem no template
- Datas: converter para YYYY-MM-DD
- Valores: remover R$, pontos de milhar, trocar virgula por ponto, converter para float
- Enums: aplicar mapeamentos do template (ex: 'C' -> 'CREDITO')

Escreva apenas o codigo Python. Sem markdown.
"""


def montar_prompt_retry(erro_traceback, script_anterior, tentativa):
    return f"""{SYSTEM_PROMPT}

O script falhou (tentativa {tentativa}/{MAX_RETRIES}).

ERRO:
{erro_traceback}

SCRIPT QUE FALHOU:
{script_anterior}

Corrija o problema. `df` e `pd` ja estao disponiveis. NAO use import.
Responda apenas com o codigo Python corrigido.
"""


def chamar_gemini(prompt: str, api_key: str) -> str:
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text or ""


def gerar_script_com_retry(
    detalhes_validacao: list[dict],
    df: pd.DataFrame,
    template: dict,
    encoding_detectado: str,
    delimitador_detectado: str,
    client,
    metricas: dict,
    api_key: str = "",
) -> tuple:
    from .executor import executar_script, limpar_markdown
    import sys
    from pathlib import Path as _Path

    root = _Path(__file__).parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from src.validation import validar_csv_completo

    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada.")

    script_atual = ""
    ultimo_erro = ""

    for tentativa in range(1, MAX_RETRIES + 1):
        logger.info("[INFO] Chamando Gemini — tentativa %d/%d", tentativa, MAX_RETRIES)
        metricas["ia_calls"] += 1

        if tentativa == 1:
            prompt = montar_prompt_inicial(
                detalhes_validacao, df, template,
                encoding_detectado, delimitador_detectado,
            )
        else:
            prompt = montar_prompt_retry(ultimo_erro, script_atual, tentativa)

        try:
            resposta_bruta = chamar_gemini(prompt, api_key)
            script_atual = limpar_markdown(resposta_bruta)
            logger.info("[INFO] Script recebido (%d chars). Executando...", len(script_atual))

            df_resultado, erro_exec = executar_script(script_atual, df)

            if df_resultado is None:
                ultimo_erro = erro_exec or "Erro desconhecido"
                logger.warning("[WARN] Execucao falhou na tentativa %d", tentativa)
                continue

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, encoding="utf-8"
            ) as tmp:
                df_resultado.to_csv(tmp.name, index=False)
                tmp_path = tmp.name

            try:
                validacao = validar_csv_completo(tmp_path, template)
            finally:
                os.unlink(tmp_path)

            if validacao["valido"]:
                logger.info("[SUCCESS] Script validado na tentativa %d", tentativa)
                return script_atual, df_resultado

            ultimo_erro = (
                f"Script executou mas ainda falha na validacao.\n"
                f"Erros: {json.dumps(validacao['detalhes'], ensure_ascii=False, indent=2)}"
            )
            logger.warning("[WARN] Validacao falhou na tentativa %d", tentativa)

        except Exception as e:
            ultimo_erro = f"Erro ao chamar Gemini: {e}\n{tb_mod.format_exc()}"
            logger.error("[ERROR] %s", ultimo_erro)

    raise RuntimeError(
        f"IA nao conseguiu gerar script valido apos {MAX_RETRIES} tentativas.\n"
        f"Ultimo erro:\n{ultimo_erro}"
    )