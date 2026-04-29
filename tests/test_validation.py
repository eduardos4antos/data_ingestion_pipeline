"""
Testes de validacao de arquivos CSV.

Estes testes detectam problemas em arquivos CSV comparando-os com o template esperado.
Execute com: pytest tests/test_validation.py -v

O output dos testes pode ser usado para alimentar uma IA que gera scripts de correcao.
"""

import json
import pytest
from pathlib import Path

from src.validation import (
    detectar_encoding,
    detectar_delimitador,
    carregar_csv,
    validar_colunas_obrigatorias,
    validar_nomes_colunas,
    validar_formato_data,
    validar_formato_valor,
    validar_enum,
    validar_csv_completo,
    gerar_relatorio_divergencias,
)


# =============================================================================
# TESTES DE DETECCAO DE ENCODING
# =============================================================================

class TestDeteccaoEncoding:
    """Detecta o encoding do arquivo CSV."""

    def test_encoding_perfeito_utf8(self, sample_csv_perfeito):
        """perfeito.csv deve estar em UTF-8."""
        encoding = detectar_encoding(sample_csv_perfeito)
        assert encoding.lower().replace("-", "") in ["utf8", "ascii"], \
            f"ERRO: Encoding detectado '{encoding}' - esperado UTF-8"

    def test_encoding_latin1_problema(self, sample_csv_encoding_latin1):
        """encoding_latin1.csv esta em Latin-1 mas deveria ser UTF-8."""
        encoding = detectar_encoding(sample_csv_encoding_latin1)
        # O arquivo DEVERIA estar em UTF-8, mas esta em Latin-1
        # Este teste FALHA para indicar que o arquivo precisa de conversao
        assert encoding.lower().replace("-", "") in ["utf8", "ascii"], \
            f"ERRO DETECTADO: Encoding '{encoding}' - esperado UTF-8. " \
            f"Arquivo contem caracteres especiais em encoding Latin-1/ISO-8859-1. " \
            f"Converter para UTF-8 antes da ingestao."


# =============================================================================
# TESTES DE DETECCAO DE DELIMITADOR
# =============================================================================

class TestDeteccaoDelimitador:
    """Detecta o delimitador usado no arquivo CSV."""

    def test_delimitador_virgula(self, sample_csv_perfeito):
        """perfeito.csv deve usar virgula como delimitador."""
        delimitador = detectar_delimitador(sample_csv_perfeito)
        assert delimitador == ",", \
            f"Delimitador: '{delimitador}'"

    def test_delimitador_ponto_virgula(self, sample_csv_delimitador_pv):
        """delimitador_pv.csv usa ponto-e-virgula."""
        delimitador = detectar_delimitador(sample_csv_delimitador_pv)
        assert delimitador == ",", \
            f"ERRO DETECTADO: Delimitador e '{delimitador}' - esperado ','. Precisa conversao."


# =============================================================================
# TESTES DE COLUNAS OBRIGATORIAS
# =============================================================================

class TestColunasObrigatorias:
    """Verifica se todas as colunas obrigatorias estao presentes."""

    def test_colunas_perfeito(self, sample_csv_perfeito, template_schema):
        """perfeito.csv deve ter todas as colunas obrigatorias."""
        df = carregar_csv(sample_csv_perfeito)
        resultado = validar_colunas_obrigatorias(df, template_schema)
        assert resultado["valido"], \
            f"Colunas presentes: {list(df.columns)}"

    def test_colunas_faltando(self, sample_csv_colunas_faltando, template_schema):
        """colunas_faltando.csv tem colunas ausentes."""
        df = carregar_csv(sample_csv_colunas_faltando)
        resultado = validar_colunas_obrigatorias(df, template_schema)
        assert resultado["valido"], \
            f"ERRO DETECTADO: Colunas obrigatorias faltando: {resultado['colunas_faltando']}. " \
            f"Colunas presentes: {list(df.columns)}"


# =============================================================================
# TESTES DE NOMES DE COLUNAS
# =============================================================================

class TestNomesColunas:
    """Verifica se os nomes das colunas estao corretos."""

    def test_nomes_perfeito(self, sample_csv_perfeito, template_schema):
        """perfeito.csv deve ter nomes de colunas corretos."""
        df = carregar_csv(sample_csv_perfeito)
        resultado = validar_nomes_colunas(df, template_schema)
        assert resultado["valido"], \
            f"Nomes corretos"

    def test_nomes_diferentes(self, sample_csv_nomes_diferentes, template_schema):
        """nomes_diferentes.csv usa aliases ao inves dos nomes padrao."""
        df = carregar_csv(sample_csv_nomes_diferentes)
        resultado = validar_nomes_colunas(df, template_schema)
        assert resultado["valido"], \
            f"ERRO DETECTADO: Colunas com nomes diferentes. " \
            f"Mapeamento necessario: {resultado['mapeamento_sugerido']}. " \
            f"Colunas desconhecidas: {resultado['colunas_desconhecidas']}"


# =============================================================================
# TESTES DE FORMATO DE DATA
# =============================================================================

class TestFormatoData:
    """Verifica se as datas estao no formato correto (YYYY-MM-DD)."""

    def test_data_formato_iso(self, sample_csv_perfeito, template_schema):
        """perfeito.csv deve ter datas em formato ISO."""
        df = carregar_csv(sample_csv_perfeito)
        resultado = validar_formato_data(df, "data_transacao", template_schema)
        assert resultado["valido"], \
            f"Formato: {resultado['formato_detectado']}"

    def test_data_formato_brasileiro(self, sample_csv_formato_data_br, template_schema):
        """formato_data_br.csv tem datas em DD/MM/YYYY."""
        df = carregar_csv(sample_csv_formato_data_br)
        resultado = validar_formato_data(df, "data_transacao", template_schema)
        assert resultado["valido"], \
            f"ERRO DETECTADO: Formato de data incorreto. " \
            f"Detectado: '{resultado['formato_detectado']}' - Esperado: 'YYYY-MM-DD'. " \
            f"Linhas com problema: {resultado['linhas_invalidas'][:5]}..."


# =============================================================================
# TESTES DE FORMATO DE VALOR
# =============================================================================

class TestFormatoValor:
    """Verifica se os valores monetarios estao no formato correto."""

    def test_valor_decimal(self, sample_csv_perfeito, template_schema):
        """perfeito.csv deve ter valores em formato decimal."""
        df = carregar_csv(sample_csv_perfeito)
        resultado = validar_formato_valor(df, "valor", template_schema)
        assert resultado["valido"], \
            f"Formato: {resultado['formato_detectado']}"

    def test_valor_brasileiro(self, sample_csv_formato_valor_br, template_schema):
        """formato_valor_br.csv tem valores em R$ 1.234,56."""
        df = carregar_csv(sample_csv_formato_valor_br)
        resultado = validar_formato_valor(df, "valor", template_schema)
        assert resultado["valido"], \
            f"ERRO DETECTADO: Formato de valor incorreto. " \
            f"Detectado: '{resultado['formato_detectado']}' - Esperado: decimal (1234.56). " \
            f"Exemplo de valores: {df['valor'].head(3).tolist()}"


# =============================================================================
# TESTES DE VALORES ENUM
# =============================================================================

class TestValoresEnum:
    """Verifica se os valores de campos enum sao validos."""

    def test_tipo_transacao_valido(self, sample_csv_perfeito, template_schema):
        """perfeito.csv deve ter tipos de transacao validos."""
        df = carregar_csv(sample_csv_perfeito)
        resultado = validar_enum(df, "tipo", template_schema)
        assert resultado["valido"], \
            f"Tipos encontrados: {df['tipo'].unique().tolist()}"

    def test_categoria_valida(self, sample_csv_perfeito, template_schema):
        """perfeito.csv deve ter categorias validas."""
        df = carregar_csv(sample_csv_perfeito)
        resultado = validar_enum(df, "categoria", template_schema)
        assert resultado["valido"], \
            f"Categorias encontradas: {df['categoria'].unique().tolist()}"

    def test_status_valido(self, sample_csv_perfeito, template_schema):
        """perfeito.csv deve ter status validos."""
        df = carregar_csv(sample_csv_perfeito)
        resultado = validar_enum(df, "status", template_schema)
        assert resultado["valido"], \
            f"Status encontrados: {df['status'].unique().tolist()}"

    def test_enum_nomes_diferentes(self, sample_csv_nomes_diferentes, template_schema):
        """nomes_diferentes.csv tem valores enum em ingles."""
        df = carregar_csv(sample_csv_nomes_diferentes)
        # A coluna se chama 'type' ao inves de 'tipo'
        if "type" in df.columns:
            resultado = validar_enum(df, "type", template_schema)
            # Este teste vai falhar porque 'type' nao esta no template
            # Mas o mapeamento de nomes deve ser feito primeiro
        if "tipo" in df.columns:
            resultado = validar_enum(df, "tipo", template_schema)
            assert resultado["valido"], \
                f"ERRO DETECTADO: Valores enum precisam mapeamento. " \
                f"Valores invalidos: {resultado['valores_invalidos']}. " \
                f"Mapeamento sugerido: {resultado['mapeamento_sugerido']}"


# =============================================================================
# TESTES DE COLUNAS EXTRAS
# =============================================================================

class TestColunasExtras:
    """Verifica se ha colunas extras que nao estao no template."""

    def test_sem_colunas_extras(self, sample_csv_perfeito, template_schema):
        """perfeito.csv nao deve ter colunas extras."""
        df = carregar_csv(sample_csv_perfeito)
        colunas_template = set(template_schema["colunas"].keys())
        colunas_arquivo = set(df.columns)
        extras = colunas_arquivo - colunas_template
        assert len(extras) == 0, \
            f"Sem colunas extras"

    def test_com_colunas_extras(self, sample_csv_colunas_extras, template_schema):
        """colunas_extras.csv tem colunas adicionais."""
        df = carregar_csv(sample_csv_colunas_extras)
        colunas_template = set(template_schema["colunas"].keys())
        colunas_arquivo = set(df.columns)
        extras = colunas_arquivo - colunas_template
        assert len(extras) == 0, \
            f"ERRO DETECTADO: Colunas extras encontradas: {list(extras)}. " \
            f"Essas colunas devem ser removidas antes da ingestao."


# =============================================================================
# TESTES DE VALIDACAO COMPLETA
# =============================================================================

class TestValidacaoCompleta:
    """Executa validacao completa do arquivo."""

    def test_csv_perfeito(self, sample_csv_perfeito, template_schema):
        """perfeito.csv deve passar em todas as validacoes."""
        resultado = validar_csv_completo(sample_csv_perfeito, template_schema)
        assert resultado["valido"], \
            f"CSV valido - pronto para ingestao"

    def test_csv_multiplos_problemas(self, sample_csv_multiplos_problemas, template_schema):
        """multiplos_problemas.csv tem varios erros."""
        resultado = validar_csv_completo(sample_csv_multiplos_problemas, template_schema)
        assert resultado["valido"], \
            f"ERRO DETECTADO: Arquivo com {resultado['total_erros']} problema(s). " \
            f"Detalhes: {json.dumps(resultado['detalhes'], indent=2, ensure_ascii=False)}"


# =============================================================================
# TESTE DE GERACAO DE RELATORIO
# =============================================================================

class TestRelatorio:
    """Gera relatorio de divergencias para alimentar a IA."""

    def test_relatorio_perfeito(self, sample_csv_perfeito, template_schema):
        """Relatorio para CSV perfeito deve indicar sucesso."""
        relatorio = gerar_relatorio_divergencias(sample_csv_perfeito, template_schema)
        assert "Nenhuma divergencia" in relatorio or len(relatorio.strip()) == 0, \
            f"Relatorio:\n{relatorio}"

    def test_relatorio_com_erros(self, sample_csv_multiplos_problemas, template_schema):
        """Relatorio deve detalhar todos os erros encontrados."""
        relatorio = gerar_relatorio_divergencias(sample_csv_multiplos_problemas, template_schema)
        # Este teste sempre "passa" mas imprime o relatorio completo
        print(f"\n{'='*60}")
        print("RELATORIO DE ERROS PARA IA:")
        print('='*60)
        print(relatorio)
        print('='*60)
        assert "Nenhuma divergencia" in relatorio, \
            f"ERROS ENCONTRADOS - Relatorio para IA:\n{relatorio}"
