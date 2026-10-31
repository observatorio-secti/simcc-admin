# Spec Delta: Stateless IdP Authentication

## Requirements

### Requirement: Validação de Token RS256 via JWKS
O `simcc-admin` SHALL validar tokens JWT Bearer utilizando o algoritmo RS256 e o endpoint JWKS ou chave pública do `observatorio-idp`.

#### Scenario: Token assinado válido
- **WHEN** uma requisição a uma rota protegida envia `Authorization: Bearer <token_rs256_valido>` com claim `"role": "ADMIN"`
- **THEN** a requisição é aceita e o usuário autenticado possui `role = UserRole.ADMIN`

#### Scenario: Token inválido ou com algoritmo incorreto
- **WHEN** uma requisição envia um token expirado, corrompido ou emitido com chave desconhecida
- **THEN** a resposta é HTTP 401 Unauthorized

### Requirement: Controle de Acesso por Cargo Stateless
O sistema SHALL extrair o papel do usuário diretamente da claim `role` do token sem consultar banco de dados.

#### Scenario: Usuário sem papel de administrador
- **WHEN** um usuário com claim `"role": "DEFAULT"` acessa `/academic/institutions`
- **THEN** a resposta é HTTP 403 Forbidden com `{"detail": "Not enough permissions"}`
