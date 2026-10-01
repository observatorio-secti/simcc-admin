from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from simcc_admin.models import Researcher, ResearcherInstitution

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
    assert body["filters_applied"] == {"q": None, "institution_id": None}
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
async def test_create_researcher_with_institutions(admin_client, institution_generator):
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
async def test_create_researcher_conflict(admin_client, researcher_generator):
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
