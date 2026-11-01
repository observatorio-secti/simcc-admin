"""Script para sincronizar pesquisadores das listas oficiais (UFOB, EBMSP, UFRB).

Este script lê os CSVs em Simcc/simcc-back/storage/researchers/ (UFOB, EBMSP, UFRB),
garante que todos os pesquisadores existam em academic.researchers (aplicando zfill(16)),
associa-os à coleção 'simcc', vincula-os às respectivas instituições em
academic.researcher_institutions, e substitui vínculos com a instituição 'EXTERNA'
pela instituição oficial da lista.
"""

import csv
import logging
import sys
from pathlib import Path
from uuid import uuid4

import psycopg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("import_institution_csvs")

DB_URL = "postgresql://db_user:db_password@localhost:5432/db"

CSV_CONFIGS = [
    {
        "institution": "UFOB",
        "path": Path(
            "/home/gls/Travail/Observatorio/Simcc/simcc-back/storage/researchers/ufob.csv"
        ),
        "delimiter": ";",
        "name_col": "NOME SERVIDOR",
        "lattes_col": "lattes_id",
    },
    {
        "institution": "EBMSP",
        "path": Path(
            "/home/gls/Travail/Observatorio/Simcc/simcc-back/storage/researchers/ebmsp.csv"
        ),
        "delimiter": ";",
        "name_col": "NOME_DOCENTE",
        "lattes_col": "lattes_id",
    },
    {
        "institution": "UFRB",
        "path": Path(
            "/home/gls/Travail/Observatorio/Simcc/simcc-back/storage/researchers/ufrb.csv"
        ),
        "delimiter": ",",
        "name_col": "name",
        "lattes_col": "lattes_id",
    },
]


def run_import(db_url: str = DB_URL) -> None:
    # 1. Carrega dados dos 3 CSVs
    logger.info("Lendo arquivos CSV das instituições...")
    researchers_data = {}  # lattes_id -> {"name": str, "target_institutions": set[str]}

    for cfg in CSV_CONFIGS:
        csv_path = cfg["path"]
        inst_acronym = cfg["institution"]
        if not csv_path.is_file():
            raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")

        loaded_count = 0
        with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=cfg["delimiter"])
            for row in reader:
                raw_lattes = (row.get(cfg["lattes_col"]) or "").strip()
                name = (row.get(cfg["name_col"]) or "").strip()
                if not raw_lattes:
                    continue

                lattes_id = raw_lattes.zfill(16)
                if lattes_id not in researchers_data:
                    researchers_data[lattes_id] = {
                        "name": name,
                        "target_institutions": set(),
                    }
                researchers_data[lattes_id]["target_institutions"].add(inst_acronym)
                if name and (
                    not researchers_data[lattes_id]["name"]
                    or researchers_data[lattes_id]["name"].startswith("Pesquisador")
                ):
                    researchers_data[lattes_id]["name"] = name
                loaded_count += 1

        logger.info(
            "Carregados %d registros da instituição %s (%s)",
            loaded_count,
            inst_acronym,
            csv_path.name,
        )

    logger.info("Total de pesquisadores únicos consolidados: %d", len(researchers_data))

    # 2. Conectar ao banco e executar alterações dentro de transação
    logger.info("Conectando ao banco de dados: %s", db_url)
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        # 2.1 Buscar instituições
        cur.execute("SELECT id, acronym, name FROM academic.institutions;")
        institutions = {row[1]: row[0] for row in cur.fetchall()}
        for req_inst in ["UFOB", "EBMSP", "UFRB", "EXTERNA"]:
            if req_inst not in institutions:
                raise RuntimeError(
                    f"Instituição obrigatória '{req_inst}' não encontrada no banco."
                )

        externa_id = institutions["EXTERNA"]

        # 2.2 Buscar coleção 'simcc'
        cur.execute("SELECT id FROM academic.collections WHERE slug = 'simcc';")
        simcc_col_row = cur.fetchone()
        if not simcc_col_row:
            raise RuntimeError(
                "Coleção padrão 'simcc' não encontrada em academic.collections."
            )
        simcc_col_id = simcc_col_row[0]

        # 2.3 Mapear pesquisadores existentes no banco
        lattes_list = list(researchers_data.keys())
        cur.execute(
            """
            SELECT id, lattes_id, name
            FROM academic.researchers
            WHERE lattes_id = ANY(%s);
            """,
            (lattes_list,),
        )
        existing_researchers = {
            row[1]: {"id": row[0], "name": row[2]} for row in cur.fetchall()
        }
        logger.info(
            "Pesquisadores já presentes no banco: %d", len(existing_researchers)
        )

        # 2.4 Inserir novos pesquisadores
        new_researchers = []
        for lattes_id, info in researchers_data.items():
            if lattes_id not in existing_researchers:
                new_id = uuid4()
                existing_researchers[lattes_id] = {
                    "id": new_id,
                    "name": info["name"],
                }
                new_researchers.append((new_id, info["name"], lattes_id))

        if new_researchers:
            logger.info(
                "Inserindo %d novos pesquisadores em academic.researchers...",
                len(new_researchers),
            )
            cur.executemany(
                """
                INSERT INTO academic.researchers (id, name, lattes_id, created_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (lattes_id) DO UPDATE SET name = EXCLUDED.name;
                """,
                new_researchers,
            )
        else:
            logger.info("Nenhum novo pesquisador precisa ser inserido.")

        # 2.5 Atualizar nomes de placeholders (ex: 'Pesquisador <lattes_id>')
        updates_name = []
        for lattes_id, info in researchers_data.items():
            curr_name = existing_researchers[lattes_id]["name"] or ""
            if curr_name.startswith("Pesquisador ") and info["name"]:
                updates_name.append(
                    (info["name"], existing_researchers[lattes_id]["id"])
                )

        if updates_name:
            logger.info(
                "Atualizando nomes de %d pesquisadores com nomes oficiais...",
                len(updates_name),
            )
            cur.executemany(
                """
                UPDATE academic.researchers
                SET name = %s
                WHERE id = %s;
                """,
                updates_name,
            )

        # 2.6 Tratar vínculos com 'EXTERNA' (substituir por instituição alvo)
        all_researcher_ids = [v["id"] for v in existing_researchers.values()]
        cur.execute(
            """
            SELECT researcher_id
            FROM academic.researcher_institutions
            WHERE researcher_id = ANY(%s) AND institution_id = %s;
            """,
            (all_researcher_ids, externa_id),
        )
        externa_researcher_ids = [row[0] for row in cur.fetchall()]

        if externa_researcher_ids:
            logger.info(
                "Removendo vínculo 'EXTERNA' de %d pesquisadores para associar à instituição oficial...",
                len(externa_researcher_ids),
            )
            cur.execute(
                """
                DELETE FROM academic.researcher_institutions
                WHERE researcher_id = ANY(%s) AND institution_id = %s;
                """,
                (externa_researcher_ids, externa_id),
            )

        # 2.7 Inserir vínculos com as instituições alvo (UFOB, EBMSP, UFRB)
        affiliation_rows = []
        for lattes_id, info in researchers_data.items():
            r_id = existing_researchers[lattes_id]["id"]
            for target_acronym in info["target_institutions"]:
                target_inst_id = institutions[target_acronym]
                affiliation_rows.append((uuid4(), r_id, target_inst_id))

        logger.info(
            "Garantindo %d vínculos institucionais oficiais...",
            len(affiliation_rows),
        )
        cur.executemany(
            """
            INSERT INTO academic.researcher_institutions (id, researcher_id, institution_id, created_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (researcher_id, institution_id) DO NOTHING;
            """,
            affiliation_rows,
        )

        # 2.8 Garantir que todos estejam na coleção 'simcc'
        collection_rows = []
        for lattes_id in researchers_data:
            r_id = existing_researchers[lattes_id]["id"]
            collection_rows.append((uuid4(), r_id, simcc_col_id))

        logger.info(
            "Garantindo %d vínculos na coleção 'simcc'...",
            len(collection_rows),
        )
        cur.executemany(
            """
            INSERT INTO academic.researcher_collections (id, researcher_id, collection_id, attributes, created_at)
            VALUES (%s, %s, %s, '{}'::jsonb, now())
            ON CONFLICT (researcher_id, collection_id) DO NOTHING;
            """,
            collection_rows,
        )

        # 2.9 Contagens finais de verificação
        cur.execute("SELECT count(*) FROM academic.researchers;")
        total_researchers = cur.fetchone()[0]

        cur.execute(
            """
            SELECT i.acronym, count(DISTINCT ri.researcher_id)
            FROM academic.researcher_institutions ri
            JOIN academic.institutions i ON i.id = ri.institution_id
            WHERE i.acronym IN ('UFOB', 'EBMSP', 'UFRB', 'EXTERNA')
            GROUP BY i.acronym
            ORDER BY i.acronym;
            """
        )
        inst_counts = dict(cur.fetchall())

        cur.execute(
            """
            SELECT count(DISTINCT rc.researcher_id)
            FROM academic.researcher_collections rc
            WHERE rc.collection_id = %s;
            """,
            (simcc_col_id,),
        )
        simcc_collection_total = cur.fetchone()[0]

        conn.commit()

        logger.info("=== SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO ===")
        logger.info(
            "Total de pesquisadores em academic.researchers: %d",
            total_researchers,
        )
        logger.info("Pesquisadores por instituição:")
        for acr in ["UFOB", "EBMSP", "UFRB", "EXTERNA"]:
            logger.info("  * %s: %d", acr, inst_counts.get(acr, 0))
        logger.info(
            "Total de pesquisadores na coleção 'simcc': %d",
            simcc_collection_total,
        )


if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DB_URL
    run_import(db)
