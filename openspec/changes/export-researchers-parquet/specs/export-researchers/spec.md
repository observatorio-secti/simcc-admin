# export-researchers Specification

## Overview
Permite a exportação de pesquisadores ativos no sistema em formato binário Parquet para integração com serviços de pipeline de dados (como o `simcc-etl`) ou download por administradores.

## Requirements

### Requirement: Autenticação Segura de Serviço
O endpoint `GET /academic/researchers/export/parquet` DEVE aceitar autenticação via cabeçalho HTTP `X-Service-Token` ou via Bearer Token JWT de usuário com role `ADMIN`.

#### Scenario: Acesso autorizado via X-Service-Token
- **GIVEN** que a variável `ADMIN_SERVICE_TOKEN` está configurada no servidor com um valor seguro
- **WHEN** um cliente faz `GET /academic/researchers/export/parquet` com o cabeçalho `X-Service-Token` correspondente
- **THEN** o status HTTP DEVE ser 200 OK e a resposta DEVE conter um arquivo Parquet válido.

#### Scenario: Rejeição com X-Service-Token incorreto
- **GIVEN** que o cliente envia um `X-Service-Token` divergente do configurado
- **WHEN** a requisição `GET /academic/researchers/export/parquet` é enviada
- **THEN** o status HTTP DEVE ser 401 Unauthorized com a mensagem `Invalid service token`.

#### Scenario: Acesso autorizado via JWT de Administrador
- **GIVEN** um usuário autenticado com a role `ADMIN`
- **WHEN** a requisição `GET /academic/researchers/export/parquet` é feita sem `X-Service-Token`, mas com `Authorization: Bearer <token_admin>`
- **THEN** o status HTTP DEVE ser 200 OK.

#### Scenario: Rejeição sem credenciais
- **GIVEN** que a requisição não contém nem `X-Service-Token` válido nem token JWT de administrador
- **WHEN** a requisição `GET /academic/researchers/export/parquet` é enviada
- **THEN** o status HTTP DEVE ser 401 Unauthorized.

### Requirement: Filtragem e Conteúdo do Parquet
O arquivo Parquet gerado DEVE conter exclusivamente a coluna `lattes_id`, contendo apenas registros onde `lattes_id` não é nulo e não é string em branco.

#### Scenario: Dados do arquivo exportado
- **GIVEN** pesquisadores cadastrados com Lattes válidos e pesquisadores com Lattes nulo ou em branco
- **WHEN** o Parquet é baixado e desserializado
- **THEN** ele DEVE conter apenas a coluna `lattes_id` e conter somente os valores não vazios.
