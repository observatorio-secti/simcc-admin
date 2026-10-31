# Design: Delegar Gestão de Usuários e Autenticação ao Observatório IdP

## Context

O `simcc-admin` nasceu com autenticação local embutida (Argon2id, rotas `/auth/token`, `/users` e OAuth social Google/ORCID). Com a consolidação do `observatorio-idp` como autoridade central de identidade, todo o ciclo de vida de credenciais e contas federadas passa a residir exclusivamente no IdP.

## Decisions

1. **Eliminação Completa das Tabelas de Usuário**:
   - As tabelas `users` e `oauth_accounts` no schema `public` são dropadas por migração Alembic.
   - O schema `academic` (`institutions`, `researchers`, `collections`, etc.) não é afetado, pois nenhum modelo acadêmico possui chave estrangeira para `users`.

2. **`AuthenticatedUser` como Objeto em Memória**:
   - Em `simcc_admin/security.py`, definimos um dataclass:
     ```python
     @dataclass
     class AuthenticatedUser:
         id: UUID
         email: str | None
         name: str | None
         role: UserRole
     ```
   - `get_current_user` valida o token Bearer RS256 usando `PyJWKClient(settings.IDP_JWKS_URL, cache_keys=True)` ou `settings.IDP_PUBLIC_KEY_PEM` (útil em testes unitários).
   - O payload assinado do IdP contém:
     - `sub`: UUID do usuário.
     - `email`: e-mail do usuário.
     - `name`: nome completo.
     - `role`: `'ADMIN'` ou `'DEFAULT'`.
   - `AuthenticatedUser` é construído diretamente a partir dessas claims. Nenhuma consulta ao banco de dados é necessária para autenticar uma chamada de API.

3. **Compatibilidade com `RequireRole` e `RequireServiceTokenOrRole`**:
   - A dependência de proteção de rotas `RequireRole(UserRole.ADMIN)` verifica `current_user.role` da mesma forma que antes, mantendo a hierarquia (`ADMIN` pode acessar rotas `DEFAULT`).
   - `RequireServiceTokenOrRole` continua aceitando `X-Service-Token` (para microsserviços como `simcc-etl`) ou o Bearer token de um `AuthenticatedUser` admin.

4. **Testes sem Dependência de Rede Externa**:
   - Os testes unitários assinam tokens RS256 com um par de chaves RSA em memória (gerado na fixture do `conftest.py`) e injetam a chave pública correspondente em `settings.IDP_PUBLIC_KEY_PEM`, validando o fluxo de forma isolada, rápida e sem necessidade de conexão HTTP externa.
