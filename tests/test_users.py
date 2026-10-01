from http import HTTPStatus
from uuid import UUID

from simcc_admin.models import UserRole


def test_create_user(client):
    response = client.post(
        "/users/",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "secret",
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert data["role"] == UserRole.DEFAULT
    assert UUID(data["id"])


def test_read_current_user(client, user, token):
    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["username"] == user.username
    assert data["email"] == user.email
    assert data["role"] == UserRole.DEFAULT
    assert data["id"] == str(user.id)


def test_read_current_user_unauthorized(client):
    response = client.get("/users/me")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_read_users_unauthorized(client):
    response = client.get("/users/")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_read_users_forbidden_for_default_user(client, token):
    response = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {"detail": "Not enough permissions"}


def test_read_users_with_admin(admin_client):
    response = admin_client.get("/users/")
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    # admin_user criado pela fixture admin_client já existe
    assert body["pagination"]["total_items"] >= 1
    assert body["pagination"]["page"] == 1


def test_read_users_with_admin_and_users(admin_client, user):
    response = admin_client.get("/users/")
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    user_ids = [u["id"] for u in body["data"]]
    assert str(user.id) in user_ids


def test_update_user(client, user, token):
    response = client.put(
        f"/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "bob",
            "email": "bob@example.com",
            "password": "mynewpassword",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "username": "bob",
        "email": "bob@example.com",
        "id": str(user.id),
        "role": UserRole.DEFAULT,
    }


def test_update_integrity_error(client, user, token):
    # Inserindo fausto
    client.post(
        "/users/",
        json={
            "username": "fausto",
            "email": "fausto@example.com",
            "password": "secret",
        },
    )

    # Alterando o user da fixture para fausto
    response_update = client.put(
        f"/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "fausto",
            "email": "bob@example.com",
            "password": "mynewpassword",
        },
    )

    assert response_update.status_code == HTTPStatus.CONFLICT
    assert response_update.json() == {"detail": "Username or Email already exists"}


def test_delete_user(client, user, token):
    response = client.delete(
        f"/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "User deleted"}


def test_update_user_with_wrong_user(client, other_user, token):
    response = client.put(
        f"/users/{other_user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "bob",
            "email": "bob@example.com",
            "password": "mynewpassword",
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {"detail": "Not enough permissions"}


def test_delete_user_wrong_user(client, other_user, token):
    response = client.delete(
        f"/users/{other_user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json() == {"detail": "Not enough permissions"}


def test_admin_can_update_other_user(admin_client, other_user):
    response = admin_client.put(
        f"/users/{other_user.id}",
        json={
            "username": "updated_by_admin",
            "email": "admin_updated@example.com",
            "password": "newpassword123",
        },
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["username"] == "updated_by_admin"
    assert data["email"] == "admin_updated@example.com"


def test_admin_can_delete_other_user(admin_client, other_user):
    response = admin_client.delete(f"/users/{other_user.id}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "User deleted"}
