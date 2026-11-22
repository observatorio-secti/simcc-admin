from typing import Annotated

from fastapi import APIRouter, Depends

from simcc_admin.schemas import ErrorDetail, MeResponse, MeUser
from simcc_admin.security import AuthenticatedUser, get_current_user

router = APIRouter(tags=["auth"])


@router.get(
    "/me",
    response_model=MeResponse,
    responses={401: {"model": ErrorDetail}},
    summary="Retorna identidade do usuário autenticado e status de admin",
)
async def read_me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(
        user=MeUser(
            sub=current_user.sub,
            name=current_user.name,
            email=current_user.email,
        ),
        is_admin=current_user.is_admin,
    )
