# SimCC Admin

Módulo administrativo do ecossistema SimCC focado em gestão acadêmica de instituições, pesquisadores e vínculos (`academic.institutions`, `academic.researchers`), com autenticação *stateless* baseada em tokens RS256 delegada integralmente ao **Observatório IdP**.

---

## 🛠️ Comandos Úteis

| Comando | Descrição |
|---|---|
| `poetry install` | Instala dependências do projeto |
| `poetry run poe serve` | Inicia o servidor de desenvolvimento (`fastapi dev`) |
| `poetry run pytest` | Roda a suíte de testes unitários e de integração |
| `poetry run poe lint` | Executa a verificação de código com Ruff |
| `poetry run poe format` | Aplica correções e formatação de código com Ruff |
| `poetry run python -m src.simcc_admin.import_institution_csvs` | Sincroniza/corrige pesquisadores e vínculos a partir dos CSVs oficiais das instituições |

---

## 📁 Estrutura de Pastas

```text
simcc-admin/
├── src/simcc_admin/
│   ├── app.py                      # Ponto de entrada FastAPI e registro de rotas
│   ├── database.py                 # Configuração do engine e sessão assíncrona (SQLAlchemy)
│   ├── models.py                   # Modelos acadêmicos (academic.institutions, academic.researchers)
│   ├── schemas.py                  # Schemas Pydantic para validação e serialização
│   ├── security.py                 # Validação stateless de JWT RS256 via JWKS (PyJWKClient) e X-Service-Token
│   ├── settings.py                 # Variáveis de ambiente com pydantic-settings
│   ├── bootstrap.py                # Inicialização da coleção padrão simcc
│   ├── import_institution_csvs.py  # Sincronização dos CSVs institucionais anotados (UFOB, EBMSP, UFRB)
│   └── routers/                    # Endpoints da aplicação
│       └── academic/       # Gestão acadêmica (instituições e pesquisadores)
│           ├── institutions.py
│           └── researchers.py  # CRUD e exportação Parquet (/academic/researchers/export/parquet)
├── tests/
│   ├── conftest.py         # Fixtures globais (PostgresContainer, chaves RSA in-memory, client, session)
│   ├── test_app.py         # Testes de rotas raiz e health check
│   ├── test_security.py    # Testes unitários de validação RS256 e controle de papéis (RequireRole)
│   └── test_academic.py    # Testes das rotas acadêmicas e exportação Parquet
├── openspec/               # Propostas de mudanças e especificações guiadas por comportamento
└── pyproject.toml          # Dependências, configurações de ferramentas e tarefas Poe
```

---

## 🧪 Como os Testes São Implementados

* **Validação de Token Stateless**: Os testes utilizam chaves RSA geradas em memória para emitir tokens RS256 de teste com claims `sub`, `email`, `role`, validando a segurança sem dependência de conexões de rede externas.
* **Banco Real com Testcontainers**: A fixture de engine inicia um container PostgreSQL (`PostgresContainer("postgres:16")`), garantindo isolamento total sem mocks de banco.
* **Isolamento de Sessão**: Cada teste usa a fixture `session`, que cria as tabelas (`create_all`), injeta a `AsyncSession` no FastAPI via `app.dependency_overrides[get_session]` e remove os dados no teardown (`drop_all`).
* **TestClient**: As requisições HTTP nos testes utilizam o `TestClient` síncrono do Starlette/FastAPI apontando para a aplicação com as dependências sobrescritas.

---

## 🛣️ Como os Routers São Desenvolvidos

1. **Definição com Prefixo e Tags**:
   Cada domínio possui seu módulo em `src/simcc_admin/routers/` instanciando um `APIRouter(prefix="...", tags=["..."])`.

2. **Injeção de Dependências Tipadas**:
   Uso de `typing.Annotated` para injetar sessão do banco de dados e usuário autenticado via IdP:
   ```python
   Session = Annotated[AsyncSession, Depends(get_session)]
   CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
   RequireAdmin = Annotated[AuthenticatedUser, Depends(RequireRole(UserRole.ADMIN))]
   ```

3. **Operações Assíncronas**:
   Queries são assíncronas utilizando a sintaxe do SQLAlchemy 2.0 (`await session.scalar(...)`, `await session.commit()`).

---

## ⚙️ Configuração (`.env`)

| Variável | Obrigatória | Descrição | Padrão |
|---|:---:|---|---|
| `DATABASE_URL` | Sim | URL assíncrona do PostgreSQL (`postgresql+psycopg://...`) | — |
| `ADMIN_SERVICE_TOKEN` | Sim | Token secreto de serviço (*Machine-to-Machine*) para integrações internas (ex.: `simcc-etl`) | — |
| `IDP_ISSUER` | Não | Issuer esperado no token RS256 do IdP | `https://observatoriocti.secti.ba.gov.br/idp` |
| `IDP_JWKS_URL` | Não | Endpoint público JWKS para validação das chaves RSA | `https://observatoriocti.secti.ba.gov.br/idp/.well-known/jwks.json` |
| `IDP_AUDIENCE` | Não | Audience esperada no token (se configurado) | `None` |
| `IDP_PUBLIC_KEY_PEM`| Não | Chave pública RSA alternativa (PEM) para validação estática offline | `None` |

---

## 🌐 Endpoints Principais

### Gestão Acadêmica (`/academic`)
* `GET /academic/institutions`: Listagem paginada de instituições cadastradas
* `POST /academic/institutions`: Criação de nova instituição (requer papel `ADMIN` no IdP)
* `GET /academic/researchers`: Listagem paginada de pesquisadores
* `POST /academic/researchers`: Cadastro ou vinculação de pesquisador (requer papel `ADMIN` no IdP)
* `GET /academic/researchers/export/parquet`: Exportação binária em Parquet com `lattes_id` dos pesquisadores ativos. Autenticação via header `X-Service-Token` (ou token JWT de `ADMIN`).
