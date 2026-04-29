"""
Pipeline de Ingestão de CSV com IA — Franq Desafio
Execução: streamlit run app/main.py (da raiz do projeto)
"""

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Garante que src/ e app/ são encontrados
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

# Módulos do projeto
from app.database import inicializar_banco, DB_PATH
from app.cache import (
    gerar_hash_estrutura,
    buscar_script_cache,
    salvar_script_cache,
    registrar_log_ingestao,
    buscar_id_script,
)
from app.executor import executar_script, limpar_markdown
from app.ia_service import gerar_script_com_retry
from app.ingestion import ingesting_dataframe as ingesting_dataframe
from app.fallback import aplicar_fallback_manual, gerar_resumo_fallback

# Validador oficial do desafio
from src.validation import (
    detectar_encoding,
    detectar_delimitador,
    carregar_csv,
    validar_csv_completo,
    gerar_relatorio_divergencias,
)

# ── Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Template ──────────────────────────────────────────────────────────
TEMPLATE_PATH = ROOT / "database" / "template.json"
with open(TEMPLATE_PATH, encoding="utf-8") as f:
    TEMPLATE = json.load(f)

# ── Init banco ────────────────────────────────────────────────────────
inicializar_banco()

# ═════════════════════════════════════════════════════════════════════
# Configuração da Página
# ═════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Pipeline CSV — Franq",
    page_icon="🔄",
    layout="wide",
)

st.title("🔄 Pipeline de Ingestão de CSV com IA")
st.caption("Upload → Validação automática → Correção por IA → Cache → Ingestão no banco")

# ── API Key ───────────────────────────────────────────────────────────
api_key = os.getenv("GEMINI_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Configuração")
    api_key_input = st.text_input(
        "Gemini API Key",
        value=api_key,
        type="password",
        placeholder="AIzaSy...",
    )
    if api_key_input:
        api_key = api_key_input

    st.divider()
    st.subheader("📊 Banco de Dados")
    st.caption(f"`{DB_PATH.name}`")
    if st.button("🔄 Atualizar contagem"):
        st.rerun()

    try:
        from app.database import get_connection
        with get_connection() as conn:
            n = conn.execute("SELECT COUNT(*) FROM transacoes_financeiras").fetchone()[0]
            cs = conn.execute("SELECT COUNT(*) FROM scripts_transformacao").fetchone()[0]
        st.metric("Transações no banco", n)
        st.metric("Scripts em cache", cs)
    except Exception as e:
        st.warning(f"Banco indisponível: {e}")

    if not api_key:
        st.error("⚠️ Configure a API Key para usar a IA")


# ═════════════════════════════════════════════════════════════════════
# 1. Upload
# ═════════════════════════════════════════════════════════════════════

st.header("1️⃣ Upload do CSV")

arquivo = st.file_uploader(
    "Selecione um arquivo CSV",
    type=["csv"],
    help="O sistema detecta encoding, delimitador e problemas automaticamente.",
)

if arquivo is None:
    st.info("👆 Faça o upload de um arquivo CSV para iniciar.")
    st.stop()

conteudo_bytes = arquivo.read()
logger.info("[INFO] Upload recebido: %s (%d bytes)", arquivo.name, len(conteudo_bytes))


# ═════════════════════════════════════════════════════════════════════
# 2. Preview e Estatísticas
# ═════════════════════════════════════════════════════════════════════

st.header("2️⃣ Preview e Estatísticas")

# Salva em arquivo temporário para usar as funções do src/validation.py
# (que recebem filepath, não bytes)
with tempfile.NamedTemporaryFile(
    suffix=".csv", delete=False, mode="wb"
) as tmp:
    tmp.write(conteudo_bytes)
    TMP_CSV = Path(tmp.name)

try:
    encoding = detectar_encoding(TMP_CSV)
    delimitador = detectar_delimitador(TMP_CSV)
    df_original = carregar_csv(TMP_CSV)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Linhas", df_original.shape[0])
    col2.metric("Colunas", df_original.shape[1])
    col3.metric("Encoding", encoding)
    col4.metric("Delimitador", repr(delimitador))

    st.dataframe(df_original.head(10), use_container_width=True)

    with st.expander("ℹ️ Detalhes das colunas"):
        info = pd.DataFrame({
            "Coluna": df_original.columns,
            "Tipo pandas": df_original.dtypes.values,
            "Nulos": df_original.isnull().sum().values,
            "Exemplo": [df_original[c].dropna().iloc[0] if not df_original[c].dropna().empty else "—"
                        for c in df_original.columns],
        })
        st.dataframe(info, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao ler o arquivo: {e}")
    st.stop()


# ═════════════════════════════════════════════════════════════════════
# 3. Validação Automática
# ═════════════════════════════════════════════════════════════════════

st.header("3️⃣ Validação Automática")
logger.info("[INFO] Validação iniciada")

resultado_validacao = validar_csv_completo(TMP_CSV, TEMPLATE)
relatorio = gerar_relatorio_divergencias(TMP_CSV, TEMPLATE)

if resultado_validacao["valido"]:
    st.success("✅ CSV válido! Pronto para ingestão direta.")

else:
    st.error(f"❌ {resultado_validacao['total_erros']} problema(s) detectado(s)")

    # Exibe cada erro de forma visual e clara
    for detalhe in resultado_validacao["detalhes"]:
        tipo = detalhe.get("tipo", "")

        if tipo == "colunas_faltando":
            st.warning(
                f"**Colunas obrigatórias faltando:** `{detalhe['colunas']}`\n\n"
                f"Colunas presentes: `{df_original.columns.tolist()}`"
            )
        elif tipo == "nomes_colunas":
            mapa = detalhe.get("mapeamento", {})
            linhas_mapa = "\n".join(f"- `{k}` → `{v}`" for k, v in mapa.items())
            st.warning(f"**Nomes de colunas incorretos — renomear:**\n{linhas_mapa}")
        elif tipo == "formato_data":
            st.warning(
                f"**Formato de data incorreto:** detectado `{detalhe.get('formato_detectado')}`, "
                f"esperado `YYYY-MM-DD`"
            )
        elif tipo == "formato_valor":
            st.warning(
                f"**Formato de valor incorreto:** detectado `{detalhe.get('formato_detectado')}`, "
                f"esperado decimal (ex: `1234.56`)"
            )
        else:
            st.warning(f"**{tipo}:** {json.dumps(detalhe, ensure_ascii=False)}")

    with st.expander("📋 Relatório completo"):
        st.code(relatorio)


# ═════════════════════════════════════════════════════════════════════
# 4. Execução do Pipeline
# ═════════════════════════════════════════════════════════════════════

st.header("4️⃣ Executar Pipeline")

col_btn, col_info = st.columns([1, 3])

with col_btn:
    executar = st.button(
        "🚀 Processar e Ingerir",
        type="primary",
        disabled=not api_key and not resultado_validacao["valido"],
        use_container_width=True,
    )

with col_info:
    if resultado_validacao["valido"]:
        st.info("CSV já válido — ingestão direta sem necessidade de IA.")
    elif not api_key:
        st.warning("Configure a API Key para corrigir via IA.")

if not executar:
    st.stop()


# ═════════════════════════════════════════════════════════════════════
# Pipeline
# ═════════════════════════════════════════════════════════════════════

metricas = {"ia_calls": 0, "cache_hits": 0}
t_inicio = time.time()
script_usado = None
veio_do_cache = False

progress = st.progress(0)
status_text = st.empty()

def atualizar(pct: int, msg: str):
    progress.progress(pct)
    status_text.markdown(f"⚙️ {msg}")
    logger.info("[INFO] %s", msg)

try:
    # ── Caso 1: CSV já válido ─────────────────────────────────────────
    if resultado_validacao["valido"]:
        atualizar(50, "CSV válido — iniciando ingestão direta...")
        sucesso, erros, msgs_erro = ingesting_dataframe(df_original)
        duracao = time.time() - t_inicio
        registrar_log_ingestao(
            arquivo.name, len(df_original), sucesso, erros,
            usou_ia=False, script_id=None, duracao_segundos=duracao,
        )
        atualizar(100, "Concluído!")
        df_final = df_original
        script_usado = None

    else:
        # ── Caso 2: CSV com erros — busca cache ou chama IA ──────────

        # Extrai os tipos de erro para compor o hash
        tipos_erro = [d.get("tipo", "") for d in resultado_validacao["detalhes"]]
        hash_estrutura = gerar_hash_estrutura(df_original, tipos_erro)

        atualizar(15, f"Buscando script no cache (hash: {hash_estrutura[:12]}…)")
        logger.info("[INFO] Buscando script no cache")

        script_cache = buscar_script_cache(hash_estrutura)

        if script_cache:
            # ── Cache HIT ─────────────────────────────────────────────
            logger.info("[INFO] Cache HIT — reutilizando script")
            metricas["cache_hits"] += 1
            veio_do_cache = True
            atualizar(35, "Script encontrado no cache — executando...")

            df_resultado, erro_exec = executar_script(script_cache, df_original)

            if df_resultado is not None:
                # Revalida o resultado do cache
                with tempfile.NamedTemporaryFile(
                    suffix=".csv", delete=False, mode="w", encoding="utf-8"
                ) as tmp_out:
                    df_resultado.to_csv(tmp_out.name, index=False)
                    tmp_out_path = tmp_out.name

                try:
                    val_cache = validar_csv_completo(tmp_out_path, TEMPLATE)
                finally:
                    os.unlink(tmp_out_path)

                if val_cache["valido"]:
                    script_usado = script_cache
                    df_final = df_resultado
                    atualizar(70, "Script do cache executou com sucesso — ingerindo...")
                else:
                    # Cache inválido — cai para a IA
                    logger.warning("[WARN] Script do cache não passou na revalidação, chamando IA")
                    veio_do_cache = False
                    script_cache = None  # força chamada à IA abaixo
            else:
                logger.warning("[WARN] Script do cache falhou na execução: %s", erro_exec)
                veio_do_cache = False
                script_cache = None

        if not script_cache or not veio_do_cache:
            # ── Cache MISS — chama a IA ou usa fallback ─────────────────
            if not api_key:
                st.error("API Key não configurada. Não é possível chamar a IA.")
                st.stop()

            # Gemini — sem import necessario aqui
            client = None  # Gemini usa api_key direto

            atualizar(30, "Chamando IA para gerar script de correção…")
            logger.info("[INFO] Chamando IA")

            try:
                script_ia, df_final = gerar_script_com_retry(
                    detalhes_validacao=resultado_validacao["detalhes"],
                    df=df_original,
                    template=TEMPLATE,
                    encoding_detectado=encoding,
                    delimitador_detectado=delimitador,
                    client=client,
                    api_key=api_key,
                    metricas=metricas,
                )
                script_usado = script_ia
            except Exception as e:
                # ── FALLBACK MANUAL ─────────────────────────────────────
                erro_str = str(e)
                precisa_fallback = (
                    "RESOURCE_EXHAUSTED" in erro_str or
                    "429" in erro_str or
                    "quota" in erro_str.lower() or
                    "rate limit" in erro_str.lower()
                )

                if precisa_fallback:
                    st.warning("⚠️ **IA indisponível (quota excedida)**")
                    st.info("💡 **Fallback manual disponível** — deseja usar?")

                    col_fb1, col_fb2 = st.columns(2)
                    with col_fb1:
                        usar_fallback = st.checkbox(
                            "Usar correção manual",
                            value=False,
                            help="Aplica correções rigorosas baseadas no template sem usar IA"
                        )
                    with col_fb2:
                        st.caption(
                            "O fallback usa os aliases e mapeamentos do template "
                            "para corrigir nomes de colunas, formatos de data, valores, "
                            "e mapeamentos enum."
                        )

                    if usar_fallback:
                        atualizar(35, "Aplicando fallback manual…")
                        logger.info("[INFO] Usando fallback manual")

                        df_final, correcoes = aplicar_fallback_manual(
                            df_original,
                            resultado_validacao["detalhes"],
                            TEMPLATE,
                        )

                        # Mostra as correções aplicadas
                        st.success("✅ **Correções aplicadas pelo fallback:**")
                        for correcao in correcoes:
                            st.write(f"  • {correcao}")

                        # Revalida o resultado
                        with tempfile.NamedTemporaryFile(
                            suffix=".csv", delete=False, mode="w", encoding="utf-8"
                        ) as tmp_fb:
                            df_final.to_csv(tmp_fb.name, index=False)
                            tmp_fb_path = tmp_fb.name

                        try:
                            val_fb = validar_csv_completo(tmp_fb_path, TEMPLATE)
                        finally:
                            os.unlink(tmp_fb_path)

                        if val_fb["valido"]:
                            st.success("✅ Fallback corrigiu o CSV!")
                            script_usado = "# Fallback manual (sem IA)"
                        else:
                            st.error("❌ Fallback não corrigiu todos os erros")
                            st.write("Erros restantes:")
                            for erro in val_fb["detalhes"]:
                                st.write(f"  - {erro}")
                            # Não tenta mais — mostra os erros restantes
                            script_usado = None
                            df_final = None
                    else:
                        st.error("❌ Pipeline falhou: IA indisponível e fallback não aceito.")
                        st.stop()
                else:
                    # Outro erro — re-lança
                    raise

            # Salva no cache para próxima vez
            atualizar(70, "Salvando script no cache...")
            descricao_cache = f"Arquivo: {arquivo.name}, Erros: {tipos_erro}"

            if not veio_do_cache and script_usado and "fallback" not in script_usado:
                salvar_script_cache(hash_estrutura, script_usado, descricao_cache)
                logger.info("[INFO] script salvo no cache")
            else:
                logger.info("[INFO] script não salvo no cache")


        # ── Ingestão ──────────────────────────────────────────────────
        atualizar(80, "Ingerindo dados no banco SQLite…")
        sucesso, erros, msgs_erro = ingesting_dataframe(df_final)

        duracao = time.time() - t_inicio
        script_id = buscar_id_script(hash_estrutura) if not resultado_validacao["valido"] else None
        registrar_log_ingestao(
            arquivo.name, len(df_final), sucesso, erros,
            usou_ia=not veio_do_cache and not resultado_validacao["valido"],
            script_id=script_id,
            duracao_segundos=duracao,
        )

    atualizar(100, "Pipeline concluído!")


except RuntimeError as e:
    st.error(f"❌ Pipeline falhou:\n\n{e}")
    st.stop()

except Exception as e:
    import traceback
    st.error(f"❌ Erro inesperado: {e}")
    with st.expander("Traceback completo"):
        st.code(traceback.format_exc())
    st.stop()


# ═════════════════════════════════════════════════════════════════════
# 5. Resultado
# ═════════════════════════════════════════════════════════════════════

st.header("5️⃣ Resultado")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Registros inseridos", sucesso)
m2.metric("Erros na ingestão", erros)
m3.metric("Chamadas à IA", metricas["ia_calls"])
m4.metric("Cache hits", metricas["cache_hits"])
m5.metric("Tempo total", f"{time.time() - t_inicio:.1f}s")

if veio_do_cache:
    st.info("⚡ Script **reutilizado do cache** — nenhuma chamada à IA necessária!")

if sucesso > 0:
    st.success(f"✅ {sucesso} registro(s) inserido(s) com sucesso em `transacoes_financeiras`.")

if erros > 0:
    with st.expander(f"⚠️ {erros} erro(s) na ingestão"):
        for msg in msgs_erro:
            st.markdown(f"- {msg}")

# DataFrame corrigido
if df_final is not None:
    st.subheader("📋 DataFrame após correção")
    st.dataframe(df_final, use_container_width=True)

# Script utilizado
if script_usado:
    label = "⚡ Script do cache utilizado" if veio_do_cache else "🤖 Script gerado pela IA"
    with st.expander(label):
        st.code(script_usado, language="python")

# ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Franq Desafio — Pipeline: Upload → Validação (src/validation.py) → Cache → IA → Ingestão (SQLite)")