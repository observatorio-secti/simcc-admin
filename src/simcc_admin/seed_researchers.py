"""Script simples e idempotente para inserir pesquisadores a partir dos CSVs de seed."""

from __future__ import annotations

import argparse
import csv
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import psycopg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("seed_researchers")

DEFAULT_SEED_DIR = (
    Path(__file__).resolve().parents[2] / "storage" / "seed" / "researchers"
)
DEFAULT_DB_URL = "postgresql://db_user:db_password@localhost:5432/db"

INSTITUTION_NAMES: dict[str, str] = {
    "UFBA": "Universidade Federal da Bahia",
    "UNEB": "Universidade do Estado da Bahia",
    "IFBA": "Instituto Federal de Educação, Ciência e Tecnologia da Bahia",
    "UESB": "Universidade Estadual do Sudoeste da Bahia",
    "UFRB": "Universidade Federal do Recôncavo da Bahia",
    "UEFS": "Universidade Estadual de Feira de Santana",
    "UESC": "Universidade Estadual de Santa Cruz",
    "UFSB": "Universidade Federal do Sul da Bahia",
    "EBMSP": "Escola Bahiana de Medicina e Saúde Pública",
    "UFOB": "Universidade Federal do Oeste da Bahia",
    "FIOCRUZ-IGM": "Instituto Gonçalo Moniz - Fiocruz Bahia",
    "CIMATEC": "Centro Universitário SENAI CIMATEC",
}

OFFICIAL_INSTITUTION_CSVS = [
    {
        "filename": "ebmsp.csv",
        "institution": "EBMSP",
        "delimiter": ";",
        "name_col": "NOME_DOCENTE",
        "lattes_col": "lattes_id",
    },
    {
        "filename": "ufob.csv",
        "institution": "UFOB",
        "delimiter": ";",
        "name_col": "NOME SERVIDOR",
        "lattes_col": "lattes_id",
    },
    {
        "filename": "ufrb.csv",
        "institution": "UFRB",
        "delimiter": ",",
        "name_col": "name",
        "lattes_col": "lattes_id",
    },
    {
        "filename": "cimatec.csv",
        "institution": "CIMATEC",
        "delimiter": ",",
        "name_col": "Nome completo",
        "lattes_col": "Identificador Lattes",
    },
]


@dataclass
class ResearcherEntry:
    name: str
    institutions: set[str] = field(default_factory=set)
    collections: set[str] = field(default_factory=set)


def clean_dsn(url: str) -> str:
    """Converte URLs SQLAlchemy (psycopg/asyncpg) para DSN padrão do psycopg."""
    for prefix in ("postgresql+psycopg://", "postgresql+asyncpg://"):
        if url.startswith(prefix):
            return url.replace(prefix, "postgresql://", 1)
    return url


def resolve_db_url(cli_db_url: str | None = None) -> str:
    """Resolve a URL do banco a partir de CLI, ambiente, .env ou padrão."""
    if cli_db_url:
        return clean_dsn(cli_db_url)

    env_url = os.environ.get("ADMIN_DATABASE_URL")
    if env_url:
        return clean_dsn(env_url)

    try:
        from pydantic import ValidationError
        from simcc_admin.settings import Settings

        return clean_dsn(Settings().ADMIN_DATABASE_URL)
    except (ImportError, OSError, ValidationError):
        return DEFAULT_DB_URL


def _add_entry(
    entries: dict[str, ResearcherEntry],
    raw_lattes: str,
    raw_name: str,
    collection_slug: str,
    institution_acronym: str | None = None,
) -> None:
    lattes_clean = raw_lattes.strip()
    name_clean = raw_name.strip()
    if not lattes_clean or not name_clean:
        return

    lattes_id = lattes_clean.zfill(16)
    entry = entries.get(lattes_id)
    if entry is None:
        entry = ResearcherEntry(name=name_clean)
        entries[lattes_id] = entry

    entry.collections.add(collection_slug)
    if institution_acronym:
        acronym = institution_acronym.strip().upper()
        if acronym and acronym != "EXTERNA":
            entry.institutions.add(acronym)


def load_seed_csvs(seed_dir: Path) -> dict[str, ResearcherEntry]:
    """Lê todos os CSVs da pasta de seed respeitando a precedência dos oficiais."""
    entries: dict[str, ResearcherEntry] = {}

    # 1. Listas oficiais por instituição (têm precedência de nome)
    for cfg in OFFICIAL_INSTITUTION_CSVS:
        path = seed_dir / cfg["filename"]
        if not path.is_file():
            logger.warning("Arquivo não encontrado, pulando: %s", path)
            continue

        count = 0
        with path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f, delimiter=cfg["delimiter"])
            for row in reader:
                _add_entry(
                    entries,
                    row.get(cfg["lattes_col"]) or "",
                    row.get(cfg["name_col"]) or "",
                    collection_slug="simcc",
                    institution_acronym=cfg["institution"],
                )
                count += 1
        logger.info("Lido %s: %d linhas.", cfg["filename"], count)

    # 2. Consolidado simcc.csv (não cria vínculo institucional para EXTERNA)
    simcc_path = seed_dir / "simcc.csv"
    if simcc_path.is_file():
        count = 0
        with simcc_path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f, delimiter=",")
            for row in reader:
                _add_entry(
                    entries,
                    row.get("lattes_id") or "",
                    row.get("name") or "",
                    collection_slug="simcc",
                    institution_acronym=row.get("acronym") or "",
                )
                count += 1
        logger.info("Lido simcc.csv: %d linhas.", count)

    # 3. Fomento Fapesb (apenas registros com nome preenchido, sem vínculo institucional)
    fapesb_path = seed_dir / "fapesb.csv"
    if fapesb_path.is_file():
        count = 0
        with fapesb_path.open(encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f, delimiter=",")
            for row in reader:
                _add_entry(
                    entries,
                    row.get("lattes_id") or "",
                    row.get("name") or "",
                    collection_slug="fomento",
                    institution_acronym=None,
                )
                count += 1
        logger.info("Lido fapesb.csv: %d linhas.", count)

    logger.info("Total de pesquisadores únicos consolidados: %d", len(entries))
    return entries


def _ensure_collections(cur: psycopg.Cursor) -> dict[str, UUID]:
    collections_spec = [
        ("simcc", "SimCC", "Coleção principal de pesquisadores do SimCC", 1, True),
        (
            "fomento",
            "Fapesb Fomento",
            "Coleção de bolsistas e pesquisadores do Fomento Fapesb",
            30,
            False,
        ),
    ]
    for slug, name, description, refresh_days, is_default in collections_spec:
        cur.execute(
            """
            INSERT INTO academic.collections
                (id, slug, name, description, refresh_interval_days, is_default, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (slug) DO NOTHING;
            """,
            (uuid4(), slug, name, description, refresh_days, is_default),
        )

    cur.execute(
        "SELECT slug, id FROM academic.collections WHERE slug IN ('simcc', 'fomento');"
    )
    return {slug: col_id for slug, col_id in cur.fetchall()}


def _ensure_institutions(
    cur: psycopg.Cursor, needed_acronyms: set[str]
) -> dict[str, UUID]:
    cur.execute("SELECT acronym, id FROM academic.institutions;")
    existing = {acronym: inst_id for acronym, inst_id in cur.fetchall()}

    missing = sorted(
        acronym
        for acronym in needed_acronyms
        if acronym != "EXTERNA" and acronym not in existing
    )
    if missing:
        for acronym in missing:
            name = INSTITUTION_NAMES.get(acronym, acronym)
            cur.execute(
                """
                INSERT INTO academic.institutions (id, name, acronym, created_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT DO NOTHING;
                """,
                (uuid4(), name, acronym),
            )
        cur.execute("SELECT acronym, id FROM academic.institutions;")
        existing = {acronym: inst_id for acronym, inst_id in cur.fetchall()}

    return existing


def run_seed(db_url: str, seed_dir: Path = DEFAULT_SEED_DIR) -> None:
    """Executa a carga dos CSVs de seed no banco administrativo."""
    if not seed_dir.is_dir():
        raise FileNotFoundError(f"Diretório de seed não encontrado: {seed_dir}")

    entries = load_seed_csvs(seed_dir)
    if not entries:
        logger.warning("Nenhum registro válido encontrado nos CSVs.")
        return

    needed_institutions = {
        inst for entry in entries.values() for inst in entry.institutions
    }
    needed_institutions.update(INSTITUTION_NAMES.keys())

    logger.info("Conectando ao banco: %s", db_url)
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        collection_ids = _ensure_collections(cur)
        institution_ids = _ensure_institutions(cur, needed_institutions)

        # 1. Inserir pesquisadores novos (skipa os que já existem pelo lattes_id)
        researcher_rows = [
            (uuid4(), entry.name, lattes_id) for lattes_id, entry in entries.items()
        ]
        cur.executemany(
            """
            INSERT INTO academic.researchers (id, name, lattes_id, created_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (lattes_id) DO NOTHING;
            """,
            researcher_rows,
        )

        # 2. Mapear IDs reais de todos os pesquisadores (novos e já existentes)
        cur.execute(
            "SELECT lattes_id, id FROM academic.researchers WHERE lattes_id = ANY(%s);",
            (list(entries.keys()),),
        )
        researcher_id_by_lattes = {
            lattes_id: r_id for lattes_id, r_id in cur.fetchall()
        }

        # 3. Inserir vínculos em academic.researcher_institutions (sem EXTERNA)
        inst_links = []
        col_links = []
        for lattes_id, entry in entries.items():
            r_id = researcher_id_by_lattes[lattes_id]
            for acronym in entry.institutions:
                inst_id = institution_ids.get(acronym)
                if inst_id:
                    inst_links.append((uuid4(), r_id, inst_id))
            for slug in entry.collections:
                col_id = collection_ids.get(slug)
                if col_id:
                    col_links.append((uuid4(), r_id, col_id))

        if inst_links:
            cur.executemany(
                """
                INSERT INTO academic.researcher_institutions
                    (id, researcher_id, institution_id, created_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (researcher_id, institution_id) DO NOTHING;
                """,
                inst_links,
            )

        if col_links:
            cur.executemany(
                """
                INSERT INTO academic.researcher_collections
                    (id, researcher_id, collection_id, attributes, created_at)
                VALUES (%s, %s, %s, '{}'::jsonb, now())
                ON CONFLICT (researcher_id, collection_id) DO NOTHING;
                """,
                col_links,
            )

        cur.execute("SELECT count(*) FROM academic.researchers;")
        total_researchers = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM academic.researcher_institutions;")
        total_inst_links = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM academic.researcher_collections;")
        total_col_links = cur.fetchone()[0]

        conn.commit()

    logger.info(
        "Seed concluído: %d pesquisadores | %d vínculos institucionais | %d vínculos em coleções.",
        total_researchers,
        total_inst_links,
        total_col_links,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Insere pesquisadores e vínculos a partir dos CSVs de seed."
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="URL de conexão PostgreSQL (padrão: ADMIN_DATABASE_URL ou localhost).",
    )
    parser.add_argument(
        "--seed-dir",
        type=Path,
        default=DEFAULT_SEED_DIR,
        help=f"Pasta com os CSVs de seed (padrão: {DEFAULT_SEED_DIR}).",
    )
    args = parser.parse_args()
    run_seed(db_url=resolve_db_url(args.db_url), seed_dir=args.seed_dir)


if __name__ == "__main__":
    main()
