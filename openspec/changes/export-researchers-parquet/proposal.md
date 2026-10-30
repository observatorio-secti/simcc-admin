# Proposal: Exportação de Pesquisadores em Parquet para Serviços Internos

## Why

Atualmente, rotinas de orquestração de dados como o `simcc-etl` realizavam consultas SQL diretas na tabela `academic.researchers` do banco de dados do `simcc-admin` (ou recorriam a fallbacks legados como `public.researcher`) para descobrir os identificadores Lattes a serem baixados do CNPq.

Essa abordagem gera alto acoplamento arquitetural (compartilhamento de credenciais diretas do banco PostgreSQL) e dificulta a evolução dos modelos cadastrais. Além disso, a transferência de grandes volumes de IDs pode ser otimizada através de formatos colunares compactados.

A solução consiste em expor um endpoint HTTP no `simcc-admin` que exporta a lista de `lattes_id` dos pesquisadores em formato Parquet, protegido por uma chave de serviço interna (`X-Service-Token`) com validação em tempo constante.

## What Changes

- Adição da configuração obrigatória `ADMIN_SERVICE_TOKEN: str` (sem valor padrão, impedindo que o serviço suba inseguro).
- Implementação da dependência de segurança `RequireServiceTokenOrRole(UserRole.ADMIN)` em `simcc_admin.security`, aceitando autenticação via cabeçalho `X-Service-Token` (comparado com `secrets.compare_digest`) ou via token JWT de usuário administrador.
- Criação do endpoint `GET /academic/researchers/export/parquet`, posicionado antes das rotas parametrizadas por UUID para evitar colisões de roteamento.
- O endpoint consulta exclusivamente pesquisadores válidos (`lattes_id IS NOT NULL AND TRIM(lattes_id) <> ''`) e gera um arquivo Parquet em memória (via Polars com compressão zstd) contendo estritamente a coluna `lattes_id`.
- Adição da dependência `polars` ao `pyproject.toml`.

Fora do escopo: alteração nos cadastros de pesquisadores, coleções ou outras rotas do domínio acadêmico.

## Capabilities

### New Capabilities
- `export-researchers`: Exportação binária em Parquet da lista de pesquisadores válidos (`lattes_id`) para consumo por serviços internos autorizados ou administradores.

### Modified Capabilities
- Nenhuma. O endpoint é puramente aditivo.

## Impact

- `src/simcc_admin/settings.py`: Nova variável obrigatória `ADMIN_SERVICE_TOKEN`.
- `src/simcc_admin/security.py`: Nova dependência de autenticação híbrida (Service Token ou JWT de Admin).
- `src/simcc_admin/routers/academic/researchers.py`: Novo endpoint `/export/parquet`.
- `pyproject.toml`: Inclusão da biblioteca `polars`.
- `.env.example` e documentação (`README.md`).
