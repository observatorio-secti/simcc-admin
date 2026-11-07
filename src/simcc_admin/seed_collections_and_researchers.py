import csv
import logging
from pathlib import Path
from uuid import uuid4

import psycopg
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from simcc_admin.models import (
    Collection,
    Institution,
    Researcher,
    ResearcherCollection,
)
from simcc_admin.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("seed_collections_and_researchers")

INSTITUTION_NAMES = {
    "UFBA": "Universidade Federal da Bahia",
    "UNEB": "Universidade do Estado da Bahia",
    "IFBA": "Instituto Federal de Educação, Ciência e Tecnologia da Bahia",
    "UESB": "Universidade Estadual do Sudoeste da Bahia",
    "UFRB": "Universidade Federal do Recôncavo da Bahia",
    "UEFS": "Universidade Estadual de Feira de Santana",
    "UESC": "Universidade Estadual de Santa Cruz",
    "UFSB": "Universidade Federal do Sul da Bahia",
    "EXTERNA": "Outras Instituições / Vínculo Externo",
    "EBMSP": "Escola Bahiana de Medicina e Saúde Pública",
    "UFOB": "Universidade Federal do Oeste da Bahia",
    "FIOCRUZ-IGM": "Instituto Gonçalo Moniz - Fiocruz Bahia",
}


def clean_dsn(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def run_seed(
    csv_path: Path,
    fomento_db_url: str = "postgresql://postgres:postgres@localhost:5432/fomento",
) -> None:
    settings = Settings()
    admin_dsn = clean_dsn(settings.ADMIN_DATABASE_URL)
    fomento_dsn = clean_dsn(fomento_db_url)

    logger.info("Conectando ao banco administrativo: %s", admin_dsn)
    engine = create_engine(settings.ADMIN_DATABASE_URL)

    with Session(engine) as session:
        # 1. Garante a coleção 'simcc' e 'fomento'
        logger.info("Criando ou verificando coleções 'simcc' e 'fomento'...")
        simcc_col = session.scalar(select(Collection).where(Collection.slug == "simcc"))
        if not simcc_col:
            simcc_col = Collection(
                slug="simcc",
                name="SimCC",
                description="Coleção principal de pesquisadores do SimCC",
                refresh_interval_days=1,
                is_default=True,
            )
            session.add(simcc_col)
            session.flush()
        else:
            simcc_col.is_default = True
            simcc_col.refresh_interval_days = 1

        fomento_col = session.scalar(
            select(Collection).where(Collection.slug == "fomento")
        )
        if not fomento_col:
            fomento_col = Collection(
                slug="fomento",
                name="Fapesb Fomento",
                description="Coleção de bolsistas e pesquisadores do Fomento Fapesb",
                refresh_interval_days=30,
                is_default=False,
            )
            session.add(fomento_col)
            session.flush()
        else:
            fomento_col.refresh_interval_days = 30

        session.commit()
        logger.info(
            "Coleções prontas: simcc (%s, refresh=%dd), fomento (%s, refresh=%dd)",
            simcc_col.id,
            simcc_col.refresh_interval_days,
            fomento_col.id,
            fomento_col.refresh_interval_days,
        )

        # 2. Garante as 12 instituições
        logger.info("Criando ou verificando as 12 instituições...")
        inst_map: dict[str, Institution] = {}
        for acronym, name in INSTITUTION_NAMES.items():
            inst = session.scalar(
                select(Institution).where(
                    (Institution.acronym == acronym) | (Institution.name == name)
                )
            )
            if not inst:
                inst = Institution(name=name, acronym=acronym)
                session.add(inst)
                session.flush()
            inst_map[acronym] = inst

        session.commit()
        logger.info("%d instituições prontas no academic.institutions.", len(inst_map))

        # 3. Lê pesquisadores.csv e faz a carga da coleção simcc
        if not csv_path.is_file():
            raise FileNotFoundError(f"Arquivo CSV não encontrado: {csv_path}")

        logger.info("Lendo %s...", csv_path)
        csv_researchers = []
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                lattes_id = (row.get("lattes_id") or "").strip()
                acronym = (row.get("acronym") or "").strip()
                if lattes_id:
                    csv_researchers.append((name, lattes_id, acronym))

        logger.info(
            "Total de linhas lidas do CSV: %d. Populando coleção 'simcc'...",
            len(csv_researchers),
        )

        # Mapa em memória de pesquisadores existentes por lattes_id
        existing_res_rows = session.execute(
            select(Researcher.id, Researcher.lattes_id)
        ).all()
        res_by_lattes = {row[1]: row[0] for row in existing_res_rows}

        new_researchers = []
        for name, lattes_id, acronym in csv_researchers:
            if lattes_id not in res_by_lattes:
                res_id = uuid4()
                res_by_lattes[lattes_id] = res_id
                new_researchers.append(
                    {
                        "id": res_id,
                        "name": name,
                        "lattes_id": lattes_id,
                    }
                )

        if new_researchers:
            session.execute(
                text(
                    """
                    INSERT INTO academic.researchers (id, name, lattes_id, created_at)
                    VALUES (:id, :name, :lattes_id, now())
                    ON CONFLICT (lattes_id) DO UPDATE SET name = EXCLUDED.name;
                    """
                ),
                new_researchers,
            )
            session.commit()
            logger.info("Inseridos/atualizados %d pesquisadores do CSV.", len(new_researchers))

        # Vínculos institucionais e vínculos com coleção simcc
        affil_rows = []
        col_rows_simcc = []
        for name, lattes_id, acronym in csv_researchers:
            r_id = res_by_lattes[lattes_id]
            if acronym in inst_map:
                affil_rows.append(
                    {
                        "id": uuid4(),
                        "researcher_id": r_id,
                        "institution_id": inst_map[acronym].id,
                    }
                )
            col_rows_simcc.append(
                {
                    "id": uuid4(),
                    "researcher_id": r_id,
                    "collection_id": simcc_col.id,
                }
            )

        if affil_rows:
            session.execute(
                text(
                    """
                    INSERT INTO academic.researcher_institutions (id, researcher_id, institution_id, created_at)
                    VALUES (:id, :researcher_id, :institution_id, now())
                    ON CONFLICT (researcher_id, institution_id) DO NOTHING;
                    """
                ),
                affil_rows,
            )
            session.commit()
            logger.info("%d vínculos em academic.researcher_institutions inseridos.", len(affil_rows))

        if col_rows_simcc:
            session.execute(
                text(
                    """
                    INSERT INTO academic.researcher_collections (id, researcher_id, collection_id, attributes, created_at)
                    VALUES (:id, :researcher_id, :collection_id, '{}'::jsonb, now())
                    ON CONFLICT (researcher_id, collection_id) DO NOTHING;
                    """
                ),
                col_rows_simcc,
            )
            session.commit()
            logger.info("%d vínculos na coleção 'simcc' inseridos.", len(col_rows_simcc))

        # 4. Conecta no banco fomento e extrai pesquisadores com Lattes
        logger.info("Consultando pesquisadores com Lattes no banco fomento: %s", fomento_dsn)
        with psycopg.connect(fomento_dsn) as f_conn, f_conn.cursor() as cur:
            cur.execute(
                """
                    SELECT DISTINCT trim(lattes)
                    FROM public.pesquisadores
                    WHERE lattes IS NOT NULL AND trim(lattes) <> '';
                    """
            )
            fomento_lattes_ids = [row[0] for row in cur.fetchall() if row[0]]

        logger.info("Total de Lattes únicos encontrados no Fomento: %d", len(fomento_lattes_ids))

        new_fomento_researchers = []
        col_rows_fomento = []

        for lattes_id in fomento_lattes_ids:
            if lattes_id not in res_by_lattes:
                r_id = uuid4()
                res_by_lattes[lattes_id] = r_id
                new_fomento_researchers.append(
                    {
                        "id": r_id,
                        "name": f"Pesquisador {lattes_id}",
                        "lattes_id": lattes_id,
                    }
                )
            else:
                r_id = res_by_lattes[lattes_id]

            col_rows_fomento.append(
                {
                    "id": uuid4(),
                    "researcher_id": r_id,
                    "collection_id": fomento_col.id,
                }
            )

        if new_fomento_researchers:
            session.execute(
                text(
                    """
                    INSERT INTO academic.researchers (id, name, lattes_id, created_at)
                    VALUES (:id, :name, :lattes_id, now())
                    ON CONFLICT (lattes_id) DO NOTHING;
                    """
                ),
                new_fomento_researchers,
            )
            session.commit()
            logger.info(
                "Inseridos %d pesquisadores exclusivos do Fomento.",
                len(new_fomento_researchers),
            )

        if col_rows_fomento:
            # Inserção em lotes de 5000 para performance
            batch_size = 5000
            for i in range(0, len(col_rows_fomento), batch_size):
                batch = col_rows_fomento[i : i + batch_size]
                session.execute(
                    text(
                        """
                        INSERT INTO academic.researcher_collections (id, researcher_id, collection_id, attributes, created_at)
                        VALUES (:id, :researcher_id, :collection_id, '{}'::jsonb, now())
                        ON CONFLICT (researcher_id, collection_id) DO NOTHING;
                        """
                    ),
                    batch,
                )
                session.commit()
            logger.info(
                "%d vínculos na coleção 'fomento' inseridos/garantidos.",
                len(col_rows_fomento),
            )

        total_final = session.scalar(select(func.count()).select_from(Researcher))
        simcc_count = session.scalar(
            select(func.count()).select_from(ResearcherCollection).where(
                ResearcherCollection.collection_id == simcc_col.id
            )
        )
        fomento_count = session.scalar(
            select(func.count()).select_from(ResearcherCollection).where(
                ResearcherCollection.collection_id == fomento_col.id
            )
        )
        logger.info(
            "=== CARGA CONCLUÍDA COM SUCESSO ===\n"
            "Total de pesquisadores únicos no banco: %d\n"
            "Vínculos na coleção 'simcc': %d\n"
            "Vínculos na coleção 'fomento': %d",
            total_final or 0,
            simcc_count or 0,
            fomento_count or 0,
        )


if __name__ == "__main__":
    csv_file = Path("pesquisadores.csv")
    if not csv_file.exists():
        csv_file = Path("../../pesquisadores.csv")
    if not csv_file.exists():
        csv_file = Path("/home/gls/Travail/Observatorio/pesquisadores.csv")
    run_seed(csv_file)
