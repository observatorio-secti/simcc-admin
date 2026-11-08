# Seeds e Dados Anotados do SimCC Admin

Esta pasta contém os dados de carga inicial (seeds) e anotações oficiais de pesquisadores e instituições do ecossistema SimCC. Eles representam a nossa **fonte de verdade** inicial para o banco administrativo.

---

## Estrutura da Pasta

```
storage/seed/researchers/
├── README.md               # Este documento de referência
├── simcc.csv               # Base consolidada de pesquisadores do SimCC (~12.145 linhas)
├── ebmsp.csv               # Lista anotada oficial da EBMSP (552 registros)
├── ufob.csv                # Lista anotada oficial da UFOB (365 registros)
├── ufrb.csv                # Lista anotada oficial da UFRB (911 registros)
├── fapesb.csv              # Pesquisadores Fapesb/Fomento com nomes enriquecidos (32.856 registros)
└── fapesb_sem_nome.txt     # Relação de Lattes IDs do Fapesb sem correspondência de nome (1.317 registros)
```

---

## Regras de Negócio e Diretrizes de Carga

1. **Precedência dos Dados Anotados Oficiais (`researchers/*.csv`):**
   - Os arquivos em `researchers/` trazem listas nominais oficiais homologadas pelas universidades.
   - Em caso de divergência de nomes ou afiliações entre os dados anotados e `simcc.csv`, a informação dos dados anotados tem precedência.
   - Na importação de `simcc.csv`, deve ser utilizado `ON CONFLICT (lattes_id) DO NOTHING` para **preservar os dados oficiais já cadastrados**.

2. **Normalização do Identificador Lattes (`lattes_id`):**
   - O Lattes ID na Plataforma Lattes é composto estritamente por **16 dígitos numéricos**.
   - Alguns arquivos perdem os zeros à esquerda (ex: foram exportados ou manipulados em planilhas como inteiros).
   - **Obrigatório:** Aplicar preenchimento à esquerda: `LPAD(TRIM(lattes_id), 16, '0')` em SQL ou `.zfill(16)` em Python.

3. **Tratamento Especial para a Sigla `EXTERNA`:**
   - A sigla `EXTERNA` **NÃO deve ser cadastrada** na tabela `academic.institutions`.
   - **NÃO devem ser gerados vínculos** em `academic.researcher_institutions` com a sigla `EXTERNA`.
   - Os pesquisadores listados com `EXTERNA` são devidamente inseridos em `academic.researchers` e vinculados à coleção padrão `simcc` em `academic.researcher_collections`, permanecendo sem vínculo institucional até que uma instituição homologada seja associada.

4. **Multi-afiliação Institucional:**
   - Um pesquisador pode legitimamente pertencer a mais de uma instituição (ex: docente da UFRB que também atua na EBMSP).
   - Vínculos múltiplos são permitidos e esperados em `academic.researcher_institutions`, utilizando `(researcher_id, institution_id)` como chave de unicidade.

5. **Vinculação à Coleção Padrão:**
   - Todos os pesquisadores válidos devem possuir vínculo com a coleção padrão `simcc` (`slug = 'simcc'`) em `academic.researcher_collections`.

---

## Instituições Oficiais Suportadas

Atualmente são suportadas as **11 instituições oficiais** da Bahia:

| Sigla | Nome Oficial |
| :--- | :--- |
| **UFBA** | Universidade Federal da Bahia |
| **UNEB** | Universidade do Estado da Bahia |
| **IFBA** | Instituto Federal de Educação, Ciência e Tecnologia da Bahia |
| **UESB** | Universidade Estadual do Sudoeste da Bahia |
| **UFRB** | Universidade Federal do Recôncavo da Bahia |
| **UEFS** | Universidade Estadual de Feira de Santana |
| **UESC** | Universidade Estadual de Santa Cruz |
| **UFSB** | Universidade Federal do Sul da Bahia |
| **EBMSP** | Escola Bahiana de Medicina e Saúde Pública |
| **UFOB** | Universidade Federal do Oeste da Bahia |
| **FIOCRUZ-IGM** | Instituto Gonçalo Moniz - Fiocruz Bahia |

---

## Procedimento de Carga no Banco Administrativo

O processo de carga em banco zerado segue duas fases principais, executadas preferencialmente via tabelas temporárias (`staging`) para alta performance e segurança transacional:

### Fase 1: Carga dos Dados Anotados Oficiais (`researchers/`)

1. Cadastrar as instituições oficiais envolvidas (`EBMSP`, `UFOB`, `UFRB`) em `academic.institutions`.
2. Carregar `ebmsp.csv` (delimitador `;`), `ufob.csv` (delimitador `;`) e `ufrb.csv` (delimitador `,`) em tabelas temporárias.
3. Unificar os registros com `LPAD(TRIM(lattes_id), 16, '0')`.
4. Inserir em `academic.researchers` com `ON CONFLICT (lattes_id) DO NOTHING`.
5. Criar os vínculos em `academic.researcher_institutions` cruzando pelo `acronym`.
6. Vincular todos à coleção `simcc` em `academic.researcher_collections`.

### Fase 2: Carga do Consolidado (`simcc.csv`)

1. Cadastrar as 8 instituições restantes em `academic.institutions` (**sem cadastrar `EXTERNA`**).
2. Carregar `simcc.csv` (delimitador `,`) para tabela temporária de staging.
3. Inserir os novos pesquisadores em `academic.researchers` usando `ON CONFLICT (lattes_id) DO NOTHING` (mantendo os dados da Fase 1 intactos).
4. Inserir os vínculos institucionais em `academic.researcher_institutions` com filtro `WHERE acronym <> 'EXTERNA'`.
5. Garantir que todos os pesquisadores novos estejam vinculados à coleção `simcc` em `academic.researcher_collections`.

### Fase 3: Carga do Fomento Fapesb (`fapesb.csv`)

1. Carregar `fapesb.csv` (delimitador `,`) para tabela temporária de staging.
2. Filtrar apenas os registros que possuem `name` preenchido (os 1.317 registros sem nome listados em `fapesb_sem_nome.txt` permanecem fora até resolução).
3. Inserir os novos pesquisadores em `academic.researchers` com `ON CONFLICT (lattes_id) DO NOTHING` (preservando nomes existentes).
4. **Sem vínculo institucional:** Não criar registros em `academic.researcher_institutions` para os pesquisadores originários exclusivamente da Fapesb.
5. **Vínculo com a coleção `fomento`:** Inserir os 31.539 pesquisadores com nome em `academic.researcher_collections` associados à coleção `fomento` (`slug = 'fomento'`). Pesquisadores já pertencentes à coleção `simcc` mantêm ambos os vínculos ativos simultaneamente.

