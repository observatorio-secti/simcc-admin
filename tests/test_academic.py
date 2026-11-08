import io
import json
from http import HTTPStatus
from uuid import UUID, uuid4

import polars as pl
import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from simcc_admin.models import (
    Collection,
    Researcher,
    ResearcherCollection,
    ResearcherInstitution,
)
from simcc_admin.settings import Settings

# --- Testes de RBAC nas Rotas Acadêmicas ---


def test_academic_researchers_unauthorized(client):
    response = client.get("/academic/researchers")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_academic_researchers_forbidden_for_default_user(client, token):
    response = client.get(
        "/academic/researchers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {"detail": "Not enough permissions"}


def test_academic_institutions_unauthorized(client):
    response = client.get("/academic/institutions")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_academic_institutions_forbidden_for_default_user(client, token):
    response = client.get(
        "/academic/institutions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {"detail": "Not enough permissions"}


# --- Testes de Busca de Pesquisadores ---


@pytest.mark.asyncio
async def test_search_researchers_empty(admin_client):
    response = admin_client.get("/academic/researchers")
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert body["data"] == []
    assert body["pagination"]["total_items"] == 0
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["per_page"] == 20
    assert body["pagination"]["total_pages"] == 0
    assert body["pagination"]["has_next"] is False
    assert body["pagination"]["has_prev"] is False
    assert body["filters_applied"] == {
        "q": None,
        "institution_id": None,
        "collection_id": None,
    }
    assert body["sort"] == {"by": "name", "order": "asc"}
    assert "took_ms" in body["meta"]
    assert body["meta"]["cached"] is False


@pytest.mark.asyncio
async def test_search_researchers_pagination(admin_client, researcher_generator):
    for i in range(5):
        await researcher_generator(name=f"Pesquisador {i}", lattes_id=f"{i:016d}")

    response = admin_client.get("/academic/researchers?page=1&per_page=2")
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert len(body["data"]) == 2
    assert body["pagination"]["total_items"] == 5
    assert body["pagination"]["total_pages"] == 3
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["per_page"] == 2
    assert body["pagination"]["has_next"] is True
    assert body["pagination"]["has_prev"] is False

    # Página 2
    page2_resp = admin_client.get("/academic/researchers?page=2&per_page=2")
    page2_body = page2_resp.json()
    assert len(page2_body["data"]) == 2
    assert page2_body["pagination"]["has_next"] is True
    assert page2_body["pagination"]["has_prev"] is True

    # Página 3 (última)
    page3_resp = admin_client.get("/academic/researchers?page=3&per_page=2")
    page3_body = page3_resp.json()
    assert len(page3_body["data"]) == 1
    assert page3_body["pagination"]["has_next"] is False
    assert page3_body["pagination"]["has_prev"] is True


@pytest.mark.asyncio
async def test_search_researchers_filter_by_name(admin_client, researcher_generator):
    r1 = await researcher_generator(name="Maria Silva", lattes_id="1111111111111111")
    await researcher_generator(name="João Souza", lattes_id="2222222222222222")

    response = admin_client.get("/academic/researchers?q=silva")
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Maria Silva"
    assert body["data"][0]["researcher_id"] == str(r1.id)
    assert body["filters_applied"]["q"] == "silva"


@pytest.mark.asyncio
async def test_search_researchers_filter_by_lattes(admin_client, researcher_generator):
    r1 = await researcher_generator(name="Carlos Lima", lattes_id="1234567890123456")
    await researcher_generator(name="Ana Rocha", lattes_id="9999999999999999")

    response = admin_client.get("/academic/researchers?q=123456")
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Carlos Lima"
    assert body["data"][0]["lattes_id"] == "1234567890123456"
    assert body["data"][0]["researcher_id"] == str(r1.id)


@pytest.mark.asyncio
async def test_search_researchers_filter_by_institution(
    admin_client,
    institution_generator,
    researcher_generator,
    researcher_institution_generator,
):
    ufba = await institution_generator(
        name="Universidade Federal da Bahia", acronym="UFBA"
    )
    uneb = await institution_generator(
        name="Universidade do Estado da Bahia", acronym="UNEB"
    )

    r1 = await researcher_generator(
        name="Pesquisador UFBA", lattes_id="1010101010101010"
    )
    r2 = await researcher_generator(
        name="Pesquisador UNEB", lattes_id="2020202020202020"
    )

    await researcher_institution_generator(researcher_id=r1.id, institution_id=ufba.id)
    await researcher_institution_generator(researcher_id=r2.id, institution_id=uneb.id)

    response = admin_client.get(f"/academic/researchers?institution_id={ufba.id}")
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Pesquisador UFBA"
    assert body["filters_applied"]["institution_id"] == str(ufba.id)
    assert len(body["data"][0]["affiliations"]) == 1
    assert body["data"][0]["affiliations"][0]["institution"]["acronym"] == "UFBA"


@pytest.mark.asyncio
async def test_search_researchers_sort(admin_client, researcher_generator):
    await researcher_generator(name="Bruno", lattes_id="2222222222222222")
    await researcher_generator(name="Alice", lattes_id="1111111111111111")
    await researcher_generator(name="Carlos", lattes_id="3333333333333333")

    # Ordem Ascendente por Nome
    resp_asc = admin_client.get("/academic/researchers?sort_by=name&sort_order=asc")
    names_asc = [item["name"] for item in resp_asc.json()["data"]]
    assert names_asc == ["Alice", "Bruno", "Carlos"]

    # Ordem Descendente por Nome
    resp_desc = admin_client.get("/academic/researchers?sort_by=name&sort_order=desc")
    names_desc = [item["name"] for item in resp_desc.json()["data"]]
    assert names_desc == ["Carlos", "Bruno", "Alice"]


# --- Testes de CRUD de Institution ---


@pytest.mark.asyncio
async def test_create_institution_success(admin_client):
    response = admin_client.post(
        "/academic/institutions/",
        json={"name": "Universidade Estadual de Campinas", "acronym": "UNICAMP"},
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["name"] == "Universidade Estadual de Campinas"
    assert data["acronym"] == "UNICAMP"
    assert UUID(data["id"])


@pytest.mark.asyncio
async def test_create_institution_conflict(admin_client, institution_generator):
    await institution_generator(name="Universidade de São Paulo", acronym="USP")

    # Nome duplicado
    resp_name = admin_client.post(
        "/academic/institutions/",
        json={"name": "Universidade de São Paulo", "acronym": "USP2"},
    )
    assert resp_name.status_code == HTTPStatus.CONFLICT

    # Sigla duplicada
    resp_acronym = admin_client.post(
        "/academic/institutions/",
        json={"name": "Outra USP", "acronym": "USP"},
    )
    assert resp_acronym.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_get_institution_success_and_not_found(
    admin_client, institution_generator
):
    inst = await institution_generator(name="UFMG", acronym="UFMG")

    resp = admin_client.get(f"/academic/institutions/{inst.id}")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["id"] == str(inst.id)
    assert resp.json()["acronym"] == "UFMG"

    resp_404 = admin_client.get(f"/academic/institutions/{uuid4()}")
    assert resp_404.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_list_institutions(admin_client, institution_generator):
    await institution_generator(name="Universidade Federal do Ceará", acronym="UFC")
    await institution_generator(name="Universidade Federal do Rio", acronym="UFRJ")

    resp = admin_client.get("/academic/institutions?q=ceará")
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["acronym"] == "UFC"
    assert body["pagination"]["total_items"] == 1


@pytest.mark.asyncio
async def test_update_institution(admin_client, institution_generator):
    inst1 = await institution_generator(name="UFBA Velha", acronym="UFBAV")
    await institution_generator(name="Existente", acronym="EXI")

    # Atualização com sucesso
    resp = admin_client.put(
        f"/academic/institutions/{inst1.id}",
        json={"name": "UFBA Nova", "acronym": "UFBAN"},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["name"] == "UFBA Nova"
    assert resp.json()["acronym"] == "UFBAN"

    # Tentativa de atualizar com nome já em uso por outra instituição
    resp_conflict = admin_client.put(
        f"/academic/institutions/{inst1.id}",
        json={"name": "Existente", "acronym": "UFBAN"},
    )
    assert resp_conflict.status_code == HTTPStatus.CONFLICT

    # 404 para ID inexistente
    resp_404 = admin_client.put(
        f"/academic/institutions/{uuid4()}",
        json={"name": "Nao Existe", "acronym": "NE"},
    )
    assert resp_404.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_delete_institution(admin_client, institution_generator):
    inst = await institution_generator(name="Para Deletar", acronym="DEL")

    resp = admin_client.delete(f"/academic/institutions/{inst.id}")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["message"] == "Institution deleted"

    # Segunda deleção retorna 404
    resp_404 = admin_client.delete(f"/academic/institutions/{inst.id}")
    assert resp_404.status_code == HTTPStatus.NOT_FOUND


# --- Testes de CRUD de Researcher e Affiliations ---


@pytest.mark.asyncio
async def test_create_researcher_with_institutions(
    admin_client, institution_generator, default_collection
):
    inst1 = await institution_generator(name="Inst 1", acronym="I1")
    inst2 = await institution_generator(name="Inst 2", acronym="I2")

    resp = admin_client.post(
        "/academic/researchers/",
        json={
            "name": "Prof. Doutor",
            "lattes_id": "1234123412341234",
            "institution_ids": [str(inst1.id), str(inst2.id)],
        },
    )
    assert resp.status_code == HTTPStatus.CREATED
    body = resp.json()
    assert body["name"] == "Prof. Doutor"
    assert body["lattes_id"] == "1234123412341234"
    assert len(body["affiliations"]) == 2
    # Verifica composição do InstitutionRef dentro de cada Affiliation
    acronyms = {a["institution"]["acronym"] for a in body["affiliations"]}
    assert acronyms == {"I1", "I2"}


@pytest.mark.asyncio
async def test_create_researcher_conflict(
    admin_client, researcher_generator, default_collection
):
    await researcher_generator(name="Original", lattes_id="5555555555555555")

    resp = admin_client.post(
        "/academic/researchers/",
        json={"name": "Duplicado", "lattes_id": "5555555555555555"},
    )
    assert resp.status_code == HTTPStatus.CONFLICT


@pytest.mark.asyncio
async def test_get_researcher_detail(
    admin_client,
    institution_generator,
    researcher_generator,
    researcher_institution_generator,
):
    inst = await institution_generator(name="Fiocruz", acronym="FIOCRUZ")
    res = await researcher_generator(name="Cientista", lattes_id="7777777777777777")
    await researcher_institution_generator(researcher_id=res.id, institution_id=inst.id)

    resp = admin_client.get(f"/academic/researchers/{res.id}")
    assert resp.status_code == HTTPStatus.OK
    body = resp.json()
    assert body["researcher_id"] == str(res.id)
    assert body["name"] == "Cientista"
    assert len(body["affiliations"]) == 1
    assert body["affiliations"][0]["institution"]["acronym"] == "FIOCRUZ"

    # 404
    resp_404 = admin_client.get(f"/academic/researchers/{uuid4()}")
    assert resp_404.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_update_researcher(admin_client, researcher_generator):
    r1 = await researcher_generator(name="Nome Antigo", lattes_id="8888888888888888")
    await researcher_generator(name="Outro", lattes_id="9999999999999999")

    # Sucesso
    resp = admin_client.put(
        f"/academic/researchers/{r1.id}",
        json={"name": "Nome Atualizado", "lattes_id": "8888888888888888"},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["name"] == "Nome Atualizado"

    # Conflito de Lattes ID
    resp_conflict = admin_client.put(
        f"/academic/researchers/{r1.id}",
        json={"name": "Nome Atualizado", "lattes_id": "9999999999999999"},
    )
    assert resp_conflict.status_code == HTTPStatus.CONFLICT

    # 404
    resp_404 = admin_client.put(
        f"/academic/researchers/{uuid4()}",
        json={"name": "Fantasma", "lattes_id": "0000000000000000"},
    )
    assert resp_404.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_delete_researcher(admin_client, researcher_generator):
    res = await researcher_generator(name="Para Deletar", lattes_id="4444444444444444")

    resp = admin_client.delete(f"/academic/researchers/{res.id}")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["message"] == "Researcher deleted"

    resp_404 = admin_client.delete(f"/academic/researchers/{res.id}")
    assert resp_404.status_code == HTTPStatus.NOT_FOUND


# --- Testes de Endpoints Atômicos de Vínculo (Affiliations) ---


@pytest.mark.asyncio
async def test_atomic_affiliation_endpoints(
    admin_client, institution_generator, researcher_generator
):
    inst = await institution_generator(name="Universidade A", acronym="UA")
    res = await researcher_generator(name="Pesquisador B", lattes_id="3333111122224444")

    # 1. Adicionar vínculo
    resp_add = admin_client.post(
        f"/academic/researchers/{res.id}/institutions/{inst.id}"
    )
    assert resp_add.status_code == HTTPStatus.CREATED
    data = resp_add.json()
    assert data["institution"]["id"] == str(inst.id)
    assert data["institution"]["acronym"] == "UA"
    assert "created_at" in data

    # 2. Tentar adicionar novamente retorna conflito
    resp_conflict = admin_client.post(
        f"/academic/researchers/{res.id}/institutions/{inst.id}"
    )
    assert resp_conflict.status_code == HTTPStatus.CONFLICT

    # 3. 404 para entidades inexistentes
    resp_404_res = admin_client.post(
        f"/academic/researchers/{uuid4()}/institutions/{inst.id}"
    )
    assert resp_404_res.status_code == HTTPStatus.NOT_FOUND

    # 4. Remover vínculo
    resp_del = admin_client.delete(
        f"/academic/researchers/{res.id}/institutions/{inst.id}"
    )
    assert resp_del.status_code == HTTPStatus.OK
    assert resp_del.json()["message"] == "Affiliation removed"

    # 5. Tentar remover novamente retorna 404
    resp_del_404 = admin_client.delete(
        f"/academic/researchers/{res.id}/institutions/{inst.id}"
    )
    assert resp_del_404.status_code == HTTPStatus.NOT_FOUND


# --- Testes de Integridade do Modelo ---


@pytest.mark.asyncio
async def test_academic_models_integrity(
    session,
    institution_generator,
    researcher_generator,
    researcher_institution_generator,
):
    inst1 = await institution_generator(name="USP", acronym="USP")
    res1 = await researcher_generator(
        name="Pesquisador 1", lattes_id="0001000100010001"
    )

    assert isinstance(inst1.id, UUID)
    assert isinstance(res1.id, UUID)

    link = await researcher_institution_generator(
        researcher_id=res1.id, institution_id=inst1.id
    )
    assert isinstance(link.id, UUID)

    res1_id = res1.id
    inst1_id = inst1.id

    with pytest.raises(IntegrityError):
        await researcher_institution_generator(
            researcher_id=res1_id, institution_id=inst1_id
        )
    await session.rollback()

    res_to_del = await session.scalar(
        select(Researcher).where(Researcher.id == res1_id)
    )
    await session.delete(res_to_del)
    await session.commit()

    remaining_link = await session.scalar(
        select(ResearcherInstitution).where(
            ResearcherInstitution.researcher_id == res1_id
        )
    )
    assert remaining_link is None


@pytest.mark.asyncio
async def test_collection_models_integrity(
    session,
    collection_generator,
    researcher_generator,
    researcher_collection_generator,
):
    col1 = await collection_generator(slug="c1", name="C1", is_default=True)
    res1 = await researcher_generator(name="Pesquisador Col", lattes_id="0002000200020002")
    col1_id = col1.id
    res1_id = res1.id

    # 1. Duplicate default collection raises IntegrityError
    with pytest.raises(IntegrityError):
        await collection_generator(slug="c2", name="C2", is_default=True)
    await session.rollback()

    # 2. Check constraint refresh_interval_days >= 1
    with pytest.raises(IntegrityError):
        await collection_generator(slug="c3", name="C3", refresh_interval_days=0)
    await session.rollback()

    # 3. Create link
    link = await researcher_collection_generator(
        researcher_id=res1_id, collection_id=col1_id, attributes={"tipo": "bolsa"}
    )
    assert isinstance(link.id, UUID)
    assert link.attributes == {"tipo": "bolsa"}

    # 4. Duplicate (researcher_id, collection_id) raises IntegrityError
    with pytest.raises(IntegrityError):
        await researcher_collection_generator(
            researcher_id=res1_id, collection_id=col1_id
        )
    await session.rollback()

    # 5. FK RESTRICT on collection delete when it has members
    with pytest.raises(IntegrityError):
        await session.execute(delete(Collection).where(Collection.id == col1_id))
        await session.commit()
    await session.rollback()

    # 6. Cascade delete on researcher delete
    await session.execute(delete(Researcher).where(Researcher.id == res1_id))
    await session.commit()

    remaining_rc = await session.scalar(
        select(ResearcherCollection).where(ResearcherCollection.researcher_id == res1_id)
    )
    assert remaining_rc is None


# --- Testes de Exportação Parquet com X-Service-Token ---


def test_export_parquet_unauthorized(client):
    response = client.get("/academic/researchers/export/parquet")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_export_parquet_invalid_service_token(client):
    response = client.get(
        "/academic/researchers/export/parquet",
        headers={"X-Service-Token": "token-totalmente-invalido"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Invalid service token"}


@pytest.mark.asyncio
async def test_export_parquet_with_valid_service_token(client, researcher_generator):
    settings = Settings()
    # Cria pesquisadores válidos e um com lattes em branco (espaços)
    await researcher_generator(name="Valido 1", lattes_id="1111222233334444")
    await researcher_generator(name="Valido 2", lattes_id="5555666677778888")
    await researcher_generator(name="Lattes Branco", lattes_id="   ")

    response = client.get(
        "/academic/researchers/export/parquet",
        headers={"X-Service-Token": settings.ADMIN_SERVICE_TOKEN},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"] == "application/octet-stream"
    assert "attachment; filename=" in response.headers["content-disposition"]

    # Lê o Parquet retornado
    df = pl.read_parquet(io.BytesIO(response.content))
    assert "lattes_id" in df.columns
    assert "refresh_interval_days" in df.columns
    exported_ids = df["lattes_id"].to_list()
    assert exported_ids == ["1111222233334444", "5555666677778888"]


@pytest.mark.asyncio
async def test_export_parquet_with_admin_jwt(admin_client, researcher_generator):
    await researcher_generator(name="Admin Export", lattes_id="9999888877776666")

    response = admin_client.get("/academic/researchers/export/parquet")
    assert response.status_code == HTTPStatus.OK
    df = pl.read_parquet(io.BytesIO(response.content))
    assert "9999888877776666" in df["lattes_id"].to_list()


def test_export_parquet_does_not_conflict_with_researcher_id(client):
    # Rota /{researcher_id} com UUID inexistente retorna 401 para usuário anônimo
    # enquanto /export/parquet também retorna 401 mas não 422 de UUID inválido
    res_export = client.get(
        "/academic/researchers/export/parquet",
        headers={"X-Service-Token": "invalid"},
    )
    assert res_export.status_code == HTTPStatus.UNAUTHORIZED
    assert res_export.json() == {"detail": "Invalid service token"}


# --- Testes de Exportação Parquet: Instituições ---


def test_export_institutions_parquet_unauthorized(client):
    response = client.get("/academic/institutions/export/parquet")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_export_institutions_parquet_invalid_service_token(client):
    response = client.get(
        "/academic/institutions/export/parquet",
        headers={"X-Service-Token": "token-invalido"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Invalid service token"}


@pytest.mark.asyncio
async def test_export_institutions_parquet_with_valid_service_token(
    client, institution_generator
):
    settings = Settings()
    await institution_generator(name="Universidade A", acronym="UNIA")
    await institution_generator(name="Universidade B", acronym="UNIB")

    response = client.get(
        "/academic/institutions/export/parquet",
        headers={"X-Service-Token": settings.ADMIN_SERVICE_TOKEN},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"] == "application/octet-stream"
    assert 'filename="institutions.parquet"' in response.headers["content-disposition"]

    df = pl.read_parquet(io.BytesIO(response.content))
    assert "name" in df.columns
    assert "acronym" in df.columns
    assert df["name"].to_list() == ["Universidade A", "Universidade B"]
    assert df["acronym"].to_list() == ["UNIA", "UNIB"]


@pytest.mark.asyncio
async def test_export_institutions_parquet_with_admin_jwt(
    admin_client, institution_generator
):
    await institution_generator(name="Universidade Admin", acronym="UNIADM")

    response = admin_client.get("/academic/institutions/export/parquet")
    assert response.status_code == HTTPStatus.OK
    df = pl.read_parquet(io.BytesIO(response.content))
    assert "UNIADM" in df["acronym"].to_list()


def test_export_institutions_parquet_does_not_conflict_with_institution_id(client):
    res_export = client.get(
        "/academic/institutions/export/parquet",
        headers={"X-Service-Token": "invalid"},
    )
    assert res_export.status_code == HTTPStatus.UNAUTHORIZED
    assert res_export.json() == {"detail": "Invalid service token"}


# --- Testes de Exportação Parquet: Coleções ---


def test_export_collections_parquet_unauthorized(client):
    response = client.get("/academic/collections/export/parquet")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_export_collections_parquet_invalid_service_token(client):
    response = client.get(
        "/academic/collections/export/parquet",
        headers={"X-Service-Token": "token-invalido"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Invalid service token"}


@pytest.mark.asyncio
async def test_export_collections_parquet_with_valid_service_token(
    client, collection_generator
):
    settings = Settings()
    col = await collection_generator(
        slug="ciencia-dados",
        name="Ciência de Dados",
        description="Coleção de dados",
        refresh_interval_days=7,
        is_default=False,
    )

    response = client.get(
        "/academic/collections/export/parquet",
        headers={"X-Service-Token": settings.ADMIN_SERVICE_TOKEN},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"] == "application/octet-stream"
    assert 'filename="collections.parquet"' in response.headers["content-disposition"]

    df = pl.read_parquet(io.BytesIO(response.content))
    assert set(df.columns) == {
        "id",
        "slug",
        "name",
        "description",
        "refresh_interval_days",
        "is_default",
        "created_at",
    }
    assert str(col.id) in df["id"].to_list()
    assert "ciencia-dados" in df["slug"].to_list()
    row = df.filter(pl.col("slug") == "ciencia-dados").to_dicts()[0]
    assert row["name"] == "Ciência de Dados"
    assert row["description"] == "Coleção de dados"
    assert row["refresh_interval_days"] == 7
    assert row["is_default"] is False


@pytest.mark.asyncio
async def test_export_collections_parquet_with_admin_jwt(
    admin_client, collection_generator
):
    await collection_generator(slug="admin-col", name="Admin Coleção")

    response = admin_client.get("/academic/collections/export/parquet")
    assert response.status_code == HTTPStatus.OK
    df = pl.read_parquet(io.BytesIO(response.content))
    assert "admin-col" in df["slug"].to_list()


def test_export_collections_parquet_does_not_conflict_with_collection_id(client):
    res_export = client.get(
        "/academic/collections/export/parquet",
        headers={"X-Service-Token": "invalid"},
    )
    assert res_export.status_code == HTTPStatus.UNAUTHORIZED
    assert res_export.json() == {"detail": "Invalid service token"}


# --- Testes de Exportação Parquet: Vínculos Pesquisador ↔ Instituição ---


def test_export_researcher_institutions_parquet_unauthorized(client):
    response = client.get("/academic/researchers/institutions/export/parquet")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_export_researcher_institutions_parquet_invalid_service_token(client):
    response = client.get(
        "/academic/researchers/institutions/export/parquet",
        headers={"X-Service-Token": "token-invalido"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Invalid service token"}


@pytest.mark.asyncio
async def test_export_researcher_institutions_parquet_with_valid_service_token(
    client,
    researcher_generator,
    institution_generator,
    researcher_institution_generator,
):
    settings = Settings()
    res1 = await researcher_generator(name="Pesquisador 1", lattes_id="1111000011110000")
    res2 = await researcher_generator(name="Pesquisador 2", lattes_id="2222000022220000")
    res_no_lattes = await researcher_generator(name="Sem Lattes", lattes_id="   ")

    inst1 = await institution_generator(name="Instituto X", acronym="IX")
    inst2 = await institution_generator(name="Instituto Y", acronym="IY")

    await researcher_institution_generator(researcher_id=res1.id, institution_id=inst1.id)
    await researcher_institution_generator(researcher_id=res1.id, institution_id=inst2.id)
    await researcher_institution_generator(researcher_id=res2.id, institution_id=inst1.id)
    await researcher_institution_generator(researcher_id=res_no_lattes.id, institution_id=inst1.id)

    response = client.get(
        "/academic/researchers/institutions/export/parquet",
        headers={"X-Service-Token": settings.ADMIN_SERVICE_TOKEN},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"] == "application/octet-stream"
    assert 'filename="researcher_institutions.parquet"' in response.headers["content-disposition"]

    df = pl.read_parquet(io.BytesIO(response.content))
    assert "lattes_id" in df.columns
    assert "acronym" in df.columns

    rows = df.to_dicts()
    assert len(rows) == 3
    assert {"lattes_id": "1111000011110000", "acronym": "IX"} in rows
    assert {"lattes_id": "1111000011110000", "acronym": "IY"} in rows
    assert {"lattes_id": "2222000022220000", "acronym": "IX"} in rows


@pytest.mark.asyncio
async def test_export_researcher_institutions_parquet_with_admin_jwt(
    admin_client,
    researcher_generator,
    institution_generator,
    researcher_institution_generator,
):
    res = await researcher_generator(name="Pesquisador JWT", lattes_id="3333000033330000")
    inst = await institution_generator(name="Instituto Z", acronym="IZ")
    await researcher_institution_generator(researcher_id=res.id, institution_id=inst.id)

    response = admin_client.get("/academic/researchers/institutions/export/parquet")
    assert response.status_code == HTTPStatus.OK
    df = pl.read_parquet(io.BytesIO(response.content))
    assert {"lattes_id": "3333000033330000", "acronym": "IZ"} in df.to_dicts()


def test_export_researcher_institutions_parquet_does_not_conflict_with_researcher_id(client):
    res_export = client.get(
        "/academic/researchers/institutions/export/parquet",
        headers={"X-Service-Token": "invalid"},
    )
    assert res_export.status_code == HTTPStatus.UNAUTHORIZED
    assert res_export.json() == {"detail": "Invalid service token"}


# --- Testes de Exportação Parquet: Vínculos Pesquisador ↔ Coleção ---


def test_export_researcher_collections_parquet_unauthorized(client):
    response = client.get("/academic/researchers/collections/export/parquet")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_export_researcher_collections_parquet_invalid_service_token(client):
    response = client.get(
        "/academic/researchers/collections/export/parquet",
        headers={"X-Service-Token": "token-invalido"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Invalid service token"}


@pytest.mark.asyncio
async def test_export_researcher_collections_parquet_with_valid_service_token(
    client,
    researcher_generator,
    collection_generator,
    researcher_collection_generator,
):
    settings = Settings()
    res = await researcher_generator(name="Pesquisador Col", lattes_id="4444000044440000")
    col = await collection_generator(slug="colecao-teste", name="Coleção Teste")
    await researcher_collection_generator(
        researcher_id=res.id,
        collection_id=col.id,
        attributes={"cargo": "docente", "nivel": "titular"},
    )

    response = client.get(
        "/academic/researchers/collections/export/parquet",
        headers={"X-Service-Token": settings.ADMIN_SERVICE_TOKEN},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"] == "application/octet-stream"
    assert 'filename="researcher_collections.parquet"' in response.headers["content-disposition"]

    df = pl.read_parquet(io.BytesIO(response.content))
    assert set(df.columns) == {"lattes_id", "collection_id", "attributes", "created_at"}
    rows = df.to_dicts()
    assert len(rows) >= 1
    match = [r for r in rows if r["lattes_id"] == "4444000044440000"]
    assert len(match) == 1
    assert match[0]["collection_id"] == str(col.id)
    parsed_attrs = json.loads(match[0]["attributes"])
    assert parsed_attrs == {"cargo": "docente", "nivel": "titular"}


@pytest.mark.asyncio
async def test_export_researcher_collections_parquet_with_admin_jwt(
    admin_client,
    researcher_generator,
    collection_generator,
    researcher_collection_generator,
):
    res = await researcher_generator(name="Pesquisador Col Admin", lattes_id="5555000055550000")
    col = await collection_generator(slug="colecao-admin", name="Coleção Admin")
    await researcher_collection_generator(
        researcher_id=res.id,
        collection_id=col.id,
        attributes={},
    )

    response = admin_client.get("/academic/researchers/collections/export/parquet")
    assert response.status_code == HTTPStatus.OK
    df = pl.read_parquet(io.BytesIO(response.content))
    assert "5555000055550000" in df["lattes_id"].to_list()


def test_export_researcher_collections_parquet_does_not_conflict_with_researcher_id(client):
    res_export = client.get(
        "/academic/researchers/collections/export/parquet",
        headers={"X-Service-Token": "invalid"},
    )
    assert res_export.status_code == HTTPStatus.UNAUTHORIZED
    assert res_export.json() == {"detail": "Invalid service token"}
