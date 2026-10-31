# Tasks: Delegar Gestão de Usuários e Autenticação ao Observatório IdP

## 1. Limpeza de Modelos e Migração
- [x] 1.1 Remover modelos `User` e `OAuthAccount` de `src/simcc_admin/models.py`.
- [x] 1.2 Criar migração Alembic para dropar as tabelas `public.oauth_accounts` e `public.users`.
- [x] 1.3 Atualizar `bootstrap.py` para não tentar criar usuário administrador no banco.

## 2. Remoção de Rotas e Dependências Locais
- [x] 2.1 Remover `src/simcc_admin/routers/auth.py`, `src/simcc_admin/routers/users.py` e a pasta `src/simcc_admin/oauth/`.
- [x] 2.2 Atualizar `src/simcc_admin/app.py` desregistrando os routers `/auth` e `/users`.
- [x] 2.3 Limpar schemas relacionados a usuários locais em `src/simcc_admin/schemas.py`.

## 3. Implementação Stateless em `security.py`
- [x] 3.1 Atualizar `src/simcc_admin/settings.py` com `IDP_ISSUER`, `IDP_JWKS_URL`, `IDP_AUDIENCE` e `IDP_PUBLIC_KEY_PEM`.
- [x] 3.2 Definir `AuthenticatedUser` e implementar decodificação RS256 via `PyJWKClient` / `IDP_PUBLIC_KEY_PEM` em `src/simcc_admin/security.py`.
- [x] 3.3 Adaptar `RequireRole` e `RequireServiceTokenOrRole` para operar sobre `AuthenticatedUser`.

## 4. Testes e Validação
- [x] 4.1 Remover testes legados de login/usuário (`test_auth.py`, `test_users.py`, `test_oauth.py`).
- [x] 4.2 Atualizar fixtures em `tests/conftest.py` para emitir tokens RS256 de teste com par de chaves RSA em memória.
- [x] 4.3 Atualizar `tests/test_security.py` e `tests/test_rbac.py` para validar o fluxo RS256 e RBAC.
- [x] 4.4 Executar suíte de testes do `simcc-admin` e garantir aprovação.
