# Documentação de Endpoints e Autenticação (SIMCC Admin)

Este documento descreve todos os endpoints disponíveis na API, organizados por blocos funcionais, suas políticas de controle de acesso (RBAC), e os métodos suportados para autenticação e login.

---

## 1. Métodos de Autenticação e Login na API

Atualmente, a plataforma suporta **três fluxos de autenticação**, todos convergindo para a emissão de tokens de acesso **JWT (Bearer Token)**.

### 1.1 Login Tradicional (E-mail / Username + Senha)
Utiliza o padrão OAuth2 Password Flow.
- **Endpoint**: `POST /auth/token`
- **Content-Type**: `application/x-www-form-urlencoded`
- **Corpo da Requisição**:
  ```bash
  username=admin@simcc.org   # Pode ser o email ou o username cadastrado
  password=admin_secret_password
  ```
- **Resposta (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```

---

### 1.2 Login Social via Google OAuth 2.0
Fluxo desacoplado para aplicações Frontend (SPA) ou Navegador.
1. **Iniciar Login**:
   - `GET /auth/google/login`
   - O backend gera o `state` de segurança e redireciona (HTTP 307) para a tela de consentimento da Google.
2. **Callback e Emissão do Token**:
   - `GET /auth/google/callback?code=...&state=...`
   - O servidor troca o código pelo token do Google, obtém os dados do perfil, cria ou vincula a conta no banco de dados e redireciona para a URL do frontend configurada (`FRONTEND_AUTH_CALLBACK_URL`):
     ```
     http://localhost:3000/auth/callback?token=<JWT>&token_type=bearer
     ```

---

### 1.3 Login Acadêmico via ORCID OAuth 2.0
Fluxo com suporte a ambiente Sandbox e Produção.
1. **Iniciar Login**:
   - `GET /auth/orcid/login`
   - Redireciona o usuário para a página de autorização do ORCID.
2. **Callback e Emissão do Token**:
   - `GET /auth/orcid/callback?code=...&state=...`
   - Obtém o ORCID iD e dados do pesquisador, cadastra ou vincula o usuário no sistema e redireciona com o token JWT emitido:
     ```
     http://localhost:3000/auth/callback?token=<JWT>&token_type=bearer
     ```

---

### 1.4 Como Utilizar o Token nas Requisições
Em todos os endpoints protegidos, envie o token no cabeçalho HTTP:
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

### 1.5 Primeiro Usuário do Sistema (Bootstrap Automático)
Ao subir o contêiner ou executar o entrypoint da aplicação, o script `bootstrap.py` lê as variáveis do `.env`:
```ini
ADMIN_USERNAME="admin"
ADMIN_EMAIL="admin@simcc.org"
ADMIN_PASSWORD="admin_secret_password"
```
Se o banco ainda não possuir o usuário administrador, ele é semeado automaticamente com cargo `ADMIN`. Caso já exista, a operação é ignorada de forma idempotente.

---

## 2. Catálogo de Endpoints da Plataforma

### 2.1 Bloco: Sistema & Status

| Método | Endpoint | Acesso | Descrição |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Público | Healthcheck da API (retorna mensagem de boas-vindas). |

---

### 2.2 Bloco: Autenticação & Sessão (`/auth`)

| Método | Endpoint | Acesso | Descrição |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/token` | Público | Autenticação local por senha; retorna token de acesso JWT. |
| `POST` | `/auth/refresh` | Autenticado | Atualiza e renova o token JWT do usuário atual. |
| `GET` | `/auth/{provider}/login` | Público | Inicia o fluxo OAuth 2.0 (`google` ou `orcid`). |
| `GET` | `/auth/{provider}/callback` | Público | Callback de autorização do provedor OAuth 2.0. |

---

### 2.3 Bloco: Usuários (`/users`)

| Método | Endpoint | Acesso / RBAC | Descrição |
| :--- | :--- | :--- | :--- |
| `POST` | `/users/` | Público | Cadastro de novo usuário no sistema (atribuído com cargo `DEFAULT`). |
| `GET` | `/users/me` | Autenticado (`DEFAULT` ou `ADMIN`) | Retorna os dados cadastrais e o cargo (`role`) do próprio usuário autenticado. |
| `GET` | `/users/` | **Apenas `ADMIN`** | Listagem paginada de todos os usuários do sistema (Envelope Padronizado). |
| `PUT` | `/users/{user_id}` | Próprio Usuário ou `ADMIN` | Atualiza dados (username, email, senha) do usuário. Usuário `DEFAULT` só pode atualizar a si mesmo. |
| `DELETE` | `/users/{user_id}` | Próprio Usuário ou `ADMIN` | Deleta uma conta. Usuário `DEFAULT` só pode deletar a si mesmo. |

---

### 2.4 Bloco: Domínio Acadêmico - Instituições (`/academic/institutions`)

| Método | Endpoint | Acesso / RBAC | Descrição |
| :--- | :--- | :--- | :--- |
| `GET` | `/academic/institutions` | **Apenas `ADMIN`** | Busca e lista instituições paginadas com filtros por nome/sigla (`q`), ordenação (`sort_by`, `sort_order`). |
| `POST` | `/academic/institutions/` | **Apenas `ADMIN`** | Cadastra uma nova instituição de ensino/pesquisa (`name`, `acronym`). |
| `GET` | `/academic/institutions/{id}` | **Apenas `ADMIN`** | Obtém os dados detalhados de uma instituição específica por UUID. |
| `PUT` | `/academic/institutions/{id}` | **Apenas `ADMIN`** | Atualiza os dados de uma instituição existente. |
| `DELETE` | `/academic/institutions/{id}` | **Apenas `ADMIN`** | Remove uma instituição do sistema. |

---

### 2.5 Bloco: Domínio Acadêmico - Pesquisadores (`/academic/researchers`)

| Método | Endpoint | Acesso / RBAC | Descrição |
| :--- | :--- | :--- | :--- |
| `GET` | `/academic/researchers` | **Apenas `ADMIN`** | Busca e lista pesquisadores paginados no envelope padrão. Suporta busca textual por nome ou Lattes ID (`q`), filtro por instituição (`institution_id`), paginação (`page`, `per_page`) e ordenação (`sort_by`, `sort_order`). |
| `POST` | `/academic/researchers/` | **Apenas `ADMIN`** | Cadastra um pesquisador com vínculo opcional a uma lista de instituições (`institution_ids`). |
| `GET` | `/academic/researchers/{id}` | **Apenas `ADMIN`** | Obtém detalhes completos do pesquisador, incluindo o bloco composto de vínculos (`affiliations`). |
| `PUT` | `/academic/researchers/{id}` | **Apenas `ADMIN`** | Atualiza os dados cadastrais (nome, Lattes ID) de um pesquisador. |
| `DELETE` | `/academic/researchers/{id}` | **Apenas `ADMIN`** | Remove um pesquisador e seus vínculos associados em cascata. |
| `POST` | `/academic/researchers/{id}/institutions/{institution_id}` | **Apenas `ADMIN`** | Cria atomicamente o vínculo de afiliação entre um pesquisador e uma instituição. |
| `DELETE` | `/academic/researchers/{id}/institutions/{institution_id}` | **Apenas `ADMIN`** | Remove atomicamente o vínculo de afiliação entre um pesquisador e uma instituição. |

---

## 3. Padrão das Respostas (Envelope Padronizado)

Todas as rotas de listagem e busca paginada utilizam o envelope estruturado:

```json
{
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_items": 150,
    "total_pages": 8,
    "has_next": true,
    "has_prev": false
  },
  "filters_applied": {
    "q": "inteligência",
    "institution_id": "a5d0a688-2940-42cf-9ca7-ee646e7f2597"
  },
  "sort": {
    "by": "name",
    "order": "asc"
  },
  "meta": {
    "took_ms": 12,
    "cached": false,
    "timestamp": "2026-10-01T21:15:00Z"
  },
  "facets": null,
  "summary": null
}
```
