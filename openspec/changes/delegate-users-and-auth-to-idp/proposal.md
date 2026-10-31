# Proposal: Delegar Gestão de Usuários e Autenticação ao Observatório IdP

## Why

Atualmente, o `simcc-admin` gerencia suas próprias tabelas de usuários, senhas Argon2id e autenticação OAuth social com Google e ORCID. No entanto, no ecossistema Observatório, o princípio norteador de arquitetura determina que o **`observatorio-idp`** é a única autoridade responsável por responder *"Quem é essa pessoa?"* (`sub`, `email`, `name`, `role`). 

O `simcc-admin` deve atuar puramente como um **Resource Server** acadêmico e administrativo, validando tokens assimétricos RS256 de forma *stateless* via JWKS, eliminando duplicação de cadastros, senhas e integrações OAuth redundantes.

## What Changes

1. **Remoção de Usuários Locais**:
   - Remover as tabelas `public.users` e `public.oauth_accounts`.
   - Remover os routers `/auth` e `/users` e o módulo `simcc_admin/oauth/`.
   - Remover dependência e código de hashing de senhas (`pwdlib`).

2. **Validação Stateless de Tokens RS256 via JWKS**:
   - Atualizar `simcc_admin/security.py` para validar tokens RS256 emitidos pelo `observatorio-idp` utilizando `PyJWKClient` (com cache de chaves) contra o endpoint JWKS do IdP (`/.well-known/jwks.json`).
   - Construir o objeto `AuthenticatedUser(id, email, name, role)` diretamente das claims do JWT (`sub`, `email`, `name`, `role`), sem realizar consultas a tabelas locais de usuários.
   - Preservar o controle de permissões por papéis (`RequireRole(UserRole.ADMIN)` e `RequireServiceTokenOrRole(UserRole.ADMIN)`).

3. **Configuração e Bootstrap**:
   - Adicionar variáveis de ambiente do IdP (`IDP_ISSUER`, `IDP_JWKS_URL`, `IDP_AUDIENCE`, `IDP_PUBLIC_KEY_PEM`).
   - Atualizar `bootstrap.py` para inicializar apenas coleções acadêmicas padrão (sem tentar criar usuário admin local no banco).

## Capabilities

### Modified Capabilities
- `academic-api`: As rotas `/academic/*` continuam exigindo o papel `ADMIN`, mas agora validado diretamente a partir do token RS256 emitido pelo `observatorio-idp`.

## Impact
- `src/simcc_admin/models.py`: Remoção de `User` e `OAuthAccount`.
- `src/simcc_admin/routers/auth.py`, `src/simcc_admin/routers/users.py`, `src/simcc_admin/oauth/`: Removidos.
- `src/simcc_admin/app.py`: Remoção dos routers de usuário e autenticação.
- `src/simcc_admin/security.py`: Validação stateless via JWKS.
- `migrations/versions/`: Nova migração excluindo tabelas `oauth_accounts` e `users`.
