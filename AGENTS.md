# AGENTS.md — SimCC Admin (`simcc-admin`)

Este repositório faz parte do **Ecossistema Observatório CT&I Bahia / SimCC**. Ele é versionado de forma independente e atua como o **serviço administrativo e cadastro fonte (`admin_db`)** de usuários, instituições (`academic.institutions`), pesquisadores (`academic.researchers`) e vínculos institucionais (`academic.researcher_institutions`).

> Para entender a integração deste serviço com `simcc-etl`, `Jade-Extrator-Hop` e `simcc-back`, consulte `../README.md` (`Simcc/README.md`) e `../../AGENTS.md`.

---

## 1. Princípios Arquiteturais e Contratos com o Ecossistema

1. **Contrato do Schema `academic` (`admin_db` — Porta Host `5433`)**:
   - As tabelas `academic.institutions`, `academic.researchers` e `academic.researcher_institutions` são lidas diretamente via JDBC pelo **Apache Hop (`Jade-Extrator-Hop`)** nos pipelines `ImportInstitution.hpl` e `ImportResearcher.hpl`, e via SQLAlchemy pelo **`simcc-etl`** (`soap_lattes`).
   - Qualquer alteração de coluna ou constraint no schema `academic` **exige alinhamento simultâneo** em `Simcc/Jade-Extrator-Hop` e `Simcc/simcc-etl`.
2. **Padrão de Routers e Segurança**:
   - Injeção de dependências com `typing.Annotated` (`Session = Annotated[AsyncSession, Depends(get_session)]`, `CurrentUser = Annotated[User, Depends(get_current_user)]`).
   - Sempre definir `response_model` explícito para evitar exposição de hashes de senha Argon2.
   - Suporte a autenticação delegada/integrada com o `observatorio-idp` e login OAuth (Google / ORCID).
3. **Testes Isolados com Testcontainers**:
   - Os testes utilizam um banco PostgreSQL real via `PostgresContainer("postgres:16")` em `tests/conftest.py`, com `factory-boy` e `freezegun`.
4. **Idioma e Convenções**:
   - Documentação, comentários, artefatos `openspec/`, mensagens de erro e commits em **Português do Brasil (pt-BR)**.
   - Identificadores de código em **inglês**.

---

## 2. Comandos Padrão de Desenvolvimento

- **Instalar dependências**: `poetry install`
- **Iniciar servidor dev**: `poetry run poe serve`
- **Aplicar migrações**: `poetry run alembic upgrade head`
- **Executar bootstrap inicial**: `poetry run python -m simcc_admin.bootstrap`
- **Testes + lint + cobertura**: `poetry test` (ou `poetry run pytest`)
- **Lint e formatação**: `poetry run poe lint` e `poetry run poe format`

---

## 3. Padrão de Documentação e Gatilhos Obrigatórios (Definition of Done)

A documentação deste repositório vive em [`README.md`](README.md) e nas especificações de [`openspec/`](openspec/). A integração ponta a ponta do SimCC está documentada em `../README.md`.

### Tabela de Atualização Obrigatória

**Nenhuma alteração de código está pronta sem atualizar a documentação correspondente na mesma tarefa:**

| Se você alterar... | Atualize obrigatoriamente: |
| :--- | :--- |
| Variáveis em `src/simcc_admin/settings.py` | `.env.example` (se aplicável), `README.md` e a seção de `.env` em `../README.md` (`Simcc/README.md`) |
| Modelos e migrações (especialmente no schema `academic`) | `README.md` e `../README.md` (verificando impacto em `Jade-Extrator-Hop` e `simcc-etl`) |
| Rotas em `src/simcc_admin/routers/` ou estrutura de pastas em `src/` | Árvore **📁 Estrutura de Pastas** e documentação de rotas no `README.md` |
| Tarefas Poe em `pyproject.toml` | Tabela **🛠️ Comandos Úteis** no `README.md` |
