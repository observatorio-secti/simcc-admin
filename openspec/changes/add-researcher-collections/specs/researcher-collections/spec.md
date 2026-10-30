# Spec Delta

## Purpose

Define a que coleções cada pesquisador pertence, com dados próprios por vínculo, para que cada sistema consumidor exiba apenas os pesquisadores da sua coleção sem duplicar pessoas.

## ADDED Requirements

### Requirement: Pertencimento N:N sem duplicar pesquisador
Um pesquisador SHALL poder pertencer a várias coleções, e o par pesquisador/coleção MUST ser único. O pesquisador continua sendo um único registro, identificado pelo `lattes_id`.

#### Scenario: Mesma pessoa em duas coleções
- **WHEN** um pesquisador de `simcc` é adicionado a `fapesb-bolsistas`
- **THEN** ele aparece nas duas coleções e continua existindo um único pesquisador com aquele `lattes_id`

### Requirement: Adicionar pesquisador a uma coleção
O sistema SHALL adicionar um pesquisador a uma coleção via `POST /academic/researchers/{researcher_id}/collections/{collection_id}`, com corpo opcional `{"attributes": {...}}` (objeto JSON, padrão `{}`).

#### Scenario: Adição com atributos
- **WHEN** um admin adiciona o pesquisador a `fapesb-bolsistas` com `{"attributes": {"modalidade": "BOL0001/2025"}}`
- **THEN** a resposta é 201 com `collection` (id, slug, name), `attributes` e `created_at`

#### Scenario: Vínculo já existente
- **WHEN** o pesquisador já pertence à coleção
- **THEN** a resposta é 409

#### Scenario: Pesquisador ou coleção inexistente
- **WHEN** o `researcher_id` ou o `collection_id` não existe
- **THEN** a resposta é 404 indicando qual dos dois não foi encontrado

### Requirement: Atualizar atributos do vínculo
O sistema SHALL substituir os `attributes` de um vínculo existente via `PUT /academic/researchers/{researcher_id}/collections/{collection_id}`.

#### Scenario: Substituição de atributos
- **WHEN** um admin envia `PUT` com `{"attributes": {"vigencia_fim": "2026-12-31"}}`
- **THEN** a resposta é 200 e o vínculo passa a ter exatamente esses atributos

#### Scenario: Vínculo inexistente
- **WHEN** o pesquisador não pertence à coleção
- **THEN** a resposta é 404

### Requirement: Remover pesquisador de uma coleção
O sistema SHALL remover o vínculo via `DELETE /academic/researchers/{researcher_id}/collections/{collection_id}` sem apagar o pesquisador, seus vínculos institucionais nem suas outras coleções.

#### Scenario: Remoção de uma coleção
- **WHEN** um pesquisador de `simcc` e `fapesb-bolsistas` é removido de `fapesb-bolsistas`
- **THEN** a resposta é 200 com `{"message": "Collection membership removed"}` e ele continua em `simcc`

#### Scenario: Vínculo inexistente
- **WHEN** o pesquisador não pertence à coleção
- **THEN** a resposta é 404

### Requirement: Coleções na criação de pesquisador
`POST /academic/researchers` SHALL aceitar `collection_ids`. Quando o campo é omitido ou vazio, o pesquisador MUST entrar na coleção padrão.

#### Scenario: Criação sem coleções informadas
- **WHEN** um admin cria um pesquisador sem `collection_ids` e `simcc` é a padrão
- **THEN** o pesquisador criado pertence apenas a `simcc`

#### Scenario: Criação com coleções informadas
- **WHEN** um admin cria um pesquisador com `collection_ids` contendo apenas `fapesb-bolsistas`
- **THEN** o pesquisador pertence apenas a `fapesb-bolsistas`

#### Scenario: Coleção informada inexistente
- **WHEN** `collection_ids` contém um id desconhecido
- **THEN** a resposta é 422 e o pesquisador não é criado

#### Scenario: Sem coleção padrão configurada
- **WHEN** nenhuma coleção é padrão e `collection_ids` é omitido
- **THEN** a resposta é 422 e o pesquisador não é criado

### Requirement: Filtro de busca por coleção
`GET /academic/researchers` SHALL aceitar `collection_id` e retornar apenas pesquisadores daquela coleção. O filtro MUST combinar com `q` e `institution_id`, e `filters_applied` MUST ecoar o `collection_id`.

#### Scenario: Busca restrita a uma coleção
- **WHEN** existem 2 pesquisadores em `simcc` e 1 apenas em `fapesb-bolsistas`, e um admin busca com `collection_id` de `simcc`
- **THEN** a resposta traz os 2 de `simcc` e `pagination.total_items: 2`

#### Scenario: Pesquisador em várias coleções aparece uma vez
- **WHEN** um pesquisador está em `simcc` e em `fapesb-bolsistas` e a busca é feita sem filtro
- **THEN** ele aparece uma única vez e é contado uma vez em `total_items`

### Requirement: Coleções nas respostas de pesquisador
As respostas de busca e de detalhe de pesquisador SHALL incluir `collections`: uma lista com `collection` (id, slug, name), `attributes` e `created_at`, ordenada pelo nome da coleção.

#### Scenario: Detalhe de pesquisador
- **WHEN** um admin consulta `GET /academic/researchers/{id}` de um pesquisador em `simcc` e `fapesb-bolsistas`
- **THEN** a resposta traz `collections` com as duas entradas, além de `affiliations`
