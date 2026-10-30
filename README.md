# SimCC Admin

Módulo administrativo do SimCC focado em gerenciamento de usuários e autenticação assíncrona com FastAPI e SQLAlchemy.

---

## 🛠️ Comandos Úteis

| Comando | Descrição |
|---|---|
| `poetry install` | Instala dependências do projeto |
| `poetry run poe serve` | Inicia o servidor de desenvolvimento (`fastapi dev`) |
| `poetry test` | Executa lint, suíte de testes e gera relatório de cobertura HTML |
| `poetry run poe lint` | Executa a verificação de código com Ruff |
| `poetry run poe format` | Aplica correções e formatação de código com Ruff |
| `poetry run pytest` | Roda diretamente a suíte de testes |

---

## 📁 Estrutura de Pastas

```text
simcc-admin/
├── src/simcc_admin/
│   ├── app.py              # Ponto de entrada FastAPI e registro de rotas
│   ├── database.py         # Configuração do engine e sessão assíncrona (SQLAlchemy)
│   ├── models.py           # Modelos de banco de dados (mapped_as_dataclass)
│   ├── schemas.py          # Schemas Pydantic para validação e serialização
│   ├── security.py         # Hashing de senha (Argon2), criação/validação de JWT e X-Service-Token
│   ├── settings.py         # Variáveis de ambiente com pydantic-settings
│   └── routers/            # Endpoints da aplicação
│       ├── auth.py         # Autenticação e tokens (/auth)
│       ├── users.py        # CRUD de usuários (/users)
│       └── academic/       # Gestão acadêmica (instituições e pesquisadores)
│           ├── institutions.py
│           └── researchers.py  # CRUD e exportação Parquet (/academic/researchers/export/parquet)
├── tests/
│   ├── conftest.py         # Fixtures globais (PostgresContainer, client, session, token)
│   ├── test_app.py         # Testes de rotas raiz
│   ├── test_auth.py        # Testes de autenticação e expiração de token
│   ├── test_security.py    # Testes unitários de hashing e JWT
│   ├── test_academic.py    # Testes das rotas acadêmicas e exportação Parquet
│   └── test_users.py       # Testes de integração do CRUD de usuários
└── pyproject.toml          # Dependências, configurações de ferramentas e tarefas Poe
```

---

## 🧪 Como os Testes São Implementados

* **Banco Real com Testcontainers**: A fixture de engine inicia um container PostgreSQL (`PostgresContainer("postgres:16")`), garantindo isolamento total sem mocks de banco.
* **Isolamento de Sessão**: Cada teste usa a fixture `session`, que cria as tabelas (`create_all`), injeta a `AsyncSession` no FastAPI via `app.dependency_overrides[get_session]` e remove os dados no teardown (`drop_all`).
* **TestClient**: As requisições HTTP nos testes utilizam o `TestClient` síncrono do Starlette/FastAPI apontando para a aplicação com as dependências sobrescritas.
* **Factories e Autenticação**: A criação de modelos é auxiliada pelo `factory-boy` (`UserFactory`), e a fixture `token` gera automaticamente o Bearer Token necessário para rotas autenticadas.
* **Manipulação de Tempo**: O pacote `freezegun` é empregado em testes de expiração de token para congelar e avançar o relógio do sistema de forma controlada.

---

## 🛣️ Como os Routers São Desenvolvidos

1. **Definição com Prefixo e Tags**:
   Cada domínio possui seu módulo em `src/simcc_admin/routers/` instanciando um `APIRouter(prefix="...", tags=["..."])`.

2. **Injeção de Dependências Tipadas**:
   Uso de `typing.Annotated` para injetar sessão do banco de dados e usuário autenticado:
   ```python
   Session = Annotated[AsyncSession, Depends(get_session)]
   CurrentUser = Annotated[User, Depends(get_current_user)]
   ```

3. **Validação de Entrada e Resposta**:
   - Parâmetros e corpos de requisição usam schemas Pydantic (`UserSchema`, `OAuth2Form`).
   - Rotas tipam o modelo de retorno com `response_model` (`UserPublic`, `Token`, `UserList`), impedindo vazamento de dados sensíveis (como hashes de senha).

4. **Operações Assíncronas**:
   Queries são assíncronas utilizando a syntax do SQLAlchemy 2.0 (`await session.scalar(...)`, `await session.commit()`).

5. **Registro na Aplicação**:
   Todo novo router deve ser incluído em `src/simcc_admin/app.py`:
   ```python
   app.include_router(novo_router.router)
   ```

---

## ⚙️ Configuração (`.env`)

| Variável | Obrigatória | Descrição |
|---|:---:|---|
| `DATABASE_URL` | Sim | URL assíncrona do PostgreSQL (`postgresql+psycopg://...`) |
| `SECRET_KEY` | Sim | Chave de assinatura dos tokens JWT |
| `ALGORITHM` | Sim | Algoritmo de hash JWT (ex.: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Sim | Tempo de expiração do token de acesso (ex.: `30`) |
| `ADMIN_SERVICE_TOKEN` | Sim | Token secreto de serviço (*Machine-to-Machine*) para integrações internas (ex.: `simcc-etl`) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Não | Credenciais para bootstrap do primeiro usuário administrador |

---

## 🌐 Endpoints Principais

### Autenticação e Usuários
* `POST /auth/token`: Login de usuário (retorna JWT)
* `POST /auth/refresh`: Renovação de token de acesso
* `GET /users`: Listagem de usuários (requer `ADMIN`)
* `POST /users`: Criação de novo usuário

### Gestão Acadêmica (`/academic`)
* `GET /academic/institutions`: Listagem paginada de instituições
* `GET /academic/researchers`: Listagem paginada de pesquisadores
* `GET /academic/researchers/export/parquet`: Exportação binária em Parquet com `lattes_id` dos pesquisadores ativos. Autenticação via header `X-Service-Token` (ou token JWT de `ADMIN`).
