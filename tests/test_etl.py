from http import HTTPStatus
from uuid import uuid4

import httpx

from simcc_admin.routers import etl as etl_router


def test_etl_requires_admin(client, user, token_generator):
    token = token_generator(user)
    res = client.get("/etl/routines", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == HTTPStatus.FORBIDDEN


def test_etl_routes_proxy_and_errors(admin_client, admin_user, monkeypatch):
    run_id = str(uuid4())
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["url"] = str(request.url)

        if request.method == "GET" and request.url.path == "/routines":
            return httpx.Response(200, json=["lattes_extract", "openalex_enrich"])

        if request.method == "POST" and request.url.path == "/runs":
            import json

            captured["post_body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(202, json={"run_id": run_id, "status": "ACCEPTED"})

        if request.method == "GET" and request.url.path == "/runs":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": run_id,
                            "status": "RUNNING",
                            "started_at": "2026-11-22T05:00:00Z",
                            "ended_at": None,
                            "triggered_by": admin_user.sub,
                            "current_routine": "lattes_extract",
                            "routines": ["lattes_extract"],
                            "lattes_ids": None,
                            "steps": {},
                            "error_message": None,
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "per_page": 10,
                        "total_items": 1,
                        "total_pages": 1,
                        "has_next": False,
                        "has_prev": False,
                    },
                },
            )

        if request.method == "GET" and request.url.path == f"/runs/{run_id}":
            return httpx.Response(
                200,
                json={
                    "id": run_id,
                    "status": "COMPLETED",
                    "started_at": "2026-11-22T05:00:00Z",
                    "ended_at": "2026-11-22T05:01:00Z",
                    "triggered_by": admin_user.sub,
                    "current_routine": None,
                    "routines": ["lattes_extract"],
                    "lattes_ids": None,
                    "steps": {},
                    "error_message": None,
                },
            )

        if request.method == "GET" and request.url.path == f"/runs/{run_id}/logs":
            return httpx.Response(
                200,
                json={
                    "lines": [{"msg": "ok"}],
                    "next_offset": 1,
                    "status": "COMPLETED",
                },
            )

        return httpx.Response(404, json={"detail": "Not found"})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        etl_router,
        "_get_etl_client",
        lambda: httpx.AsyncClient(
            base_url="http://etl.local",
            headers={"X-ETL-API-Key": "secret-key"},
            transport=transport,
        ),
    )

    # GET /etl/routines
    r_routines = admin_client.get("/etl/routines")
    assert r_routines.status_code == HTTPStatus.OK
    assert r_routines.json() == ["lattes_extract", "openalex_enrich"]
    assert captured["headers"]["x-etl-api-key"] == "secret-key"

    # POST /etl/runs injeta triggered_by do token
    r_trigger = admin_client.post(
        "/etl/runs", json={"routines": ["lattes_extract"], "force": True}
    )
    assert r_trigger.status_code == HTTPStatus.ACCEPTED
    assert r_trigger.json() == {"run_id": run_id, "status": "ACCEPTED"}
    assert captured["post_body"]["triggered_by"] == admin_user.sub
    assert captured["post_body"]["force"] is True

    # GET /etl/runs repassa page, per_page e status
    r_runs = admin_client.get(
        "/etl/runs", params={"page": 1, "per_page": 10, "status": "RUNNING"}
    )
    assert r_runs.status_code == HTTPStatus.OK
    assert r_runs.json()["pagination"]["total_items"] == 1
    assert "status=RUNNING" in captured["url"]

    # GET /etl/runs/{run_id}
    r_detail = admin_client.get(f"/etl/runs/{run_id}")
    assert r_detail.status_code == HTTPStatus.OK
    assert r_detail.json()["status"] == "COMPLETED"

    # GET /etl/runs/{run_id}/logs
    r_logs = admin_client.get(
        f"/etl/runs/{run_id}/logs", params={"offset": 0, "limit": 50}
    )
    assert r_logs.status_code == HTTPStatus.OK
    assert r_logs.json() == {
        "lines": [{"msg": "ok"}],
        "next_offset": 1,
        "status": "COMPLETED",
    }


def test_etl_401_from_upstream_becomes_502_and_timeout_becomes_504(
    admin_client, monkeypatch
):
    def unauthorized_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid API Key"})

    monkeypatch.setattr(
        etl_router,
        "_get_etl_client",
        lambda: httpx.AsyncClient(
            base_url="http://etl.local",
            transport=httpx.MockTransport(unauthorized_handler),
        ),
    )
    res_502 = admin_client.get("/etl/routines")
    assert res_502.status_code == HTTPStatus.BAD_GATEWAY
    assert "detail" in res_502.json()

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(
        etl_router,
        "_get_etl_client",
        lambda: httpx.AsyncClient(
            base_url="http://etl.local",
            transport=httpx.MockTransport(timeout_handler),
        ),
    )
    res_504 = admin_client.get("/etl/routines")
    assert res_504.status_code == HTTPStatus.GATEWAY_TIMEOUT
    assert "detail" in res_504.json()
