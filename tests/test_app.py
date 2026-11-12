from fastapi import FastAPI
from fastapi.testclient import TestClient

from simcc_admin.app import ForwardedPrefixMiddleware, app
from simcc_admin.settings import Settings

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Olá Mundo!"}


def test_settings_root_path_normalization():
    assert Settings.assemble_root_path("") == ""
    assert Settings.assemble_root_path(None) == ""
    assert Settings.assemble_root_path("/") == ""
    assert Settings.assemble_root_path("/simcc/admin") == "/simcc/admin"
    assert Settings.assemble_root_path("simcc/admin") == "/simcc/admin"
    assert Settings.assemble_root_path("/simcc/admin/") == "/simcc/admin"


def test_redoc_default_and_forwarded_prefix():
    # Sem prefixo configurado
    res = client.get("/redoc")
    assert res.status_code == 200

    # Com cabeçalho X-Forwarded-Prefix do proxy reverso
    res_proxy = client.get("/redoc", headers={"X-Forwarded-Prefix": "/simcc/admin"})
    assert res_proxy.status_code == 200
    assert 'spec-url="/simcc/admin/openapi.json"' in res_proxy.text


def test_custom_root_path_app():
    custom_app = FastAPI(root_path="/simcc/admin")
    custom_app.add_middleware(ForwardedPrefixMiddleware, default_prefix="/simcc/admin")

    custom_client = TestClient(custom_app)

    redoc_res = custom_client.get("/redoc")
    assert redoc_res.status_code == 200
    assert 'spec-url="/simcc/admin/openapi.json"' in redoc_res.text

    docs_res = custom_client.get("/docs")
    assert docs_res.status_code == 200
    assert "url: '/simcc/admin/openapi.json'" in docs_res.text
