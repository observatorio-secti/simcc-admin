# Tasks

## 1. Modelo e migration

- [x] 1.1 Adicionar `Collection` e `ResearcherCollection` em `src/simcc_admin/models.py` (schema `academic`, `CHECK refresh_interval_days >= 1`, índice único parcial em `is_default`, FK de coleção `RESTRICT`, `attributes` JSONB) e a relação `Researcher.collections`.
- [x] 1.2 Adicionar fixtures e factories para coleções.
- [x] 1.3 Criar a revisão Alembic (`b7c4e91a2d01_add_researcher_collections.py`) com tabelas, índice, seed de `simcc` e `fomento` e backfill.

## 2. Catálogo de coleções

- [x] 2.1 Adicionar em `src/simcc_admin/schemas.py` os schemas `CollectionCreate`, `CollectionUpdate`, `CollectionRef` e `CollectionPublic` (com `researcher_count`).
- [x] 2.2 Criar `routers/academic/collections.py` com listagem paginada (`q`, ordenação, `researcher_count`), detalhe, criação, edição e remoção, e registrar o router em `routers/academic/__init__.py`.

## 3. Pertencimento de pesquisadores

- [x] 3.1 Adicionar `CollectionMembership` e `MembershipAttributes` aos schemas, `collections` em `ResearcherItem` e `collection_id` em `FiltersApplied`, e montar a lista ordenada por nome em `researchers.py`.
- [x] 3.2 Implementar `POST`, `PUT` e `DELETE /academic/researchers/{researcher_id}/collections/{collection_id}`.
- [x] 3.3 Fazer `create_researcher` aceitar `collection_ids`, usar a coleção padrão quando vier vazio e devolver 422 sem gravar nada para id desconhecido ou ausência de padrão.
- [x] 3.4 Adicionar o filtro `collection_id` na busca usando `EXISTS`, combinável com `q` e `institution_id`.
- [x] 3.5 Atualizar rota `/academic/researchers/export/parquet` com `refresh_interval_days` e filtro opcional `?collection=`.

## 4. Documentação e integração

- [x] 4.1 Atualizar o `README.md` (rotas de coleções, conceito e endpoints).
- [x] 4.2 Executar testes e script de carga `seed_collections_and_researchers.py`.

## Workflow follow-up

- Arquivar a change após revisão (`openspec archive add-researcher-collections`).
- Abrir as changes seguintes: importação de planilha no admin, filtro por coleção no simcc-back (MVs de pesquisadores e produções) e seleção por `refresh_interval_days` / `last_extracted_at` no Hop.
