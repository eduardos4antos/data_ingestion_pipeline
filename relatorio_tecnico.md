# 🔀 O Relatório Que Ninguém Pediu Mas Todos Precisam

## (Ou: Como Eu Construí Um Pipeline de CSV e Por Quê)

---

> *"Não legga este arquivo como documentação. Leia como uma história de código."*
> — Autor, depois de perceber que ninguém lê READMEs tradicionais

---

## 🚀 TL;DR (Para Quem Não Tem Tempo)

```
┌─────────────────────────────────────────────────────────────────┐
│  PROBLEMA: CSVs de 50 fontes diferentes = 50 formatos distintos│
│  SOLUÇÃO:  Pipeline que:                                        │
│    1. Detecta automaticamente encoding + delimitador           │
│    2. Valida contra template JSON                              │
│    3. Se erro → chama IA (Gemini) para gerar script           │
│    4. Salva script em cache (hash SHA-256)                    │
│    5. Insere no SQLite                                         │
│  STACK: Streamlit + SQLite + Google Gemini + pandas            │
└─────────────────────────────────────────────────────────────────┘
```

**Tempo de implementação**: ~2 dias  
**Linhas de código**: ~800  
**Café consumido**: ☕☕☕☕☕☕ (6 xícaras)

---

## 2. Decisões de Arquitetura

### 2.1 Stack Tecnológico

| Componente | Decisão | Justificativa |
|------------|---------|----------------|
| **Interface** | Streamlit | Requisito do desafio. Permite criar UI interativa rapidamente com suporte a upload, preview e visualização de dados. |
| **Banco de Dados** | SQLite |轻量, não requer servidor separado, schema definido no desafio (`schema.sql`). Ideal para protótipos e aplicações desktop. |
| **IA** | Google Gemini | Requisito do desafio. API REST simples, bom custo-benefício, suporte nativo a geração de código. |
| **Validação** | Módulo customizado `src/validation.py` | Fornecido pelo desafio como base. Modular e testável. |

### 2.2 Estrutura de Módulos

```
app/
├── main.py        # Interface Streamlit (orquestrador)
├── database.py    # Conexão SQLite
├── cache.py       # Lógica de cache de scripts
├── executor.py   # Execução segura de scripts
├── ia_service.py # Integração com Gemini
└── ingestion.py  # Inserção no banco
```

**Justificativa**: Separação de responsabilidades clara. Cada módulo tem uma única responsabilidade (SRP), facilitando manutenção e testes. O `main.py` atua como orquestrador, coordenando os demais módulos.

---

## 3. Decisões de Implementação

### 3.1 Carregamento de CSV

**Decisão**: Utilizar funções de `src/validation.py` (`detectar_encoding`, `detectar_delimitador`, `carregar_csv`) em vez de `pd.read_csv()` direto.

**Justificativa**:
- O módulo de validação já detecta automaticamente encoding (UTF-8, Latin-1, etc.) e delimitador (vírgula, ponto-e-virgula).
- Isso elimina a necessidade de especificar parâmetros manualmente para cada arquivo.
- Garante consistência entre a validação e o carregamento.

### 3.2 Arquivo Temporário para Upload

**Decisão**: Salvar o arquivo uploadado em arquivo temporário antes de processar.

```python
with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
    tmp.write(conteudo_bytes)
    TMP_CSV = Path(tmp.name)
```

**Justificativa**:
- As funções de validação em `src/validation.py` recebem `filepath`, não bytes.
- `tempfile.NamedTemporaryFile` garante que o arquivo seja limpo automaticamente após uso.
- `delete=False` permite que o arquivo persista durante o processamento, mas seja removido ao final.

### 3.3 Estratégia de Cache

**Decisão**: Usar hash SHA-256 baseado em colunas + tipos de erro.

```python
payload = {
    "colunas": sorted(df.columns.tolist()),
    "erros": sorted(set(tipos_erro)),
}
hash = sha256(json.dumps(payload, sort_keys=True))
```

**Justificativa**:
- **Por colunas apenas?** Não é suficiente. Um CSV com colunas "date,amount" mas formato de data errado precisa de script diferente de um com formato correto.
- **Por conteúdo?** Não é estável. O mesmo arquivo com dados diferentes geraria hashes diferentes.
- **Por colunas + tipos de erro?** Ideal. Garante que CSVs com mesma estrutura E mesmos problemas reutilizem o mesmo script.
- `sorted()` garante ordem consistente independenteda ordem original.

### 3.4 Execução de Scripts via `exec()`

**Decisão**: Usar `exec()` em vez de `subprocess` ou arquivo temporário.

```python
escopo_local = {"df": df_original.copy(), "pd": pd}
escopo_global = {"__builtins__": _BUILTINS_SEGUROS, "pd": pd}
exec(script, escopo_global, escopo_local)
```

**Justificativa**:
- **Por que não subprocess?** O script precisa manipular o DataFrame em memória. Com subprocess, seria necessário serializar o DataFrame para arquivo, ler de volta — lento e complexo.
- **Por que não arquivo temporário?** Executar scripts de arquivos temporários adiciona complexidade de I/O e segurança (arquivos no disco são mais vulneráveis).
- **Por que exec() é seguro aqui?** O escopo global é restrito a builtins essenciais (`abs`, `len`, `float`, etc.). Acesso a `os`, `sys`, `open`, `__import__` é bloqueado.

### 3.5 Whitelist de Builtins

**Decisão**: Substituir `__builtins__` por whitelist explícita.

```python
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
```

**Justificativa**:
- Python permite acesso a funções perigosas via `__builtins__` padrão.
- Whitelist explícita garante que apenas funções seguras de manipulação de dados estén disponíveis.
- Funções de I/O (`open`), sistema (`os`, `sys`), e reflexão (`__import__`) são bloqueadas.

### 3.6 Retry na Chamada à IA

**Decisão**: Implementar retry automático com até 3 tentativas.

```python
MAX_RETRIES = 3

for tentativa in range(MAX_RETRIES):
    try:
        return gerar_script(...)
    except Exception as e:
        if tentativa == MAX_RETRIES - 1:
            raise
```

**Justificativa**:
- APIs de IA podem falhar por timeout, rate limiting, ou erros temporários.
- 3 tentativas é um equilíbrio entre resiliência e latência.
- Cada tentativa pode gerar um script diferente, aumentando chances de sucesso.

### 3.7 Prompt Engineering

**Decisão**: Incluir no prompt:
- Erros detectados (detalhados por tipo)
- Amostra dos dados (primeiras 5 linhas)
- Template de validação completo
- Regras claras de output

**Justificativa**:
- A IA precisa saber **o que** está errado para gerar o script correto.
- A amostra permite que a IA entenda o formato real dos dados.
- O template define o formato esperado (aliases, mapeamentos, formatos aceitos).
- Regras claras ("responda APENAS com código Python puro") reduzem markdown desnecessário.

### 3.8 Ingestão Linha a Linha

**Decisão**: Inserir registros um a um em vez de bulk insert.

```python
for idx, row in df_para_inserir.iterrows():
    valores = tuple(row[c] for c in cols_disponiveis)
    try:
        conn.execute(sql, valores)
        sucesso += 1
    except Exception as e:
        erros += 1
        mensagens_erro.append(f"Linha {idx}: {e}")
```

**Justificativa**:
- `INSERT OR IGNORE` com bulk insert Would abort toda a transação se uma linha falhar.
- Inserção linha a linha permite capturar erros individuais e continuar.
- `id_transacao` é PRIMARY KEY, então duplicatas são ignoradas automaticamente.
- Fornece feedback detalhado ao usuário sobre quais linhas falharam.

### 3.9 Variáveis de Ambiente

**Decisão**: Usar `.env` com `python-dotenv` para armazenar API key.

```python
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
api_key = os.getenv("GEMINI_API_KEY", "")
```

**Justificativa**:
- API keys não devem ser commitadas no Git.
- `.env` é padrão业界 para configuração local.
- `load_dotenv()` carrega automaticamente ao iniciar a aplicação.
- Permite que diferentes ambientes (dev, prod) usem diferentes chaves.

### 3.10 Interface Streamlit com Sidebar

**Decisão**: Exibir configuração (API key, métricas) na sidebar.

```python
with st.sidebar:
    st.header("⚙️ Configuração")
    api_key_input = st.text_input("Gemini API Key", ...)
    st.metric("Transações no banco", n)
    st.metric("Scripts em cache", cs)
```

**Justificativa**:
- Mantém a área principal focada no fluxo de upload/validação/ingestão.
- API key é configuração, não dado — sidebar é o lugar certo.
- Métricas do banco são informativas mas não essenciais ao fluxo principal.

---

## 4. Decisões de Dados

### 4.1 Schema do Banco

**Decisão**: Usar exatamente o schema definido em `database/schema.sql`.

**Justificativa**:
- O schema foi fornecido como parte do desafio.
- Alterações poderiam quebrar a interface com o sistema externo.
- As restrições CHECK (tipos, categorias, status) garantem integridade.

### 4.2 Colunas da Tabela

**Decisão**: Mapear colunas do DataFrame para colunas da tabela.

```python
COLUNAS_TABELA = [
    "id_transacao", "data_transacao", "valor", "tipo",
    "categoria", "descricao", "conta_origem", "conta_destino", "status",
]
```

**Justificativa**:
- O CSV pode ter colunas extras (não presentes na tabela).
- O sistema deve ignorar colunas desconhecidas e inserir apenas as relevantes.
- `cols_disponiveis = [c for c in COLUNAS_TABELA if c in df.columns]` filtra automaticamente.

---

## 5. Decisões de Logging

### 5.1 Nível de Log

**Decisão**: Usar `logging.INFO` com formato simples.

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
```

**Justificativa**:
- `DEBUG` seria muito verboso para uma aplicação Streamlit.
- `ERROR` seria insuficiente para debugging.
- Formato simples (hora + nível + mensagem) é fácil de ler.

### 5.2 Mensagens de Log

**Decisão**: Incluir prefixos `[INFO]`, `[ERROR]` e contexto (hash, nome do arquivo).

**Justificativa**:
- Prefixos facilitam filtragem visual.
- Contexto (hash parcial, nome do arquivo) ajuda a rastrear operações.
- Exemplo: `[INFO] Cache HIT — hash: a1b2c3d4e5f6`

---

## 6. Decisões de Tratamento de Erros

### 6.1 Try-Except Generalizado

**Decisão**: Wrap cada operação principal em try-except com mensagem clara.

```python
try:
    resultado = validar_csv_completo(TMP_CSV, TEMPLATE)
except Exception as e:
    st.error(f"Erro ao validar: {e}")
    st.stop()
```

**Justificativa**:
- Streamlit para execution se exceção não tratada.
- Mensagens claras orientam o usuário sobre o problema.
- `st.stop()` evita que o erro se propague para renderização.

### 6.2 Validação Pós-Script

**Decisão**: Sempre validar o CSV corrigido antes de ingerir.

```python
resultado = validar_csv_completo(csv_corrigido, TEMPLATE)
if not resultado["valido"]:
    st.error("Script gerado não corrigiu todos os erros")
    # Retry com feedback
```

**Justificativa**:
- A IA pode gerar scripts incompletos ou incorretos.
- Não validar resultaria em dados inválidos no banco.
- O loop de retry permite corrigir o script automaticamente.

---

## 7. Decisões de Performance

### 7.1 Cópia do DataFrame

**Decisão**: Sempre operar sobre cópia, não sobre o original.

```python
df_original = carregar_csv(TMP_CSV)
df_corrigido = df_original.copy()
# ou
escopo_local = {"df": df_original.copy(), "pd": pd}
```

**Justificativa**:
- Evita estado compartilhado entre tentativas.
- Permite retry sem precisar recarregar o arquivo.
- Isolamento facilita debugging.

### 7.2 Conexão SQLite com Context Manager

**Decisão**: Usar `with get_connection() as conn:`.

```python
with get_connection(db_path) as conn:
    conn.execute(sql, valores)
# Conexão fecha automaticamente
```

**Justificativa**:
- Garante que conexões sejam fechadas.
- Evita vazamento de conexões (problema comum com SQLite).
- Código mais limpo (não precisa de `conn.close()`).

---

## 8. Decisões de UX

### 8.1 Preview dos Dados

**Decisão**: Exibir as primeiras linhas do CSV uploadado.

```python
st.dataframe(df_original.head(10), use_container_width=True)
```

**Justificativa**:
- Permite que o usuário verifique se o arquivo foi carregado corretamente.
- Dados visualmente são mais fáceis de validar que texto puro.
- `head(10)` é suficiente sem sobrecarregar a interface.

### 8.2 Métricas na Interface

**Decisão**: Mostrar linhas, colunas, encoding, delimitador como métricas.

```python
col1.metric("Linhas", df_original.shape[0])
col2.metric("Colunas", df_original.shape[1])
col3.metric("Encoding", encoding)
col4.metric("Delimitador", delimitador)
```

**Justificativa**:
- Informação instantânea sobre o arquivo.
- Ajuda a diagnosticar problemas (ex: encoding errado = delimitador mal detectado).
- Layout em colunas é visualmente organizado.

### 8.3 Feedback Visual

**Decisão**: Usar emojis e cores para status.

- ✅ Válido: `st.success()`
- ⚠️ Erros: `st.warning()`
- ❌ Falha: `st.error()`
- 🔄 Processando: `st.spinner()`

**Justificativa**:
- Emojis são universais e rápidos de reconhecer.
- Cores (verde, amarelo, vermelho) seguem convenções de UI.
- Spinner indica que algo está acontecendo (importante para operações lentas).

---

## 9. Decisões de Segurança

### 9.1 API Key no Sidebar

**Decisão**: Campo de senha com `type="password"`.

```python
api_key_input = st.text_input(
    "Gemini API Key",
    value=api_key,
    type="password",  # Não mostra o valor
    placeholder="AIzaSy...",
)
```

**Justificativa**:
- API keys são credenciais sensíveis.
- Mesmo que seja na máquina local, é boa prática não exibir em texto claro.
- `type="password"` mascara o valor digitado.

### 9.2 Arquivo .gitignore

**Decisão**: Ignorar `.env` e `database/pipeline.db`.

```
# .gitignore
.env
database/pipeline.db
__pycache__/
*.pyc
```

**Justificativa**:
- `.env` contém credenciais — nunca commitar.
- `pipeline.db` contém dados de desenvolvimento — não relevante para produção.
- `__pycache__` e `.pyc` são artefatos de build.

---

## 10. Decisões de Testes

### 10.1 Testes Existentes

**Decisão**: Manter testes em `tests/test_validation.py` fornecidos pelo desafio.

**Justificativa**:
- O desafio já fornece testes que validam a função `validar_csv_completo()`.
- Testes que **falam** indicam problemas detectados nos CSVs de sample.
- Testes que **passam** indicam que o CSV está válido.

### 10.2 Execução de Testes

**Decisão**: Documentar comando `pytest tests/test_validation.py -v`.

**Justificativa**:
- `-v` (verbose) mostra qual teste passou/falhou.
- Ajuda o desenvolvedor a entender o que está funcionando ou não.
- Cobertura opcional (`--cov`) para verificar quanto do código é testado.

---

## 11. Resumo das Decisões

| Categoria | Decisão Principal | Benefício |
|-----------|-------------------|-----------|
| **Arquitetura** | Módulos separados por responsabilidade | Manutenção, testabilidade |
| **Validação** | Usar `src/validation.py` | Consistência, detecção automática |
| **Cache** | Hash SHA-256 (colunas + erros) | Reutilização precisa |
| **Execução** | `exec()` com whitelist | Segurança + simplicidade |
| **IA** | Google Gemini + retry | Resiliência a falhas |
| **Ingestão** | Linha a linha com error tracking | Feedback detalhado |
| **Banco** | SQLite com schema fornecido | Conformidade com desafio |
| **UI** | Streamlit com sidebar | Experiência intuitiva |
| **Segurança** | .env + whitelist de builtins | Proteção de credenciais e código |

---

## 12. Possíveis Melhorias Futuras

1. **Metricas de uso**: Quantas vezes a IA foi chamada vs scripts reutilizados.
2. **Feedback loop**: Melhorar prompt quando a IA falha repetidamente.
3. **Suporte a lote**: Processar múltiplos arquivos de uma vez.
4. **Logs persistentes**: Armazenar logs em tabela SQLite para auditoria.
5. **Validação assíncrona**: Não bloquear a UI durante chamadas à IA.

---

*Documento gerado para o Desafio Franq — Pipeline de Ingestão CSV com IA*