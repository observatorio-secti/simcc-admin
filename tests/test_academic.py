from http import HTTPStatus
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from simcc_admin.models import Researcher, ResearcherInstitution


@pytest.mark.asyncio
async def test_search_researchers_empty(client):
    response = client.get("/academic/researchers")
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
async def test_search_researchers_pagination(client, researcher_generator):
    for i in range(5):
        await researcher_generator(name=f"Pesquisador {i}", lattes_id=f"{i:016d}")

    response = client.get("/academic/researchers?page=1&per_page=2")
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
    page2_resp = client.get("/academic/researchers?page=2&per_page=2")
    page2_body = page2_resp.json()
    assert len(page2_body["data"]) == 2
    assert page2_body["pagination"]["has_next"] is True
    assert page2_body["pagination"]["has_prev"] is True

    # Página 3 (última)
    page3_resp = client.get("/academic/researchers?page=3&per_page=2")
    page3_body = page3_resp.json()
    assert len(page3_body["data"]) == 1
    assert page3_body["pagination"]["has_next"] is False
    assert page3_body["pagination"]["has_prev"] is True


@pytest.mark.asyncio
async def test_search_researchers_filter_by_name(client, researcher_generator):
    r1 = await researcher_generator(name="Maria Silva", lattes_id="1111111111111111")
    await researcher_generator(name="João Souza", lattes_id="2222222222222222")

    response = client.get("/academic/researchers?q=silva")
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Maria Silva"
    assert body["data"][0]["researcher_id"] == str(r1.id)
    assert body["filters_applied"]["q"] == "silva"


@pytest.mark.asyncio
async def test_search_researchers_filter_by_lattes(client, researcher_generator):
    r1 = await researcher_generator(name="Carlos Lima", lattes_id="1234567890123456")
    await researcher_generator(name="Ana Rocha", lattes_id="9999999999999999")

    response = client.get("/academic/researchers?q=123456")
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Carlos Lima"
    assert body["data"][0]["lattes_id"] == "1234567890123456"
    assert body["data"][0]["researcher_id"] == str(r1.id)


@pytest.mark.asyncio
async def test_search_researchers_filter_by_institution(
    client,
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

    response = client.get(f"/academic/researchers?institution_id={ufba.id}")
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Pesquisador UFBA"
    assert body["filters_applied"]["institution_id"] == str(ufba.id)


@pytest.mark.asyncio
async def test_search_researchers_sort(client, researcher_generator):
    await researcher_generator(name="Bruno", lattes_id="2222222222222222")
    await researcher_generator(name="Alice", lattes_id="1111111111111111")
    await researcher_generator(name="Carlos", lattes_id="3333333333333333")

    # Ordem Ascendente por Nome
    resp_asc = client.get("/academic/researchers?sort_by=name&sort_order=asc")
    names_asc = [item["name"] for item in resp_asc.json()["data"]]
    assert names_asc == ["Alice", "Bruno", "Carlos"]

    # Ordem Descendente por Nome
    resp_desc = client.get("/academic/researchers?sort_by=name&sort_order=desc")
    names_desc = [item["name"] for item in resp_desc.json()["data"]]
    assert names_desc == ["Carlos", "Bruno", "Alice"]


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

    # Verifica UUIDs
    assert isinstance(inst1.id, UUID)
    assert isinstance(res1.id, UUID)

    # Vínculo entre pesquisador e instituição
    link = await researcher_institution_generator(
        researcher_id=res1.id, institution_id=inst1.id
    )
    assert isinstance(link.id, UUID)

    res1_id = res1.id
    inst1_id = inst1.id

    # Tentativa de duplicar o mesmo vínculo viola constraint única
    with pytest.raises(IntegrityError):
        await researcher_institution_generator(
            researcher_id=res1_id, institution_id=inst1_id
        )
    await session.rollback()

    # Deleção em cascata: excluir pesquisador remove o vínculo automaticamente
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
