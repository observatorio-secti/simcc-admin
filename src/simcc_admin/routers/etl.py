from http import HTTPStatus
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ValidationError

from simcc_admin.schemas import (
    ErrorDetail,
    EtlRunDetail,
    EtlRunListResponse,
    EtlRunLogsResponse,
    EtlRunTriggerRequest,
    EtlRunTriggerResponse,
)
from simcc_admin.security import AdminUser, require_admin
from simcc_admin.settings import Settings

router = APIRouter(
    prefix="/etl",
    tags=["etl"],
    responses={
        401: {"model": ErrorDetail},
        403: {"model": ErrorDetail},
        502: {"model": ErrorDetail},
        504: {"model": ErrorDetail},
    },
)
admin_dep = Depends(require_admin)

ETL_TIMEOUT_SECONDS = 30.0


def _get_etl_client() -> httpx.AsyncClient:
    current_settings = Settings()
    base_url = current_settings.ETL_API_URL.strip()
    if not base_url:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="ETL service URL is not configured",
        )

    headers: dict[str, str] = {}
    if current_settings.ETL_API_KEY:
        headers["X-ETL-API-Key"] = current_settings.ETL_API_KEY

    return httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=ETL_TIMEOUT_SECONDS,
    )


async def _request_etl(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    allow_not_found: bool = False,
) -> Any:
    try:
        async with _get_etl_client() as client:
            response = await client.request(
                method,
                path,
                params=params,
                json=json_body,
            )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
            detail="ETL service timed out",
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail=f"ETL service unavailable: {exc}",
        )

    if allow_not_found and response.status_code == HTTPStatus.NOT_FOUND:
        detail = "Run not found"
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("detail"):
                detail = str(payload["detail"])
        except ValueError:
            pass
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=detail)

    if response.status_code >= 400:
        # Nunca propagar 401/403 do ETL como se fosse sessão expirada no front
        detail = f"ETL service error ({response.status_code})"
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("detail"):
                detail = f"ETL service error ({response.status_code}): {payload['detail']}"
        except ValueError:
            pass
        raise HTTPException(status_code=HTTPStatus.BAD_GATEWAY, detail=detail)

    try:
        return response.json()
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Invalid JSON response from ETL service",
        )


def _validate_etl_response[T: BaseModel](
    model_cls: type[T],
    data: Any,
    endpoint_name: str,
) -> T:
    try:
        return model_cls.model_validate(data)
    except ValidationError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail=f"Unexpected response format from ETL {endpoint_name}",
        )


@router.get(
    "/routines",
    response_model=list[Any],
    dependencies=[admin_dep],
    summary="Lista rotinas disponíveis no ETL",
)
async def list_etl_routines() -> list[Any]:
    data = await _request_etl("GET", "/routines")
    if not isinstance(data, list):
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Unexpected response format from ETL /routines",
        )
    return data


@router.post(
    "/runs",
    status_code=HTTPStatus.ACCEPTED,
    response_model=EtlRunTriggerResponse,
    summary="Dispara uma execução de ETL",
)
async def trigger_etl_run(
    payload: EtlRunTriggerRequest,
    current_user: AdminUser,
) -> EtlRunTriggerResponse:
    etl_payload = {
        "routines": payload.routines,
        "lattes_ids": payload.lattes_ids,
        "force": payload.force,
        "triggered_by": current_user.sub,
    }
    data = await _request_etl("POST", "/runs", json_body=etl_payload)
    return _validate_etl_response(EtlRunTriggerResponse, data, "/runs")


@router.get(
    "/runs",
    response_model=EtlRunListResponse,
    dependencies=[admin_dep],
    summary="Lista execuções de ETL com paginação e filtro por status",
)
async def list_etl_runs(
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    run_status: Annotated[str | None, Query(alias="status")] = None,
) -> EtlRunListResponse:
    params: dict[str, Any] = {"page": page, "per_page": per_page}
    if run_status and run_status.strip():
        params["status"] = run_status.strip()

    data = await _request_etl("GET", "/runs", params=params)
    return _validate_etl_response(EtlRunListResponse, data, "/runs")


@router.get(
    "/runs/{run_id}",
    response_model=EtlRunDetail,
    dependencies=[admin_dep],
    responses={404: {"model": ErrorDetail}},
    summary="Retorna detalhes de uma execução de ETL",
)
async def get_etl_run(run_id: UUID) -> EtlRunDetail:
    data = await _request_etl("GET", f"/runs/{run_id}", allow_not_found=True)
    return _validate_etl_response(EtlRunDetail, data, "/runs/{run_id}")


@router.get(
    "/runs/{run_id}/logs",
    response_model=EtlRunLogsResponse,
    dependencies=[admin_dep],
    summary="Retorna logs paginados por offset de uma execução de ETL",
)
async def get_etl_run_logs(
    run_id: UUID,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> EtlRunLogsResponse:
    data = await _request_etl(
        "GET",
        f"/runs/{run_id}/logs",
        params={"offset": offset, "limit": limit},
    )
    return _validate_etl_response(EtlRunLogsResponse, data, "/runs/{run_id}/logs")
