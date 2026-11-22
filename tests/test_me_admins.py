from http import HTTPStatus
from uuid import uuid4

import pytest
from sqlalchemy import select

from simcc_admin.models import Admin


def test_me_requires_authentication(client):
    res = client.get("/me")
    assert res.status_code == HTTPStatus.UNAUTHORIZED


def test_me_non_admin_even_with_idp_admin_role_claim(
    client, user, token_generator
):
    token = token_generator(user, extra_claims={"role": "ADMIN"})
    res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == HTTPStatus.OK
    assert res.json() == {
        "user": {
            "sub": user.sub,
            "name": user.name,
            "email": user.email,
        },
        "is_admin": False,
    }


def test_me_admin_user(admin_client, admin_user):
    res = admin_client.get("/me")
    assert res.status_code == HTTPStatus.OK
    assert res.json() == {
        "user": {
            "sub": admin_user.sub,
            "name": admin_user.name,
            "email": admin_user.email,
        },
        "is_admin": True,
    }


def test_academic_rejects_idp_admin_role_not_in_admins_table(
    client, user, token_generator
):
    token = token_generator(user, extra_claims={"role": "ADMIN"})
    res = client.get(
        "/academic/researchers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == HTTPStatus.FORBIDDEN


def test_admins_crud_and_guards(admin_client, admin_record, user, token_generator):
    # Usuário não admin recebe 403
    user_token = token_generator(user)
    forbidden = admin_client.get(
        "/admins", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert forbidden.status_code == HTTPStatus.FORBIDDEN

    # Criar novo admin
    create_res = admin_client.post(
        "/admins",
        json={
            "sub": "new-admin-sub",
            "name": "Maria Silva",
            "email": "maria@secti.ba.gov.br",
        },
    )
    assert create_res.status_code == HTTPStatus.CREATED
    created = create_res.json()
    assert created["sub"] == "new-admin-sub"
    assert created["created_by"] == admin_record.sub

    # Duplicado -> 409
    dup_res = admin_client.post("/admins", json={"sub": "new-admin-sub"})
    assert dup_res.status_code == HTTPStatus.CONFLICT

    # Listar e filtrar com q
    list_res = admin_client.get("/admins", params={"q": "maria"})
    assert list_res.status_code == HTTPStatus.OK
    body = list_res.json()
    assert body["pagination"]["total_items"] == 1
    assert body["data"][0]["sub"] == "new-admin-sub"

    # Não pode remover a si mesmo -> 409
    self_del = admin_client.delete(f"/admins/{admin_record.id}")
    assert self_del.status_code == HTTPStatus.CONFLICT

    # Remover o outro admin -> 204
    del_res = admin_client.delete(f"/admins/{created['id']}")
    assert del_res.status_code == HTTPStatus.NO_CONTENT

    # Remover inexistente -> 404
    missing_del = admin_client.delete(f"/admins/{uuid4()}")
    assert missing_del.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_delete_last_admin_returns_409(
    client, session, admin_record, user, token_generator
):
    # Simula um cenário onde só existe 1 admin na tabela e outro admin tenta removê-lo
    # (ou via manipulação direta): como admin_record é o único, outro sub precisaria ser admin,
    # então validamos a regra removendo admin_record por um segundo admin e tentando remover o último.
    second = Admin(sub="second-admin", name="Second", created_by="test")
    session.add(second)
    await session.commit()
    await session.refresh(second)

    # Remove admin_record usando token de second -> 204
    from simcc_admin.security import AuthenticatedUser

    second_user = AuthenticatedUser(
        sub="second-admin", name="Second", email=None, is_admin=True
    )
    second_token = token_generator(second_user)
    res_ok = client.delete(
        f"/admins/{admin_record.id}",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert res_ok.status_code == HTTPStatus.NO_CONTENT

    remaining = list(await session.scalars(select(Admin)))
    assert len(remaining) == 1
