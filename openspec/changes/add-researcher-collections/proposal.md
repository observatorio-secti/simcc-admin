# Proposal

## Why

O banco do Simcc passou a guardar pesquisadores que não fazem parte do Simcc: bolsistas vindos da planilha da Fapesb e participantes dos Clubes de Ciência. Hoje não há como dizer a que conjunto cada pesquisador pertence, então eles se misturariam nas buscas e painéis do Simcc. Usar uma instituição falsa ("Fapesb") quebra o modelo de vínculos N:N, porque a mesma pessoa pode estar no Simcc e em outro conjunto ao mesmo tempo.

## What Changes

- Novo conceito **coleção** (`collection`): um conjunto nomeado de pesquisadores (ex.: `simcc`, `fapesb-bolsistas`, `clubes-ciencia`), com slug imutável e intervalo de atualização em dias, que o Apache Hop vai usar.
- Novo vínculo pesquisador ↔ coleção (N:N), com `attributes` livres (JSON) para guardar dados específicos de cada coleção, como as colunas da planilha.
- CRUD de coleções em `/academic/collections`, restrito a administradores.
- Rotas para adicionar, atualizar e remover um pesquisador de uma coleção em `/academic/researchers/{id}/collections/{collection_id}`.
- Busca de pesquisadores ganha o filtro `collection_id`, e as respostas de pesquisador passam a listar suas coleções.
- `POST /academic/researchers` aceita `collection_ids`. Sem esse campo, o pesquisador entra na coleção padrão.
- Migration cria a coleção `simcc` como padrão e inclui nela todos os pesquisadores existentes.

Fora do escopo: importação de planilha, filtro por coleção no simcc-back e seleção por intervalo no Hop. Cada um terá a sua change.

## Capabilities

### New Capabilities

- `collections`: catálogo de coleções (criar, listar, consultar, editar, remover), coleção padrão e intervalo de atualização.
- `researcher-collections`: pertencimento de pesquisadores a coleções, com atributos por vínculo, filtro de busca e exposição nas respostas de pesquisador.

### Modified Capabilities

Nenhuma. O projeto ainda não tem specs publicadas.

## Impact

- `src/simcc_admin/models.py`: novos models `Collection` e `ResearcherCollection` no schema `academic`.
- `src/simcc_admin/schemas.py`: schemas de coleção; `ResearcherCreate`, `ResearcherItem` e `FiltersApplied` ganham campos novos (aditivos, sem quebra).
- `src/simcc_admin/routers/academic/`: novo `collections.py`; `researchers.py` ganha filtro, criação com coleções e rotas de vínculo.
- `migrations/versions/`: nova revisão com tabelas, seed de `simcc` e backfill.
- Consumidores (simcc-back, Hop, front do admin) passam a poder ler `academic.collections` e `academic.researcher_collections`, mas nada muda para eles nesta change.
