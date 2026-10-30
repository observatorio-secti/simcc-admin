# Tasks

- [x] 1. Configuração e Dependências <!-- id: 1 -->
  - [x] 1.1 Adicionar `polars` às dependências no `pyproject.toml`
  - [x] 1.2 Declarar `ADMIN_SERVICE_TOKEN: str` sem valor padrão em `src/simcc_admin/settings.py`
  - [x] 1.3 Adicionar `ADMIN_SERVICE_TOKEN` no `.env.example` e no `.env` local de desenvolvimento

- [x] 2. Camada de Segurança <!-- id: 2 -->
  - [x] 2.1 Implementar `RequireServiceTokenOrRole` em `src/simcc_admin/security.py` com `secrets.compare_digest`

- [x] 3. Endpoint de Exportação Parquet <!-- id: 3 -->
  - [x] 3.1 Declarar `GET /export/parquet` antes de `GET /{researcher_id}` em `src/simcc_admin/routers/academic/researchers.py`
  - [x] 3.2 Executar query filtrada com `lattes_id IS NOT NULL AND TRIM(lattes_id) <> ''`
  - [x] 3.3 Serializar DataFrame Polars em buffer Parquet compactado com zstd
  - [x] 3.4 Retornar resposta binária `application/octet-stream` com filename apropriado

- [x] 4. Testes Automatizados e Validação <!-- id: 4 -->
  - [x] 4.1 Criar testes em `tests/test_academic.py` cobrindo sucesso com Service Token, sucesso com JWT de Admin, e rejeição com token inválido/ausente
  - [x] 4.2 Executar suíte de testes com `pytest`

- [x] 5. Documentação <!-- id: 5 -->
  - [x] 5.1 Atualizar `Simcc/simcc-admin/README.md` com a nova rota e a variável de ambiente
