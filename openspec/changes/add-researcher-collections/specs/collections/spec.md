# Spec Delta

## Purpose

Mantém o catálogo de coleções: conjuntos nomeados de pesquisadores (Simcc, bolsistas Fapesb, Clubes de Ciência) que outros sistemas usam para decidir quem exibir e com que frequência atualizar.

## ADDED Requirements

### Requirement: Acesso restrito a administradores
As rotas de `/academic/collections` SHALL exigir autenticação e o papel ADMIN, como as demais rotas acadêmicas.

#### Scenario: Requisição sem token
- **WHEN** um cliente sem token chama `GET /academic/collections`
- **THEN** a resposta é 401

#### Scenario: Usuário sem papel ADMIN
- **WHEN** um usuário DEFAULT chama `GET /academic/collections`
- **THEN** a resposta é 403 com `{"detail": "Not enough permissions"}`

### Requirement: Criar coleção
O sistema SHALL criar uma coleção com `slug`, `name`, `description` opcional e `refresh_interval_days` (inteiro ≥ 1, padrão 1). O `slug` MUST ter apenas letras minúsculas, dígitos e hífens, e `slug` e `name` MUST ser únicos.

#### Scenario: Criação válida
- **WHEN** um admin envia `POST /academic/collections` com `{"slug": "fapesb-bolsistas", "name": "Bolsistas Fapesb", "refresh_interval_days": 7}`
- **THEN** a resposta é 201 com `id`, `slug`, `name`, `description`, `refresh_interval_days`, `is_default: false` e `created_at`

#### Scenario: Slug duplicado
- **WHEN** um admin cria uma coleção com um `slug` já existente
- **THEN** a resposta é 409

#### Scenario: Slug inválido
- **WHEN** um admin cria uma coleção com `slug` "Fapesb Bolsistas"
- **THEN** a resposta é 422

#### Scenario: Intervalo inválido
- **WHEN** um admin cria uma coleção com `refresh_interval_days` igual a 0
- **THEN** a resposta é 422

### Requirement: Listar e consultar coleções
O sistema SHALL listar coleções no envelope paginado padrão, com busca `q` por nome ou slug e ordenação por `name`, `slug` ou `created_at`. Cada item MUST trazer `researcher_count`. O sistema SHALL também retornar uma coleção pelo `id`.

#### Scenario: Listagem com contagem
- **WHEN** a coleção `fapesb-bolsistas` tem 3 pesquisadores e um admin chama `GET /academic/collections?q=fapesb`
- **THEN** a resposta traz essa coleção com `researcher_count: 3` e `pagination.total_items: 1`

#### Scenario: Coleção inexistente
- **WHEN** um admin chama `GET /academic/collections/{id}` com um id desconhecido
- **THEN** a resposta é 404

### Requirement: Slug imutável
O sistema SHALL permitir editar `name`, `description` e `refresh_interval_days` de uma coleção, mas MUST NOT permitir alterar o `slug`, porque outros sistemas o referenciam.

#### Scenario: Edição de intervalo
- **WHEN** um admin envia `PUT /academic/collections/{id}` com `refresh_interval_days: 7`
- **THEN** a resposta é 200 e a coleção passa a ter intervalo 7

#### Scenario: Tentativa de mudar slug
- **WHEN** o corpo do `PUT` contém um `slug` diferente do atual
- **THEN** a resposta é 422 e o slug não muda

### Requirement: Coleção padrão única
O sistema SHALL ter no máximo uma coleção marcada como padrão. Marcar outra coleção como padrão MUST desmarcar a anterior.

#### Scenario: Troca de padrão
- **WHEN** `simcc` é a padrão e um admin envia `PUT` em `clubes-ciencia` com `is_default: true`
- **THEN** `clubes-ciencia` passa a ser a padrão e `simcc` passa a ter `is_default: false`

### Requirement: Remoção protegida
O sistema SHALL remover uma coleção somente quando ela não tem pesquisadores e não é a padrão.

#### Scenario: Coleção com membros
- **WHEN** um admin chama `DELETE /academic/collections/{id}` para uma coleção com pesquisadores
- **THEN** a resposta é 409 e nada é removido

#### Scenario: Coleção padrão
- **WHEN** um admin tenta remover a coleção padrão
- **THEN** a resposta é 409

#### Scenario: Coleção vazia
- **WHEN** um admin remove uma coleção vazia que não é a padrão
- **THEN** a resposta é 200 com `{"message": "Collection deleted"}`

### Requirement: Coleção Simcc inicial
A migração SHALL criar a coleção `simcc` (padrão, intervalo de 1 dia) e incluir nela todos os pesquisadores já cadastrados.

#### Scenario: Banco com pesquisadores existentes
- **WHEN** a migração roda em um banco com N pesquisadores
- **THEN** existe a coleção `simcc` com `is_default: true` e N vínculos
