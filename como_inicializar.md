# Como Inicializar o Projeto — Desafio Franq

## Visão Geral

Este é o projeto **Desafio Franq** — um **pipeline de ingestão de CSV com IA** que:
1. Recebe arquivos CSV de diferentes formatos
2. Valida automaticamente usando funções de `src/validation.py`
3. Usa Google Gemini para gerar scripts de correção quando há erros
4. Salva scripts válidos em cache (SQLite) para reutilização
5. Insere os dados corrigidos no banco de dados

---

## 1. Pré-Requisitos

### 1.1 Python Instalado
- **Versão mínima**: Python 3.10+
- **Versão recomendada**: Python 3.13 (usado neste ambiente)

Verifique sua versão:
```powershell
python --version
```

### 1.2 API Key do Google Gemini
Você precisa de uma API key do Google Gemini:

1. Acesse [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Faça login com sua conta Google
3. Clique em **"Create API Key"**
4. Copie a chave (começa com `AIzaSy...`)

---

## 2. Instalação do Projeto

### 2.1 Clone ou Baixe o Projeto
```powershell
cd desafio-franq
```

### 2.2 Crie o Arquivo de Variáveis de Ambiente

Crie um arquivo chamado `.env` na raiz do projeto (`desafio-franq\.env`):

```env
# API Key do Google Gemini (obrigatória para usar a IA)
GEMINI_API_KEY=sua_chave_aqui
```

**Substitua `sua_chave_aqui`** pela sua API key real do Google Gemini.

### 2.3 Instale as Dependências

Na raiz do projeto, execute:

```powershell
pip install -r requirements.txt
```

Este comando instala:
- `streamlit` — interface web
- `pandas` — manipulação de dados
- `pytest` / `pytest-cov` — testes
- `chardet` — detecção de encoding
- `google-genai` — integração com Gemini
- `python-dotenv` — variáveis de ambiente

---

## 3. Estrutura do Projeto

```
franq_desafio/
├── .env                    # ← VOCÊ CRIA (API Key)
├── requirements.txt        # Dependências Python
├── database/
│   ├── schema.sql          # Schema do banco SQLite
│   ├── template.json      # Template de validação
│   └── pipeline.db        # ← CRIA AUTOMATICAMENTE
├── app/
│   ├── main.py            # Interface Streamlit
│   ├── database.py       # Conexão SQLite
│   ├── cache.py          # Cache de scripts
│   ├── executor.py       # Execução de scripts
│   ├── ia_service.py     # Integração Gemini
│   └── ingestion.py     # Ingestão no banco
├── src/
│   └── validation.py    # Funções de validação
├── sample_data/
│   ├── perfeito.csv     # CSV sem erros
│   └── ...outros CSVs   # CSVs com problemas
└── tests/
    └── test_validation.py
```

---

## 4. Executando o Projeto

### 4.1 Iniciar a Interface Streamlit

Na raiz do projeto (`desafio-franq`):

```powershell
streamlit run app/main.py
```

O navegador abrirá automaticamente em: `http://localhost:8501`

### 4.2 Configurar a API Key na Interface

1. No menu lateral (sidebar), localize o campo **"Gemini API Key"**
2. Cole sua API key
3. A interface está pronta para uso

---

## 5. Como Usar a Interface

### 5.1 Fluxo Completo

```
┌─────────────────────────────────────────────────────────────┐
│ 1. UPLOAD                                                  │
│    → Faça upload de um arquivo CSV                         │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. PREVIEW E ESTATÍSTICAS                                  │
│    → Veja linhas, colunas, encoding, delimitador           │
│    → Sistema detecta automaticamente                       │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. VALIDAÇÃO                                               │
│    → Valida automático com src/validation.py               │
│    → Mostra erros encontrados (se houver)                  │
└─────────────────────────────────────────────────────────────┘
                            ▼
         ┌────────────────────┬────────────────────┐
         ▼                    ▼
    ┌─────────┐         ┌─────────────┐
    │ VÁLIDO  │         │ COM ERROS  │
    └─────────┘         └─────────────┘
         │                    │
         │                    ▼
         │            ┌─────────────────┐
         │            │ BUSCAR SCRIPT   │
         │            │ NO CACHE        │
         │            └─────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐    ┌─────────────────┐
│  INGESTÃO DIRETA│    │ GERAR SCRIPT   │
│  NO BANCO       │    │ VIA IA         │
└─────────────────┘    └─────────────────┘
                            │
                            ▼
                     ┌─────────────────┐
                     │ EXECUTAR SCRIPT │
                     │ NO CSV          │
                     └─────────────────┘
                            │
                            ▼
                     ┌─────────────────┐
                     │ VALIDAR RESULT  │
                     └─────────────────┘
                            │
                    ┌──────┴──────┐
                    ▼             ▼
               PASSOU        FALHOU
                    │             │
                    ▼             ▼
            ┌───────────┐   ┌────────────┐
            │ SALVAR    │   │ REENVIAR   │
            │ SCRIPT    │   │ P/ IA      │
            └───────────┘   └────────────┘
                    │
                    ▼
            ┌─────────────────┐
            │ INGESTÃO NO     │
            │ BANCO           │
            └─────────────────┘
```

### 5.2 Arquivos de Teste Disponíveis

| Arquivo | Problema |
|---------|----------|
| `sample_data/perfeito.csv` | Nenhum — válido para ingestão |
| `sample_data/colunas_extras.csv` | Colunas adicionais não esperadas |
| `sample_data/colunas_faltando.csv` | Colunas obrigatórias ausentes |
| `sample_data/nomes_diferentes.csv` | Nomes em inglês (date, amount, etc) |
| `sample_data/formato_data_br.csv` | Datas em DD/MM/YYYY |
| `sample_data/formato_valor_br.csv` | Valores em R$ 1.234,56 |
| `sample_data/encoding_latin1.csv` | Encoding Latin-1 |
| `sample_data/delimitador_pv.csv` | Separador ponto-e-virgula |
| `sample_data/multiplos_problemas.csv` | Combinação de vários erros |

---

## 6. Executando os Testes

### 6.1 Rodar Todos os Testes

```powershell
pytest tests/test_validation.py -v
```

**O que esperar:**
- Testes que **PASSAM** = CSV está correto
- Testes que **FALHAM** = problemas detectados no CSV

### 6.2 Testes com Cobertura

```powershell
pytest tests/test_validation.py -v --cov=src --cov-report=term-missing
```

---

## 7. Solução de Problemas

### 7.1 "ModuleNotFoundError"

**Problema:** `ModuleNotFoundError: No module named '...'`  
**Solução:** Execute `pip install -r requirements.txt` novamente

### 7.2 "GEMINI_API_KEY não configurada"

**Problema:** Erro sobre API key missing  
**Solução:** 
1. Crie o arquivo `.env` com `GEMINI_API_KEY=sua_chave`
2. Ou cole a chave no campo da interface Streamlit

### 7.3 "Banco de dados não encontrado"

**Problema:** Erro ao acessar SQLite  
**Solução:** O banco é criado automaticamente na primeira execução. Verifique se a pasta `database/` existe e tem permissão de escrita.

### 7.4 Erro de Encoding

**Problema:** Caracteres estranhos no CSV  
**Solução:** O sistema detecta automaticamente encoding (UTF-8, Latin-1, etc). Se ainda houver problemas, verifique o arquivo original.

---

## 8. Variáveis de Ambiente

Crie o arquivo `.env` na raiz do projeto:

| Variável | Descrição | Obrigatório |
|----------|-----------|-------------|
| `GEMINI_API_KEY` | Chave da API Google Gemini | Sim |

Exemplo de `.env`:
```env
GEMINI_API_KEY=AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 9. Resumo de Comandos

```powershell
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Criar arquivo .env com sua API Key
# (editar desafio-franq\.env)

# 3. Iniciar a aplicação
streamlit run app/main.py

# 4. (Opcional) Rodar testes
pytest tests/test_validation.py -v
```

---

## 10. Arquitetura dos Módulos

### `app/main.py`
- Interface Streamlit completa
- Upload, preview, validação, correção, ingestão

### `app/database.py`
- Inicialização do SQLite
- Conexão com `get_connection()`

### `app/cache.py`
- Geração de hash da estrutura do CSV
- Busca/salva scripts em cache
- Registro de logs de ingestão

### `app/executor.py`
- Execução de scripts Python gerados pela IA
- Limpeza de markdown do código

### `app.ia_service.py`
- Integração com Google Gemini
- Geração de prompts com erros encontrados
- Retry automático em caso de falha

### `app/ingestion.py`
- Inserção de DataFrames no banco SQLite
- Validação antes da inserção

### `src/validation.py`
- Funções de validação oficial do desafio
- Detecção de encoding, delimitador
- Validação de colunas, datas, valores, enums

---

## 11. Banco de Dados

### Tabelas Criadas (SQLite)

1. **transacoes_financeiras** — Dados das transações ingeridas
2. **scripts_transformacao** — Scripts de correção em cache
3. **log_ingestao** — Histórico de ingestões

### Localização
- Arquivo: `database/pipeline.db`
- Criado automaticamente na primeira execução

---

## 12. Fluxo da IA

Quando um CSV tem erros:

1. **Coleta erros** → `validar_csv_completo()` retorna lista de problemas
2. **Constrói prompt** → Inclui erros + exemplo de dados + formato esperado
3. **Envia para Gemini** → API call com o prompt
4. **Recebe script** → Código Python que corrige o CSV
5. **Executa script** → `exec()` no DataFrame
6. **Valida resultado** → Roda `validar_csv_completo()` novamente
7. **Se válido → salva em cache** → Para reuse futuro
8. **Ingere no banco** → `INSERT INTO transacoes_financeiras`

---

## Pronto! 🚀

Com esses passos, o projeto estará funcionando:
1. ✅ Python instalado
2. ✅ Dependências instaladas (`pip install -r requirements.txt`)
3. ✅ Arquivo `.env` criado com `GEMINI_API_KEY`
4. ✅ Execute `streamlit run app/main.py`
5. ✅ Abra o navegador em `http://localhost:8501`
6. ✅ Faça upload de um CSV e siga o fluxo!