# Desafio Tecnico: Pipeline de Ingestao CSV com IA

## Contexto

Voce foi contratado para desenvolver uma solucao de automacao de ingestao de dados financeiros. A empresa recebe arquivos CSV de diferentes fontes (bancos, sistemas legados, parceiros) e precisa inseri-los em um banco de dados padronizado.

O problema: cada fonte envia os dados em formatos ligeiramente diferentes:
- Nomes de colunas variam (ex: `data` vs `data_transacao`)
- Formatos de data inconsistentes (DD/MM/YYYY vs YYYY-MM-DD)
- Valores monetarios em diferentes formatos (R$ 1.234,56 vs 1234.56)
- Encodings diferentes (UTF-8 vs Latin-1)
- Delimitadores variados (virgula vs ponto-e-virgula)

**Sua missao**: Criar um sistema inteligente que use IA para gerar scripts de correcao, e aprenda com essas correcoes para nao precisar da IA novamente para o mesmo tipo de arquivo.

---

## O Que Ja Esta Pronto

Fornecemos **funcoes de validacao** em `src/validation.py` para detectar problemas:

```python
from src.validation import (
    detectar_encoding,           # Detecta encoding do arquivo
    detectar_delimitador,        # Detecta delimitador (, ou ;)
    carregar_csv,                # Carrega CSV com deteccao automatica
    validar_colunas_obrigatorias,# Verifica colunas obrigatorias
    validar_nomes_colunas,       # Verifica nomes e sugere mapeamentos
    validar_formato_data,        # Verifica formato de datas
    validar_formato_valor,       # Verifica formato de valores
    validar_enum,                # Verifica valores de campos enum
    validar_csv_completo,        # Executa todas as validacoes
    gerar_relatorio_divergencias,# Gera relatorio texto dos problemas
)
```

### Exemplo de Uso

```python
import json
from src.validation import validar_csv_completo

# Carregar template
with open("database/template.json") as f:
    template = json.load(f)

# Validar um arquivo
resultado = validar_csv_completo("sample_data/multiplos_problemas.csv", template)

if resultado["valido"]:
    print("CSV pronto para ingestao!")
else:
    print(f"Encontrados {resultado['total_erros']} problema(s):")
    for erro in resultado["detalhes"]:
        print(f"  - {erro}")
```

### Executando os Testes

```bash
pip install -r requirements.txt
pytest tests/test_validation.py -v

# Testes que FALHAM = problemas detectados no CSV
# A mensagem de erro descreve o problema encontrado
```

---

## Sua Tarefa

Desenvolver uma aplicacao **Streamlit** que implemente o pipeline completo:

### 1. Interface de Upload
- Receba um arquivo CSV via upload
- Mostre preview dos dados
- Exiba estatisticas (linhas, colunas, encoding, delimitador, se é válido ou inválido e o porquê)

### 2. Validacao Automatica
- Use as funcoes de `src/validation.py` para detectar problemas
- Mostre relatorio visual dos erros encontrados
- Se nao houver erros, permita ingestao direta

### 3. Geracao de Script via IA
- Construa um prompt descrevendo os problemas encontrados
- Envie para uma IA (OpenAI, Anthropic, Gemini, ou outra)
- Receba um script Python que corrige o CSV
- Mostre o script gerado para o usuario

### 4. Validacao do Script Gerado
- Execute o script contra o CSV
- Valide se o CSV corrigido passa em `validar_csv_completo()`
- Se falhar, reenvie para a IA com os erros

### 5. Persistencia de Scripts
- Salve scripts validados no banco SQLite (veja `database/schema.sql`)
- Crie uma estrategia para identificar CSVs "similares" (ex: hash das colunas e erros detectados)
- Na proxima vez que um CSV similar for enviado, use o script salvo

### 6. Ingestao
- Insira os dados corrigidos na tabela `transacoes_financeiras`
- Mostre relatorio de sucesso/erros

---

## Fluxo Esperado

```
     UPLOAD CSV
          │
          ▼
   ┌──────────────┐
   │   VALIDAR    │  ← usar validar_csv_completo()
   └──────────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
 VALIDO     COM ERROS
    │           │
    │           ▼
    │    ┌─────────────┐
    │    │   BUSCAR    │  ← script salvo no banco?
    │    │   SCRIPT    │
    │    └─────────────┘
    │           │
    │     ┌─────┴─────┐
    │     ▼           ▼
    │  EXISTE     NAO EXISTE
    │     │           │
    │     │           ▼
    │     │    ┌─────────────┐
    │     │    │  ENVIAR P/  │  ← construir prompt com erros
    │     │    │     IA      │
    │     │    └─────────────┘
    │     │           │
    │     │           ▼
    │     │    ┌─────────────┐
    │     │    │   RECEBER   │
    │     │    │   SCRIPT    │
    │     │    └─────────────┘
    │     │           │
    │     ▼           ▼
    │    ┌─────────────────┐
    │    │ EXECUTAR SCRIPT │
    │    └─────────────────┘
    │           │
    │           ▼
    │    ┌─────────────────┐
    │    │ VALIDAR RESULT. │  ← validar_csv_completo() de novo
    │    └─────────────────┘
    │           │
    │     ┌─────┴─────┐
    │     ▼           ▼
    │  PASSOU      FALHOU ──→ reenviar p/ IA
    │     │
    │     ▼
    │  ┌─────────────┐
    │  │   SALVAR    │
    │  │   SCRIPT    │
    │  └─────────────┘
    │     │
    ▼     ▼
   ┌─────────────────┐
   │    INGERIR      │
   │    NO BANCO     │
   └─────────────────┘
```

---

## Estrutura do Projeto

```
desafio-csv-validator/
├── README.md                    # Este arquivo
├── requirements.txt             # Dependencias
├── database/
│   ├── schema.sql              # Schema SQLite (tabelas e indices)
│   └── template.json           # Template de validacao (NAO modificar)
├── src/
│   └── validation.py           # Funcoes de validacao (usar estas!)
├── tests/
│   ├── conftest.py             # Fixtures do pytest
│   └── test_validation.py      # Testes que detectam erros nos CSVs
├── sample_data/
│   ├── perfeito.csv            # CSV valido (sem erros)
│   ├── colunas_extras.csv      # Colunas adicionais nao esperadas
│   ├── colunas_faltando.csv    # Colunas obrigatorias ausentes
│   ├── nomes_diferentes.csv    # Nomes em ingles (date, amount, etc)
│   ├── formato_data_br.csv     # Datas em DD/MM/YYYY
│   ├── formato_valor_br.csv    # Valores em R$ 1.234,56
│   ├── encoding_latin1.csv     # Encoding Latin-1
│   ├── delimitador_pv.csv      # Separador ponto-e-virgula
│   └── multiplos_problemas.csv # Combinacao de varios erros
└── app/                         # <<< SUA IMPLEMENTACAO AQUI
```

---

## Funcoes de Validacao Disponiveis

| Funcao | Retorno | Descricao |
|--------|---------|-----------|
| `detectar_encoding(filepath)` | `str` | Encoding detectado (utf-8, latin-1, etc) |
| `detectar_delimitador(filepath)` | `str` | Delimitador detectado (, ou ;) |
| `carregar_csv(filepath)` | `DataFrame` | Carrega com deteccao automatica |
| `validar_colunas_obrigatorias(df, template)` | `dict` | `{valido, colunas_faltando}` |
| `validar_nomes_colunas(df, template)` | `dict` | `{valido, mapeamento_sugerido, colunas_desconhecidas}` |
| `validar_formato_data(df, coluna, template)` | `dict` | `{valido, formato_detectado, linhas_invalidas}` |
| `validar_formato_valor(df, coluna, template)` | `dict` | `{valido, formato_detectado, linhas_invalidas}` |
| `validar_enum(df, coluna, template)` | `dict` | `{valido, valores_invalidos, mapeamento_sugerido}` |
| `validar_csv_completo(filepath, template)` | `dict` | `{valido, total_erros, detalhes}` |
| `gerar_relatorio_divergencias(filepath, template)` | `str` | Relatorio texto formatado |

---

## Template de Validacao

O arquivo `database/template.json` define o formato esperado:

- **Colunas obrigatorias**: `id_transacao`, `data_transacao`, `valor`, `tipo`, `categoria`, `conta_origem`, `status`
- **Formato de data**: `YYYY-MM-DD`
- **Formato de valor**: Decimal (ex: `1234.56`)
- **Valores de tipo**: `CREDITO`, `DEBITO`
- **Valores de categoria**: `SALARIO`, `ALIMENTACAO`, `TRANSPORTE`, etc.
- **Valores de status**: `PENDENTE`, `CONFIRMADO`, `CANCELADO`

O template tambem inclui **aliases** (nomes alternativos aceitos) e **mapeamentos** (conversoes automaticas). Consulte o arquivo para detalhes.

---

## Criterios de Avaliacao

| Criterio | Peso | Descricao |
|----------|------|-----------|
| Funcionalidade | 30% | Pipeline completo funcionando |
| Integracao IA | 25% | Uso efetivo de IA para gerar scripts |
| Reutilizacao | 20% | Sistema de cache de scripts funcionando |
| Interface | 15% | UX clara e informativa |
| Codigo | 10% | Organizacao e boas praticas |

---

## Bonus (diferenciais)

- [ ] Metricas de uso (quantas vezes IA foi chamada vs script reutilizado)
- [ ] Feedback loop: melhorar prompt quando IA falha
- [ ] Suporte a multiplos arquivos em lote
- [ ] Logs detalhados das operacoes

---

## Dicas

1. **Comece simples**: Faca funcionar com `perfeito.csv` primeiro (sem erros)
2. **Leia os testes**: `test_validation.py` mostra exatamente o que e detectado
3. **Consulte o template**: `database/template.json` tem aliases e mapeamentos uteis
4. **Prompt engineering**: Inclua no prompt para a IA:
   - Os erros encontrados (de `validar_csv_completo`)
   - Exemplos de dados do arquivo (primeiras linhas)
   - O formato esperado (do template)
   - Instrucoes claras do que o script deve fazer
5. **Trate erros da IA**: Scripts gerados podem ter bugs - valide sempre

---

## Entrega

1. Implemente sua solucao na pasta `app/`
2. Inclua instrucoes de como executar
3. Envie o link do repositorio ou arquivo zip

**Prazo**: 1 semana

---

Boa sorte!
