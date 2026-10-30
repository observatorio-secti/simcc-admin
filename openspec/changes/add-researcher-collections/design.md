# Design

## Context

Hoje o schema `academic` tem `institutions`, `researchers` (único por `lattes_id`) e `researcher_institutions` (N:N). As rotas ficam em `routers/academic/` e seguem um padrão: `RequireRole(UserRole.ADMIN)` no router, envelope paginado (`Pagination`, `Sort`, `Meta`), `selectinload` para relações e 409 em conflito de unicidade. Os testes sobem Postgres via testcontainers e criam as tabelas com `metadata.create_all`, sem rodar migrations. Por isso, nada que a API precise para funcionar pode depender de dado semeado só pela migration.

Motivação em proposal.md, comportamento em `specs/`.

## Goals / Non-Goals

**Goals:**
- Modelar coleção e pertencimento sem alterar `researchers` nem `researcher_institutions`.
- Deixar `slug` e `refresh_interval_days` prontos para o simcc-back e o Hop consultarem direto no banco.

**Non-Goals:**
- Importação de planilha (change própria, que vai reutilizar a rota de vínculo e `attributes`).
- Filtro por coleção nas MVs e queries do simcc-back, e seleção por intervalo no Hop, incluindo `last_extracted_at`.
- Permissão por coleção (`user_collections`).
- Tornar `lattes_id` opcional.
- Mudar o `DELETE /academic/researchers/{id}`. Ele continua apagando a pessoa e todos os vínculos.

## Decisions

**Tabela de vínculo em vez de coluna booleana por coleção.** Cada coleção nova seria uma migration e um campo novo. Com linhas, uma coleção nova é só um `POST`. Alternativa descartada: enum ou array de slugs em `researchers`, que não comporta `attributes` por vínculo nem FK.

**Models.** Seguem o estilo de `ResearcherInstitution`:
- `Collection`: `id`, `slug` (único, indexado), `name` (único), `description` (nullable), `refresh_interval_days` (int, `server_default=1`, `CHECK >= 1`), `is_default` (bool, `server_default=false`), `created_at`.
- `ResearcherCollection`: `id`, `researcher_id` (FK CASCADE), `collection_id` (FK RESTRICT), `attributes` (JSONB, `server_default='{}'`), `created_at`, `UniqueConstraint(researcher_id, collection_id, name="uq_researcher_collection")`.
- `Researcher.collections` com `cascade="all, delete-orphan"`, como em `institutions`.

O FK para coleção é `RESTRICT`, ao contrário do `CASCADE` usado em instituições. Assim, mesmo um `DELETE` direto no banco não apaga em silêncio os vínculos de uma coleção como `simcc`. A rota devolve 409 antes de chegar ao banco.

**Unicidade do padrão no banco.** Um índice único parcial, `CREATE UNIQUE INDEX ... ON academic.collections (is_default) WHERE is_default`, garante no máximo uma coleção padrão. A troca de padrão desmarca a anterior e marca a nova na mesma transação.

**Intervalo em dias inteiros, não em `INTERVAL`.** É mais simples de validar no Pydantic e de serializar no JSON, e o Hop usa com `make_interval(days => refresh_interval_days)`. Ninguém precisa de granularidade abaixo de um dia.

**`attributes` como JSONB livre.** Cada planilha tem colunas diferentes. Validamos apenas que o valor é um objeto JSON (`dict[str, Any]`). Quando um campo precisar de filtro ou relatório próprio, ele vira coluna ou tabela em outra change.

**Slug imutável.** `CollectionUpdate` não declara `slug`. Para que a tentativa de alterá-lo dê 422, como diz a spec, o schema usa `model_config = ConfigDict(extra="forbid")`. Assim um `slug` no corpo é rejeitado, em vez de ignorado em silêncio.

**Coleção padrão resolvida em runtime.** `create_researcher` busca a coleção com `is_default = true` quando `collection_ids` vem vazio. Não há slug `simcc` fixo no código, então os testes criam a própria coleção padrão via fixture. O pesquisador e os vínculos são gravados no mesmo commit: se uma coleção for inválida, nada é gravado. Isso difere do comportamento atual com `institution_ids`, que ignora ids desconhecidos em silêncio.

**Busca sem duplicar.** O filtro `collection_id` usa `EXISTS` (subquery correlacionada) em vez de `JOIN`. Combinado com o filtro de instituição, um `JOIN` duplicaria linhas e exigiria `distinct`. Na mesma passada, o filtro de instituição pode passar a usar `EXISTS`, e o `count(distinct)` continua correto.

**Rotas.** `routers/academic/collections.py` espelha `institutions.py`. A contagem de membros sai de uma subquery com `count` agrupado por coleção. As rotas de vínculo ficam em `researchers.py`, ao lado das de instituição. As respostas usam `CollectionRef` (`id`, `slug`, `name`) e `CollectionMembership` (`collection`, `attributes`, `created_at`), com a mesma composição de `Affiliation`/`InstitutionRef`.

## Risks / Trade-offs

- [Pesquisador criado sem coleção por outro caminho (SQL direto, ETL)] → Fica fora das buscas filtradas. O backfill cobre o legado. Uma checagem de órfãos pode entrar na change de importação.
- [`attributes` sem schema vira depósito de dados inconsistentes] → A change de importação define as chaves esperadas por coleção.
- [`DELETE /researchers/{id}` apaga a pessoa de todas as coleções] → Mantido por escopo, mas fica registrado. O front do admin deve preferir remover o vínculo.
- [Consumidores ainda não filtram por coleção] → Até as changes do simcc-back e do Hop, bolsistas cadastrados aqui aparecem no Simcc. Não importar bolsistas em produção antes delas.

## Migration Plan

1. Nova revisão Alembic (`down_revision = "3e83d2129a16"`): criar `academic.collections` com o índice parcial e `academic.researcher_collections`.
2. Na mesma revisão, `INSERT` de `simcc` (`is_default = true`, intervalo 1) e `INSERT ... SELECT id FROM academic.researchers` para o backfill.
3. Downgrade: drop das duas tabelas. Não há perda de dado anterior à change.
